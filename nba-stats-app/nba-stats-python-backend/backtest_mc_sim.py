#!/usr/bin/env python3

# backtest_mc_sim.py

# Function: Replay historical NBA games without future-data leakage, evaluate
# Monte Carlo predictions, and tune simulation weights chronologically.

# Inputs: Completed team game rows from PostgreSQL plus command-line backtest
# and model-tuning settings.

# Output: Matchup features, fitted weight vectors, evaluation metrics, and
# optional prediction/weight files.

"""Leakage-free historical backtest and weight tuner for mc_sim."""

from __future__ import annotations

# Libraries

import argparse
import asyncio
import csv
import json
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import groupby
from pathlib import Path
from typing import Iterable, Sequence

import asyncpg
import numpy as np
from dotenv import load_dotenv

import mc_sim


# Define the fixed width and positional contract of each team-stat vector.
STAT_COUNT = 20
# Preserve the production defaults for adjustments, calibration, and context.
DEFAULT_WEIGHTS = (
    # Weight defensive shot disruption.
    0.35,
    # Weight the defense's forced-turnover rate.
    0.50,
    # Weight defensive foul tendency.
    0.10,
    # Weight the defense's allowed free-throw rate.
    0.50,
    # Weight offensive shot quality.
    0.08,
    # Weight effective field-goal percentage allowed.
    0.45,
    # Weight defensive rebounding strength.
    0.60,
    # Weight the lineup plus-minus signal.
    0.10,
    # Start score calibration with an identity scale.
    1.00,
    # Start score calibration with no intercept.
    0.00,
    # Start with no learned home-margin effect.
    0.00,
    # Start with no learned rest-day margin effect.
    0.00,
)
# Name each weight in the same positional order used by the simulator.
WEIGHT_NAMES = (
    "shot_disruption",
    "forced_turnovers",
    "defensive_fouls",
    "allowed_ft_rate",
    "shot_quality",
    "allowed_efg",
    "defensive_rebounds",
    "lineup_plus_minus",
    "score_scale",
    "score_intercept",
    "home_margin_effect",
    "rest_day_margin_effect",
)
# Bound random search to plausible ranges for the eight simulation adjustments.
WEIGHT_RANGES = (
    (0.00, 0.70),
    (0.00, 1.00),
    (0.00, 0.25),
    (0.00, 1.00),
    (0.00, 0.20),
    (0.00, 0.90),
    (0.00, 1.00),
    (0.00, 0.20),
)
# Map accepted command-line season types to table suffixes and id prefixes.
SEASON_TYPES = {
    "preseason": ("preseason", "1"),
    "regular": ("regseason", "2"),
    "regular-season": ("regseason", "2"),
    "playoffs": ("poffsseason", "4"),
}

# Define production defaults used by API-triggered model tuning.
API_TUNE_TRIALS = 25
API_TUNING_ITERATIONS = 750
API_MIN_PRIOR_GAMES = 5
API_MAX_GAMES = 600
API_TRAIN_FRACTION = 0.70
API_WEIGHT_SEED = 20260709


# Calculate a bounded team-minus-opponent rest advantage for one game.
def rest_difference_for_dates(
    game_date: date | None,
    team_last: date | None,
    opponent_last: date | None,
) -> float:
    """Days without a game, capped at seven; unknown schedule is neutral."""
    # Unknown dates cannot support a trustworthy schedule adjustment.
    if game_date is None or team_last is None or opponent_last is None:
        return 0.0
    # Ignore invalid histories whose latest game is not before the target game.
    if team_last >= game_date or opponent_last >= game_date:
        return 0.0
    # Count off-days since the team's last game and cap long breaks at seven.
    team_rest = min(7, max(0, (game_date - team_last).days - 1))
    # Calculate the opponent's comparable capped rest count.
    opponent_rest = min(7, max(0, (game_date - opponent_last).days - 1))
    # Limit the modeled differential to three days in either direction.
    return float(max(-3, min(3, team_rest - opponent_rest)))


# Read one optional weight with a finite fallback for older vectors.
def _weight(weights: Sequence[float], index: int, fallback: float) -> float:
    # Missing trailing context weights should retain backward-compatible defaults.
    if len(weights) <= index:
        return fallback
    # Normalize NumPy or Python numeric values to a plain float.
    value = float(weights[index])
    # Prevent NaN or infinity from contaminating predicted scores.
    return value if math.isfinite(value) else fallback


# Apply learned home-court and rest effects while preserving the predicted total.
def apply_context(
    team_score: float,
    opponent_score: float,
    weights: Sequence[float],
    venue: int = 0,
    rest_difference: float = 0.0,
) -> tuple[float, float]:
    """Adjust the margin, preserving the total. Rest is team minus opponent.

    ``venue`` is +1 for the first team at home, -1 away, or 0 neutral/unknown.
    Both effects are in margin points and are learned with shrinkage.
    """
    # Restrict venue encoding to away, neutral, or home for the first team.
    if venue not in (-1, 0, 1):
        raise ValueError("venue must be -1, 0, or 1")
    # Reject non-finite inputs before performing score arithmetic.
    if not all(math.isfinite(float(value)) for value in
               (team_score, opponent_score, rest_difference)):
        raise ValueError("scores and rest difference must be finite")
    # Clamp caller-supplied rest to the same range used during model fitting.
    rest = max(-3.0, min(3.0, float(rest_difference)))
    # Combine venue and rest contributions into a single margin shift.
    margin_adjustment = (
        venue * _weight(weights, 10, 0.0) + rest * _weight(weights, 11, 0.0)
    )
    # Split the margin shift equally so the two-team point total is unchanged.
    return (
        float(team_score) + margin_adjustment / 2.0,
        float(opponent_score) - margin_adjustment / 2.0,
    )


# Store one team's database row in model-ready form.
@dataclass(frozen=True)
class TeamRow:
    # Identify the completed NBA game.
    game_id: str
    # Record the date used for chronological ordering.
    game_date: date
    # Store the team's abbreviation.
    team: str
    # Preserve venue and opponent text from the source row.
    matchup: str
    # Hold the ordered 20-value team-stat vector.
    stats: np.ndarray
    # Store pace when advanced stats are available.
    pace: float | None


# Pair the home and away TeamRow values for one completed game.
@dataclass(frozen=True)
class Game:
    # Preserve the shared game identifier.
    game_id: str
    # Preserve the shared completion date.
    game_date: date
    # Store the row identified as the home side.
    home: TeamRow
    # Store the other row as the away side.
    away: TeamRow


# Store one past game from a single team's perspective.
@dataclass(frozen=True)
class HistoryRecord:
    # Identify the opponent faced in this record.
    opponent: str
    # Store this team's box-score vector.
    stats: np.ndarray
    # Store the opposing team's aligned vector.
    opponent_stats: np.ndarray
    # Preserve this team's joined pace value when present.
    pace: float | None
    # Preserve the date for rest-day calculations.
    game_date: date | None = None


# Hold leakage-free features and actual scores for one historical prediction.
@dataclass(frozen=True)
class BacktestExample:
    # Identify the game represented by this example.
    game_id: str
    # Record its date for chronological splitting.
    game_date: date
    # Identify the home team.
    home_team: str
    # Identify the away team.
    away_team: str
    # Store pregame home-team aggregate statistics.
    home_stats: np.ndarray
    # Store pregame away-team aggregate statistics.
    away_stats: np.ndarray
    # Store the pregame expected possession pace.
    pace: float
    # Store league baselines calculated only from prior games.
    league_averages: np.ndarray
    # Store recent home-team defensive factors.
    home_defense: np.ndarray
    # Store recent away-team defensive factors.
    away_defense: np.ndarray
    # Store the completed home score as the training target.
    actual_home: float
    # Store the completed away score as the training target.
    actual_away: float
    # Store capped home-minus-away rest days.
    rest_difference: float = 0.0


# Package the six values required to predict a future two-team matchup.
@dataclass(frozen=True)
class MatchupTeamInputs:
    # Store recent and matchup-adjusted statistics for the requested team.
    team_stats: np.ndarray
    # Store the symmetric aggregate for its opponent.
    opponent_stats: np.ndarray
    # Store the expected pace shared by both predictions.
    pace: float
    # Store league rate baselines.
    league_averages: np.ndarray
    # Store the requested team's defensive factors.
    team_defense: np.ndarray
    # Store the opponent's defensive factors.
    opponent_defense: np.ndarray


# Pair one historical example with its predicted home and away scores.
@dataclass(frozen=True)
class Prediction:
    # Retain the source features and actual outcomes.
    example: BacktestExample
    # Store the model's home-team score estimate.
    predicted_home: float
    # Store the model's away-team score estimate.
    predicted_away: float


# Collect aggregate error and winner metrics for a prediction set.
@dataclass(frozen=True)
class Metrics:
    # Count the games included in the evaluation.
    games: int
    # Store mean absolute error across individual team scores.
    score_mae: float
    # Store root mean squared error across individual team scores.
    score_rmse: float
    # Store signed mean score error to reveal systematic bias.
    score_bias: float
    # Store mean absolute game-total error.
    total_mae: float
    # Store mean absolute point-margin error.
    margin_mae: float
    # Store the fraction of non-tied games with the correct winner.
    winner_accuracy: float


# Parse all standalone backtest and tuning command-line options.
def parse_args() -> argparse.Namespace:
    # Create a parser whose description explains the leakage-free workflow.
    parser = argparse.ArgumentParser(
        description=(
            "Replay completed NBA games using only earlier games, evaluate "
            "mc_sim, and optionally tune its adjustment weights."
        )
    )
    # Accept the human-readable season used to derive a database id.
    parser.add_argument("--season", default="2025-26")
    # Restrict season type to table mappings known by this module.
    parser.add_argument(
        "--season-type",
        choices=sorted(SEASON_TYPES),
        default="playoffs",
    )
    # Allow advanced callers to override automatic season-id derivation.
    parser.add_argument("--season-id", help="Override the derived NBA season id")
    # Configure the rolling number of games used for recent form.
    parser.add_argument("--recent-games", type=int, default=20)
    # Require this many earlier games before a historical game is eligible.
    parser.add_argument("--min-prior-games", type=int, default=5)
    # Configure the strength of the head-to-head performance adjustment.
    parser.add_argument("--matchup-adjustment", type=float, default=1.0)
    # Configure shrinkage toward overall form for small matchup samples.
    parser.add_argument("--matchup-prior-games", type=float, default=5.0)
    # Configure Monte Carlo draws per final evaluation prediction.
    parser.add_argument("--iterations", type=int, default=3000)
    # Configure deterministic random-number generation.
    parser.add_argument("--seed", type=int, default=20260709)
    # Optionally retain only the newest eligible examples.
    parser.add_argument("--max-games", type=int)
    # Optionally exclude examples before this ISO date.
    parser.add_argument("--start-date", type=date.fromisoformat)
    # Optionally exclude examples after this ISO date.
    parser.add_argument("--end-date", type=date.fromisoformat)
    # Configure how many random adjustment candidates to compare.
    parser.add_argument(
        "--tune-trials",
        type=int,
        default=0,
        help="Number of random weight candidates; zero evaluates defaults only",
    )
    # Configure the earlier-date share used for training during CLI tuning.
    parser.add_argument("--train-fraction", type=float, default=0.70)
    # Configure lower-cost draws used while selecting weights.
    parser.add_argument("--tuning-iterations", type=int, default=750)
    # Optionally export per-game predictions to CSV.
    parser.add_argument("--predictions-csv", type=Path)
    # Optionally export the selected named weights to JSON.
    parser.add_argument("--weights-output", type=Path)
    # Parse the current process arguments into one namespace.
    return parser.parse_args()


# Derive the NBA database season id from a display season and canonical type.
def derive_season_id(season: str, season_type: str) -> str:
    # Convert the leading four-digit season year into an integer.
    try:
        start_year = int(season[:4])
    # Replace low-level conversion failures with a caller-facing format error.
    except (TypeError, ValueError):
        raise ValueError("season must look like 2025-26") from None
    # Prefix the start year with the season-type code used in stored rows.
    return f"{SEASON_TYPES[season_type][1]}{start_year}"


# Normalize supported frontend season labels into table-mapping keys.
def normalize_season_type(season_type: str) -> str:
    """Translate frontend season labels to the backtest's canonical keys."""
    # Ignore case, underscores, hyphens, and repeated whitespace.
    normalized = " ".join(
        season_type.strip().lower().replace("_", " ").replace("-", " ").split()
    )
    # Map accepted display, table-style, and synonym spellings.
    aliases = {
        "pre season": "preseason",
        "preseason": "preseason",
        "regular": "regular",
        "regular season": "regular",
        "regseason": "regular",
        "playoff": "playoffs",
        "playoffs": "playoffs",
        "postseason": "playoffs",
    }
    # Return the canonical key or a clear unsupported-type error.
    try:
        return aliases[normalized]
    except KeyError:
        raise ValueError(f"Unsupported season type: {season_type}") from None


# Open a PostgreSQL connection from process environment configuration.
async def connect_from_env() -> asyncpg.Connection:
    # Load local dotenv values when this file is run as a standalone tool.
    load_dotenv()
    # Define credentials that have no safe operational default.
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    # Collect every required variable that is absent or empty.
    missing = [name for name in required if not os.getenv(name)]
    # Fail once with the complete missing-setting list.
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    # Connect with required credentials and conventional local defaults.
    return await asyncpg.connect(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )


# Convert nullable database numerics into model-safe float values.
def _to_float(value: object) -> float:
    # Treat SQL NULL as zero and normalize all other numeric types.
    return float(value) if value is not None else 0.0


# Convert one asyncpg team row into the simulator's ordered 20-stat vector.
def _stats_from_row(row: asyncpg.Record) -> np.ndarray:
    # Read and normalize every database column in production index order.
    values = np.array(
        [
            _to_float(row["minutes"]),
            _to_float(row["field_goals_made"]),
            _to_float(row["field_goals_attempted"]),
            _to_float(row["field_goals_percentage"]),
            _to_float(row["field_goal_threes_made"]),
            _to_float(row["field_goal_threes_attempted"]),
            _to_float(row["field_goal_threes_percentage"]),
            _to_float(row["free_throws_made"]),
            _to_float(row["free_throws_attempted"]),
            _to_float(row["free_throws_percentage"]),
            _to_float(row["offensive_rebounds"]),
            _to_float(row["defensive_rebounds"]),
            _to_float(row["rebounds"]),
            _to_float(row["assists"]),
            _to_float(row["steals"]),
            _to_float(row["blocks"]),
            _to_float(row["turnovers"]),
            _to_float(row["personal_fouls"]),
            _to_float(row["points"]),
            _to_float(row["plus_minus"]),
        ],
        # Store doubles to match the compiled simulator's typed views.
        dtype=np.float64,
    )
    # Guard against accidental query/schema changes that alter vector width.
    if values.shape != (STAT_COUNT,):
        raise ValueError("Historical stat row did not contain 20 model inputs")
    # Return the validated model-ready vector.
    return values


# Fetch completed season rows once, attach pace, and pair teams into games.
async def load_games(
    connection: asyncpg.Connection,
    season_type: str,
    season_id: str,
) -> list[Game]:
    # Resolve the season-specific table suffix.
    suffix = SEASON_TYPES[season_type][0]
    # Build the NBA game-id prefix that separates season phases.
    game_id_prefix = f"00{SEASON_TYPES[season_type][1]}"
    # Select the basic team-game table for this season phase.
    holder = f"nbawlholder{suffix}"
    # Select the matching advanced-stat table that contains pace.
    advanced = f"nbateamadvancedstats{suffix}"
    # Retrieve all required model columns and pace in one ordered query.
    rows = await connection.fetch(
        f"""
        SELECT h.game_id, h.game_date::date AS game_date,
               h.team_abbreviation, h.matchup, h.minutes,
               h.field_goals_made, h.field_goals_attempted,
               h.field_goals_percentage, h.field_goal_threes_made,
               h.field_goal_threes_attempted,
               h.field_goal_threes_percentage, h.free_throws_made,
               h.free_throws_attempted, h.free_throws_percentage,
               h.offensive_rebounds, h.defensive_rebounds, h.rebounds,
               h.assists, h.steals, h.blocks, h.turnovers,
               h.personal_fouls, h.points, h.plus_minus, a.pace
        FROM {holder} h
        LEFT JOIN {advanced} a
          ON a.game_id = h.game_id
         AND a.team_tricode = h.team_abbreviation
        WHERE h.season_id = $1
          AND h.wl IS NOT NULL
          AND LEFT(h.game_id, 3) = $2
        ORDER BY h.game_date::date, h.game_id, h.team_abbreviation
        """,
        season_id,
        game_id_prefix,
    )

    # Convert database records into typed immutable team rows.
    team_rows: list[TeamRow] = []
    # Preserve the SQL ordering while normalizing each record.
    for row in rows:
        # Append one model-ready perspective for this team and game.
        team_rows.append(
            TeamRow(
                # Copy the database game identifier.
                game_id=row["game_id"],
                # Copy the date already cast by PostgreSQL.
                game_date=row["game_date"],
                # Copy the team's abbreviation.
                team=row["team_abbreviation"],
                # Preserve venue text for home-team identification.
                matchup=row["matchup"],
                # Convert all box-score columns into one ordered array.
                stats=_stats_from_row(row),
                # Preserve missing pace as None rather than a false observation.
                pace=_to_float(row["pace"]) if row["pace"] is not None else None,
            )
        )

    # Pair exactly two valid team rows into each completed Game.
    games: list[Game] = []
    # Group adjacent rows by the game-id ordering guaranteed by the query.
    for game_id, grouped in groupby(team_rows, key=lambda row: row.game_id):
        # Materialize the group so its size and both members are accessible.
        pair = list(grouped)
        # Skip incomplete or duplicated games that cannot form one matchup.
        if len(pair) != 2:
            continue
        # Identify the home row through the source matchup convention.
        home = next((row for row in pair if " vs. " in row.matchup), None)
        # Skip malformed pairs whose venue cannot be identified.
        if home is None:
            continue
        # The remaining row is necessarily the away side.
        away = pair[0] if pair[1] is home else pair[1]
        # Store one completed game using the home date as the shared date.
        games.append(Game(game_id, home.game_date, home, away))
    # Defensively restore chronological order for all downstream rolling logic.
    games.sort(key=lambda game: (game.game_date, game.game_id))
    # Return the clean, ordered completed-game list.
    return games


# Average the team-stat vectors held by a nonempty history slice.
def _mean_stats(records: Sequence[HistoryRecord]) -> np.ndarray:
    # Stack equal-width vectors by game and average each statistic column.
    return np.mean(np.stack([record.stats for record in records]), axis=0)


# Restore percentage consistency and physical bounds after averaging counts.
def _recompute_percentages(stats: np.ndarray) -> np.ndarray:
    # Copy input values so callers' historical arrays remain immutable.
    result = np.array(stats, dtype=np.float64, copy=True)
    # Recalculate field-goal percentage from averaged makes and attempts.
    result[3] = result[1] / result[2] if result[2] > 0.0 else 0.0
    # Recalculate three-point percentage from its component columns.
    result[6] = result[4] / result[5] if result[5] > 0.0 else 0.0
    # Recalculate free-throw percentage from its component columns.
    result[9] = result[7] / result[8] if result[8] > 0.0 else 0.0
    # Clamp every statistic except signed plus-minus to zero or greater.
    for index in range(STAT_COUNT - 1):
        result[index] = max(0.0, result[index])
    # Return the internally consistent team vector.
    return result


# Blend recent overall form with shrunken head-to-head performance.
def build_team_input(
    history: Sequence[HistoryRecord],
    opponent: str,
    recent_games: int,
    matchup_adjustment: float,
    matchup_prior_games: float,
) -> np.ndarray:
    # Restrict the baseline to the requested number of newest games.
    recent = history[-recent_games:]
    # Average overall form across that recent slice.
    base = _mean_stats(recent)
    # Extract every historical game played against the selected opponent.
    matchup_records = [record for record in history if record.opponent == opponent]
    # Apply matchup context only when data exists and its weight is nonzero.
    if matchup_records and matchup_adjustment:
        # Bound head-to-head history by the same recent-game window.
        matchup_records = matchup_records[-recent_games:]
        # Calculate the opponent-specific average vector.
        matchup_mean = _mean_stats(matchup_records)
        # Shrink small matchup samples toward overall form.
        shrinkage = len(matchup_records) / (
            len(matchup_records) + max(0.0, matchup_prior_games)
        )
        # Move the baseline toward matchup form by the configured strength.
        base = base + matchup_adjustment * shrinkage * (matchup_mean - base)
    # Recompute rate columns after all count-based blending.
    return _recompute_percentages(base)


# Calculate league baseline rates from all supplied historical perspectives.
def league_averages(history: Sequence[HistoryRecord]) -> np.ndarray:
    # Sum each team's own stat vector across history.
    stats = np.sum(np.stack([record.stats for record in history]), axis=0)
    # Sum the aligned opposing vectors for rebound-chance calculation.
    opponent_stats = np.sum(
        np.stack([record.opponent_stats for record in history]), axis=0
    )
    # Convert totals into the five rates consumed by the simulator.
    return _league_averages_from_totals(stats, opponent_stats)


# Convert cumulative league stat vectors into five simulation baselines.
def _league_averages_from_totals(
    stats: np.ndarray, opponent_stats: np.ndarray
) -> np.ndarray:
    # Estimate total offensive actions for the turnover-rate denominator.
    action_total = stats[2] + 0.44 * stats[8] + stats[16]
    # Combine offensive and opposing defensive rebounds into available chances.
    rebound_chances = stats[10] + opponent_stats[11]
    # Return league shooting, turnover, and rebounding rates.
    return np.array(
        [
            # Overall field-goal percentage or a stable league fallback.
            stats[1] / stats[2] if stats[2] else 0.471,
            # Three-point percentage or its league fallback.
            stats[4] / stats[5] if stats[5] else 0.360,
            # Free-throw percentage or its league fallback.
            stats[7] / stats[8] if stats[8] else 0.783,
            # Turnovers per estimated action.
            stats[16] / action_total if action_total else 0.127,
            # Offensive rebounds per available rebound chance.
            stats[10] / rebound_chances if rebound_chances else 0.305,
        ],
        # Preserve double precision for the Cython simulation interface.
        dtype=np.float64,
    )


# Calculate opponent-facing defensive factors over a recent history window.
def defensive_four_factors(
    history: Sequence[HistoryRecord], recent_games: int
) -> np.ndarray:
    # Select only the requested number of newest defensive performances.
    recent = history[-recent_games:]
    # Sum the team's own values across those games.
    own = np.sum(np.stack([record.stats for record in recent]), axis=0)
    # Sum what its opponents produced in the same games.
    opponent = np.sum(
        np.stack([record.opponent_stats for record in recent]), axis=0
    )
    # Estimate opponent actions for a turnover-rate denominator.
    opponent_actions = opponent[2] + 0.44 * opponent[8] + opponent[16]
    # Combine own defensive and opponent offensive rebounds into chances.
    defensive_rebound_chances = own[11] + opponent[10]
    # Return effective shooting, turnovers, free throws, and rebounding allowed.
    return np.array(
        [
            # Opponent effective field-goal percentage.
            (opponent[1] + 0.5 * opponent[4]) / opponent[2]
            if opponent[2]
            else 0.545,
            # Opponent turnover rate.
            opponent[16] / opponent_actions if opponent_actions else 0.127,
            # Opponent free-throw-attempt rate.
            opponent[8] / opponent[2] if opponent[2] else 0.250,
            # Team defensive-rebound share.
            own[11] / defensive_rebound_chances
            if defensive_rebound_chances
            else 0.695,
        ],
        # Match the simulator's required double-precision input.
        dtype=np.float64,
    )


# Estimate matchup pace from both recent histories with a box-score fallback.
def expected_pace(
    home_history: Sequence[HistoryRecord],
    away_history: Sequence[HistoryRecord],
    recent_games: int,
) -> float:
    # Collect known positive pace observations for both teams' recent games.
    paces = [
        record.pace
        for record in list(home_history[-recent_games:])
        + list(away_history[-recent_games:])
        if record.pace is not None and record.pace > 0.0
    ]
    # Prefer the combined observed pace mean when available.
    if paces:
        return float(np.mean(paces))
    # Estimate possessions from the home history when advanced pace is missing.
    stats = _mean_stats(home_history[-recent_games:])
    # Keep fallback pace positive for safe simulation iteration.
    return max(1.0, stats[2] + 0.44 * stats[8] + stats[16] - stats[10])


# Build all future-matchup model inputs from completed games only.
def build_matchup_team_inputs(
    games: Sequence[Game],
    team: str,
    opponent: str,
    recent_games: int,
    min_prior_games: int = API_MIN_PRIOR_GAMES,
    matchup_adjustment: float = 1.0,
    matchup_prior_games: float = 5.0,
) -> MatchupTeamInputs:
    # Accumulate chronological history separately for every team abbreviation.
    histories: dict[str, list[HistoryRecord]] = defaultdict(list)
    # Accumulate all team perspectives for shared league baselines.
    all_history: list[HistoryRecord] = []

    # Sort defensively so each team's appended history remains chronological.
    for game in sorted(games, key=lambda game: (game.game_date, game.game_id)):
        # Represent the completed game from the home team's perspective.
        home_record = HistoryRecord(
            game.away.team, game.home.stats, game.away.stats, game.home.pace,
            game.game_date,
        )
        # Represent the same game from the away team's perspective.
        away_record = HistoryRecord(
            game.home.team, game.away.stats, game.home.stats, game.away.pace,
            game.game_date,
        )
        # Append each perspective to its team's rolling history.
        histories[game.home.team].append(home_record)
        histories[game.away.team].append(away_record)
        # Add both perspectives to the league-wide calculation set.
        all_history.extend((home_record, away_record))

    # Resolve histories for the two requested teams.
    team_history = histories[team]
    opponent_history = histories[opponent]
    # Require enough completed games on both sides plus league context.
    if (
        len(team_history) < min_prior_games
        or len(opponent_history) < min_prior_games
        or not all_history
    ):
        raise ValueError("Not enough completed games for team aggregation")

    # Package symmetric team inputs with shared pace and league context.
    return MatchupTeamInputs(
        # Build recent and head-to-head-adjusted stats for the requested team.
        team_stats=build_team_input(
            team_history,
            opponent,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        # Build the same adjusted vector from the opponent's perspective.
        opponent_stats=build_team_input(
            opponent_history,
            team,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        # Average recent pace observations across both teams.
        pace=expected_pace(team_history, opponent_history, recent_games),
        # Calculate league baselines from every supplied completed game.
        league_averages=league_averages(all_history),
        # Calculate recent defensive context for the requested team.
        team_defense=defensive_four_factors(team_history, recent_games),
        # Calculate recent defensive context for the opponent.
        opponent_defense=defensive_four_factors(opponent_history, recent_games),
    )


# Load one requested season and aggregate model inputs for a future matchup.
async def calculate_matchup_team_inputs(
    connection: asyncpg.Connection,
    season: str,
    season_type: str,
    team: str,
    opponent: str,
    recent_games: int = 20,
) -> MatchupTeamInputs:
    # Normalize UI season text before using the table mapping.
    canonical_season_type = normalize_season_type(season_type)
    # Derive the database season id from the display season.
    season_id = derive_season_id(season, canonical_season_type)
    # Fetch and pair all completed games for that season phase.
    games = await load_games(connection, canonical_season_type, season_id)
    # Aggregate the requested teams from the completed-game snapshot.
    return build_matchup_team_inputs(
        games,
        team,
        opponent,
        recent_games,
    )


# Build chronological, leakage-free training examples from completed games.
def build_examples(
    games: Sequence[Game],
    recent_games: int,
    min_prior_games: int,
    matchup_adjustment: float,
    matchup_prior_games: float,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[BacktestExample]:
    # Maintain each team's history using only earlier completion dates.
    histories: dict[str, list[HistoryRecord]] = defaultdict(list)
    # Maintain league own-stat totals incrementally for O(n) construction.
    stats_totals = np.zeros(STAT_COUNT, dtype=np.float64)
    # Maintain aligned opponent totals for league rebound chances.
    opponent_totals = np.zeros(STAT_COUNT, dtype=np.float64)
    # Track whether league context contains at least one prior team row.
    history_count = 0
    # Accumulate every game that satisfies date and prior-history requirements.
    examples: list[BacktestExample] = []

    # Sort once so batching and rolling histories are deterministic.
    ordered_games = sorted(games, key=lambda game: (game.game_date, game.game_id))
    # Batch by date so same-day results are never visible to each other.
    for game_date, date_games_iter in groupby(ordered_games, key=lambda game: game.game_date):
        # Materialize this date's games for separate predict-then-update passes.
        date_games = list(date_games_iter)
        # Build eligible examples before adding any result from this date.
        for game in date_games:
            # Resolve both teams' histories as of the previous date.
            home_history = histories[game.home.team]
            away_history = histories[game.away.team]
            # Apply optional inclusive command-line date boundaries.
            in_date_range = (
                (start_date is None or game_date >= start_date)
                and (end_date is None or game_date <= end_date)
            )
            # Require the date range, both history thresholds, and league context.
            if (
                in_date_range
                and len(home_history) >= min_prior_games
                and len(away_history) >= min_prior_games
                and history_count
            ):
                # Append one complete feature/target record for this game.
                examples.append(
                    BacktestExample(
                        # Preserve identity and ordering metadata.
                        game_id=game.game_id,
                        game_date=game.game_date,
                        # Preserve the matchup participants.
                        home_team=game.home.team,
                        away_team=game.away.team,
                        # Build home features exclusively from earlier history.
                        home_stats=build_team_input(
                            home_history,
                            game.away.team,
                            recent_games,
                            matchup_adjustment,
                            matchup_prior_games,
                        ),
                        # Build away features through the same historical logic.
                        away_stats=build_team_input(
                            away_history,
                            game.home.team,
                            recent_games,
                            matchup_adjustment,
                            matchup_prior_games,
                        ),
                        # Estimate pace using only each team's earlier games.
                        pace=expected_pace(
                            home_history, away_history, recent_games
                        ),
                        # Convert running prior-game totals into league baselines.
                        league_averages=_league_averages_from_totals(
                            stats_totals, opponent_totals
                        ),
                        # Calculate the home defense's recent opponent outcomes.
                        home_defense=defensive_four_factors(
                            home_history, recent_games
                        ),
                        # Calculate the away defense's recent opponent outcomes.
                        away_defense=defensive_four_factors(
                            away_history, recent_games
                        ),
                        # Attach final scores only as supervised targets.
                        actual_home=game.home.stats[18],
                        actual_away=game.away.stats[18],
                        # Calculate pregame schedule context from last appearances.
                        rest_difference=rest_difference_for_dates(
                            game.game_date,
                            home_history[-1].game_date,
                            away_history[-1].game_date,
                        ),
                    )
                )

        # Update after all games on the date so same-day finals cannot leak.
        # Add this date's results only after every eligible example is frozen.
        for game in date_games:
            # Create the new home-team historical perspective.
            home_record = HistoryRecord(
                game.away.team, game.home.stats, game.away.stats, game.home.pace,
                game.game_date,
            )
            # Create the mirrored away-team perspective.
            away_record = HistoryRecord(
                game.home.team, game.away.stats, game.home.stats, game.away.pace,
                game.game_date,
            )
            # Publish both records to their teams for later dates.
            histories[game.home.team].append(home_record)
            histories[game.away.team].append(away_record)
            # Keep the original home/away summation order, but avoid stacking
            # the growing league history again for every example (O(n²)).
            # Add home and away values to cumulative own-stat totals.
            stats_totals += game.home.stats
            stats_totals += game.away.stats
            # Add their mirrored values to cumulative opponent totals.
            opponent_totals += game.away.stats
            opponent_totals += game.home.stats
            # Record the two newly available team perspectives.
            history_count += 2
    # Return examples in chronological input order.
    return examples


# Run symmetric Monte Carlo score predictions for every historical example.
def predict_examples(
    examples: Sequence[BacktestExample],
    weights: Sequence[float],
    iterations: int,
    seed: int,
) -> list[Prediction]:
    # Accumulate predictions in the same order as the examples.
    predictions: list[Prediction] = []
    # Give each game a deterministic seed derived from its sequence position.
    for index, example in enumerate(examples):
        game_seed = seed + index * 2 + 1
        # Predict home scoring against the away team's defensive factors.
        predicted_home = mc_sim.run_monte_carlo_simulation(
            example.home_stats,
            example.away_stats,
            example.pace,
            example.league_averages,
            example.away_defense,
            iterations,
            weights,
            game_seed,
        )
        # Predict away scoring from the mirrored offensive/defensive perspective.
        predicted_away = mc_sim.run_monte_carlo_simulation(
            example.away_stats,
            example.home_stats,
            example.pace,
            example.league_averages,
            example.home_defense,
            iterations,
            weights,
            # Common random numbers reduce noise in the estimated margin,
            # matching the API's symmetry when two team inputs are identical.
            game_seed,
        )
        # Apply learned home and rest effects while preserving game total.
        predicted_home, predicted_away = apply_context(
            predicted_home, predicted_away, weights, venue=1,
            rest_difference=example.rest_difference,
        )
        # Retain both estimates alongside their actual historical target.
        predictions.append(Prediction(example, predicted_home, predicted_away))
    # Return all completed historical predictions.
    return predictions


# Calculate score, total, margin, bias, and winner metrics for predictions.
def calculate_metrics(predictions: Sequence[Prediction]) -> Metrics:
    # Empty sets cannot produce meaningful aggregate error values.
    if not predictions:
        raise ValueError("No predictions to score")
    # Collect absolute team-score errors for MAE.
    errors: list[float] = []
    # Collect signed team-score errors for bias.
    signed_errors: list[float] = []
    # Collect squared team-score errors for RMSE.
    squared_errors: list[float] = []
    # Collect absolute combined-score errors.
    total_errors: list[float] = []
    # Collect absolute predicted-margin errors.
    margin_errors: list[float] = []
    # Collect binary winner correctness for non-tied actual games.
    winner_hits: list[float] = []
    # Score every paired home/away prediction.
    for prediction in predictions:
        # Resolve actual scores and context through the retained example.
        example = prediction.example
        # Process both team scores with identical error logic.
        for predicted, actual in (
            (prediction.predicted_home, example.actual_home),
            (prediction.predicted_away, example.actual_away),
        ):
            # Preserve sign before deriving absolute and squared variants.
            difference = predicted - actual
            errors.append(abs(difference))
            signed_errors.append(difference)
            squared_errors.append(difference * difference)
        # Compare predicted and actual combined game totals.
        total_errors.append(
            abs(
                prediction.predicted_home
                + prediction.predicted_away
                - example.actual_home
                - example.actual_away
            )
        )
        # Calculate predicted and actual home-minus-away margins.
        predicted_margin = prediction.predicted_home - prediction.predicted_away
        actual_margin = example.actual_home - example.actual_away
        # Record absolute point-margin error.
        margin_errors.append(abs(predicted_margin - actual_margin))
        # Exclude actual ties because neither team is the winner.
        if actual_margin != 0.0:
            # Record whether predicted and actual margins have the same sign.
            winner_hits.append(float((predicted_margin > 0.0) == (actual_margin > 0.0)))
    # Aggregate primitive error lists into the immutable public metric record.
    return Metrics(
        games=len(predictions),
        score_mae=float(np.mean(errors)),
        score_rmse=math.sqrt(float(np.mean(squared_errors))),
        score_bias=float(np.mean(signed_errors)),
        total_mae=float(np.mean(total_errors)),
        margin_mae=float(np.mean(margin_errors)),
        winner_accuracy=float(np.mean(winner_hits)) if winner_hits else math.nan,
    )


# Yield the default adjustment vector followed by reproducible random candidates.
def candidate_weights(trials: int, seed: int) -> Iterable[tuple[float, ...]]:
    # Always evaluate the current production adjustments as a baseline.
    yield DEFAULT_WEIGHTS[:8]
    # Isolate candidate generation in a locally seeded random stream.
    rng = random.Random(seed)
    # Draw the requested number of independent candidates.
    for _ in range(trials):
        # Sample each adjustment uniformly within its plausible range.
        yield tuple(rng.uniform(low, high) for low, high in WEIGHT_RANGES)


# Apply one shared linear calibration to both team scores in every prediction.
def apply_score_calibration(
    predictions: Sequence[Prediction], scale: float, intercept: float
) -> list[Prediction]:
    # Rebuild immutable Prediction records with calibrated score values.
    return [
        Prediction(
            prediction.example,
            scale * prediction.predicted_home + intercept,
            scale * prediction.predicted_away + intercept,
        )
        for prediction in predictions
    ]


# Fit robust shared scale and intercept values by minimizing score MAE.
def fit_score_calibration(predictions: Sequence[Prediction]) -> tuple[float, float]:
    # Flatten predicted home and away scores into one numeric vector.
    predicted = np.array(
        [
            score
            for prediction in predictions
            for score in (prediction.predicted_home, prediction.predicted_away)
        ],
        dtype=np.float64,
    )
    # Flatten matching actual scores in exactly the same order.
    actual = np.array(
        [
            score
            for prediction in predictions
            for score in (
                prediction.example.actual_home,
                prediction.example.actual_away,
            )
        ],
        dtype=np.float64,
    )
    # Begin with identity scaling.
    best_scale = 1.0
    # Use the median residual as a robust initial intercept.
    best_intercept = float(np.median(actual - predicted))
    # Initialize the best objective above every finite candidate MAE.
    best_mae = math.inf
    # Search a fine grid of plausible shared score scales.
    for scale in np.linspace(0.75, 1.35, 121):
        # For a fixed scale, the median residual minimizes absolute error.
        intercept = float(np.median(actual - scale * predicted))
        # Prevent calibration from learning an implausibly large point shift.
        intercept = min(30.0, max(-20.0, intercept))
        # Calculate mean absolute team-score error for this pair.
        mae = float(np.mean(np.abs(scale * predicted + intercept - actual)))
        # Retain the first strictly better calibration.
        if mae < best_mae:
            best_scale = float(scale)
            best_intercept = intercept
            best_mae = mae
    # Return the lowest-MAE scale and intercept.
    return best_scale, best_intercept


# Select adjustments on later dates, then refit calibration/context on all data.
def tune_model_weights(
    examples: Sequence[BacktestExample],
    trials: int = API_TUNE_TRIALS,
    iterations: int = API_TUNING_ITERATIONS,
    seed: int = API_WEIGHT_SEED,
) -> np.ndarray:
    """Fit on earlier dates, select by later score MAE, then refit all history."""
    # Random search counts cannot be negative.
    if trials < 0:
        raise ValueError("trials cannot be negative")
    # Every candidate prediction requires at least one simulation iteration.
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    # With no eligible games, return a contiguous copy of production defaults.
    if not examples:
        return np.ascontiguousarray(DEFAULT_WEIGHTS, dtype=np.float64)

    # Sort defensively before creating the chronological selection split.
    ordered = sorted(examples, key=lambda example: (example.game_date, example.game_id))
    # Choose the date boundary nearest the production train fraction.
    split = chronological_split_index(ordered, API_TRAIN_FRACTION)
    # Require enough total, training, and validation games for honest selection.
    can_select = len(ordered) >= 30 and split >= 15 and len(ordered) - split >= 8
    # Initialize the selection objective above all finite candidate errors.
    best_mae = math.inf
    # Fall back to production adjustments until a candidate improves the objective.
    best_adjustments = DEFAULT_WEIGHTS[:8]
    # Retain raw predictions for final all-history parameter fitting.
    best_raw: list[Prediction] = []
    # Evaluate defaults plus random candidates only when validation is reliable.
    for adjustments in candidate_weights(trials if can_select else 0, seed):
        # Predict all examples with candidate adjustments and neutral calibration.
        raw = predict_examples(ordered, tuple(adjustments) + (1.0, 0.0), iterations, seed)
        # Fit earlier games and score the untouched later-date slice.
        if can_select:
            fitted = fit_prediction_parameters(raw[:split], adjustments)
            validation = apply_prediction_parameters(raw[split:], fitted)
            score_mae = calculate_metrics(validation).score_mae
        # Avoid in-sample candidate selection when history is too sparse.
        else:
            # Sparse history uses the default candidate instead of selecting in-sample.
            score_mae = 0.0
        # Keep the strictly lowest validation-error candidate and its raw scores.
        if score_mae < best_mae:
            best_mae = score_mae
            best_adjustments = tuple(adjustments)
            best_raw = raw
    # Refit calibration and context for the winner using every available example.
    return np.ascontiguousarray(
        fit_prediction_parameters(best_raw, best_adjustments), dtype=np.float64
    )


# Find the nearest chronological split that does not divide one game date.
def chronological_split_index(examples: Sequence[BacktestExample], fraction: float) -> int:
    """Return a boundary between dates, never splitting one day's games."""
    # An empty example set has no valid split.
    if not examples:
        return 0
    # Record indexes whose adjacent examples fall on different dates.
    boundaries = [index for index in range(1, len(examples))
                  if examples[index - 1].game_date < examples[index].game_date]
    # Multiple games on one lone date cannot form a chronological holdout.
    if not boundaries:
        return 0
    # Convert the requested fraction into an ideal floating-point index.
    target = len(examples) * fraction
    # Select the legal date boundary closest to that ideal index.
    return min(boundaries, key=lambda index: abs(index - target))


# Fit score calibration plus shrunken home/rest margin coefficients.
def fit_prediction_parameters(
    raw: Sequence[Prediction], adjustments: Sequence[float],
) -> np.ndarray:
    """Fit shared score calibration and shrunken home/rest margin effects."""
    # Start with selected adjustments and neutral production trailing parameters.
    result = np.array(tuple(adjustments) + DEFAULT_WEIGHTS[8:], dtype=np.float64)
    # Tiny samples retain neutral calibration and context effects.
    if len(raw) < 5:
        return result
    # Fit a shared score scale and intercept against all team scores.
    scale, intercept = fit_score_calibration(raw)
    # Shrink calibration toward identity when fewer than 30 games are available.
    if len(raw) < 30:
        # Convert sample count into a smooth zero-to-one confidence weight.
        strength = len(raw) / (len(raw) + 30.0)
        # Shrink multiplicative deviation from one.
        scale = 1.0 + strength * (scale - 1.0)
        # Shrink the additive score shift toward zero.
        intercept *= strength
    # Store the score calibration in its fixed weight-vector positions.
    result[8:10] = (scale, intercept)
    # Apply calibration before fitting residual margin context.
    calibrated = apply_score_calibration(raw, scale, intercept)
    # Build an intercept/rest design matrix with rest clamped to training bounds.
    design = np.array([[1.0, max(-3.0, min(3.0, p.example.rest_difference))]
                       for p in calibrated], dtype=np.float64)
    # Calculate actual-minus-predicted home margins after score calibration.
    margin_residual = np.array([
        p.example.actual_home - p.example.actual_away
        - (p.predicted_home - p.predicted_away) for p in calibrated
    ])
    # Home advantage has a 40-game neutral prior; rest is shrunk more strongly
    # because schedule imbalance can otherwise absorb opponent/roster effects.
    # Solve ridge-regularized normal equations for home and rest effects.
    coefficients = np.linalg.solve(
        design.T @ design + np.diag([40.0, 80.0]),
        design.T @ np.clip(margin_residual, -40.0, 40.0),
    )
    # Limit learned home advantage to a plausible eight-point range.
    result[10] = np.clip(coefficients[0], -8.0, 8.0)
    # Limit each rest-day differential effect to three margin points.
    result[11] = np.clip(coefficients[1], -3.0, 3.0)
    # Return the complete contiguous-compatible parameter vector.
    return result


# Apply fitted score calibration and context to raw candidate predictions.
def apply_prediction_parameters(
    raw: Sequence[Prediction], weights: Sequence[float],
) -> list[Prediction]:
    # Accumulate rebuilt immutable predictions.
    predictions = []
    # Transform each raw home/away pair with the same fitted vector.
    for prediction in raw:
        # Calibrate both scores, then adjust their margin for venue and rest.
        home, away = apply_context(
            weights[8] * prediction.predicted_home + weights[9],
            weights[8] * prediction.predicted_away + weights[9],
            weights, venue=1, rest_difference=prediction.example.rest_difference,
        )
        # Preserve the source example while storing transformed scores.
        predictions.append(Prediction(prediction.example, home, away))
    # Return predictions ready for validation metrics.
    return predictions





# Calculate API-ready weights for one completed season request.
async def calculate_model_weights(
    connection: asyncpg.Connection,
    season: str,
    season_type: str,
    recent_games: int = 20,
    min_prior_games: int = API_MIN_PRIOR_GAMES,
    tune_trials: int = API_TUNE_TRIALS,
    tuning_iterations: int = API_TUNING_ITERATIONS,
    seed: int = API_WEIGHT_SEED,
) -> np.ndarray:
    """Calculate weights from completed games for one API season request."""
    # Validate history requirements before database or simulation work.
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    # Normalize frontend season text and derive its database identifier.
    canonical_season_type = normalize_season_type(season_type)
    season_id = derive_season_id(season, canonical_season_type)
    # Load all completed games for that season phase.
    games = await load_games(connection, canonical_season_type, season_id)
    # Build leakage-free examples with production matchup settings.
    examples = build_examples(
        games,
        recent_games,
        min_prior_games,
        matchup_adjustment=1.0,
        matchup_prior_games=5.0,
    )
    # Bound API tuning cost to the newest configured number of games.
    examples = examples[-API_MAX_GAMES:]

    # Monte Carlo tuning is CPU-bound. Keep it off the API event-loop thread.
    # Preserve responsiveness by dispatching the synchronous search to a worker.
    return await asyncio.to_thread(
        tune_model_weights,
        examples,
        tune_trials,
        tuning_iterations,
        seed,
    )


# Print one labeled metrics summary for command-line users.
def print_metrics(label: str, metrics: Metrics) -> None:
    # Identify the evaluated split and game count.
    print(f"\n{label} ({metrics.games} games)")
    # Print individual-team score accuracy and bias.
    print(f"  Team score MAE:  {metrics.score_mae:6.2f}")
    print(f"  Team score RMSE: {metrics.score_rmse:6.2f}")
    print(f"  Score bias:      {metrics.score_bias:+6.2f}")
    # Print combined total, margin, and winner performance.
    print(f"  Game total MAE:  {metrics.total_mae:6.2f}")
    print(f"  Margin MAE:      {metrics.margin_mae:6.2f}")
    print(f"  Winner accuracy: {metrics.winner_accuracy:6.1%}")


# Print every model weight with its stable human-readable name.
def print_weights(weights: Sequence[float]) -> None:
    # Introduce the indented name/value list.
    print("  Weights:")
    # Pair names and values in their shared positional order.
    for name, value in zip(WEIGHT_NAMES, weights):
        # Align names and format coefficients to four decimal places.
        print(f"    {name:22s} {value:.4f}")


# Export per-game predictions and actual scores to a CSV file.
def write_predictions(path: Path, predictions: Sequence[Prediction]) -> None:
    # Create missing parent directories for a user-supplied output path.
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open text output with CSV-controlled newline handling.
    with path.open("w", newline="", encoding="utf-8") as output:
        # Wrap the file handle with standards-compliant CSV serialization.
        writer = csv.writer(output)
        # Write stable column names before any prediction rows.
        writer.writerow(
            (
                "game_id",
                "game_date",
                "away_team",
                "home_team",
                "predicted_away",
                "predicted_home",
                "actual_away",
                "actual_home",
            )
        )
        # Serialize one record for every evaluated game.
        for prediction in predictions:
            # Resolve metadata and actual scores from the retained example.
            example = prediction.example
            # Write identifiers plus consistently formatted predicted/actual scores.
            writer.writerow(
                (
                    example.game_id,
                    example.game_date.isoformat(),
                    example.away_team,
                    example.home_team,
                    f"{prediction.predicted_away:.3f}",
                    f"{prediction.predicted_home:.3f}",
                    f"{example.actual_away:.0f}",
                    f"{example.actual_home:.0f}",
                )
            )


# Execute the complete standalone load, tune, evaluate, and export workflow.
async def run(args: argparse.Namespace) -> None:
    # Validate rolling-history sizes.
    if args.recent_games <= 0 or args.min_prior_games <= 0:
        raise ValueError("recent-games and min-prior-games must be positive")
    # Validate both final and tuning simulation counts.
    if args.iterations <= 0 or args.tuning_iterations <= 0:
        raise ValueError("iteration counts must be positive")
    # Require a majority training share while retaining a nonempty holdout.
    if not 0.5 <= args.train_fraction < 1.0:
        raise ValueError("train-fraction must be at least 0.5 and below 1.0")

    # Respect an explicit database season id or derive one from CLI values.
    season_id = args.season_id or derive_season_id(args.season, args.season_type)
    # Open the standalone tool's database connection.
    connection = await connect_from_env()
    # Guarantee connection cleanup after loading succeeds or fails.
    try:
        # Fetch and pair all completed games for the requested season phase.
        games = await load_games(connection, args.season_type, season_id)
    finally:
        # Release database resources before CPU-bound prediction work.
        await connection.close()
    # Build leakage-free examples within optional CLI date boundaries.
    examples = build_examples(
        games,
        args.recent_games,
        args.min_prior_games,
        args.matchup_adjustment,
        args.matchup_prior_games,
        args.start_date,
        args.end_date,
    )
    # Optionally restrict evaluation to the newest eligible games.
    if args.max_games is not None:
        examples = examples[-args.max_games :]
    # Stop with actionable guidance when no game can be evaluated.
    if not examples:
        raise RuntimeError("No eligible games; lower min-prior-games or check the season")

    # Summarize loaded and eligible sample counts.
    print(
        f"Loaded {len(games)} completed games for {args.season} "
        f"{args.season_type}; {len(examples)} are eligible."
    )
    # State the central no-future-data guarantee for the reported metrics.
    print(
        "All rolling stats, pace, league averages, and defensive factors "
        "exclude the predicted game and every later game."
    )

    # Use production defaults unless chronological tuning is requested.
    final_weights = DEFAULT_WEIGHTS
    # Evaluate the full example set unless a holdout replaces it below.
    final_examples = examples
    # Enter chronological train/holdout tuning only for positive trial counts.
    if args.tune_trials > 0:
        # Choose a legal split between complete game dates.
        split = chronological_split_index(examples, args.train_fraction)
        # Require a minimally meaningful sample for command-line tuning.
        if len(examples) < 10:
            raise RuntimeError("At least 10 eligible games are required for tuning")
        # Require at least two distinct dates for a nonempty chronological split.
        if split == 0:
            raise RuntimeError("Tuning requires eligible games on at least two dates")
        # Separate earlier training games from later untouched evaluation games.
        training = examples[:split]
        holdout = examples[split:]
        # Describe the candidate count and chronological partition.
        print(
            f"Tuning {args.tune_trials + 1} candidates on {len(training)} "
            f"earlier games; {len(holdout)} later games remain untouched."
        )
        # Tune solely on the earlier training slice.
        final_weights = tune_model_weights(
            training,
            args.tune_trials,
            args.tuning_iterations,
            args.seed,
        )
        # Evaluate the selected model on its own training data for diagnostics.
        best_metrics = calculate_metrics(
            predict_examples(
                training,
                final_weights,
                args.tuning_iterations,
                args.seed,
            )
        )
        # Print training diagnostics and selected coefficient values.
        print_metrics("Best training result", best_metrics)
        print_weights(final_weights)

        # Establish default-weight performance on the untouched later games.
        baseline_holdout = predict_examples(
            holdout, DEFAULT_WEIGHTS, args.iterations, args.seed + 1_000_000
        )
        # Report a fair chronological baseline comparison.
        print_metrics("Default weights - chronological holdout", calculate_metrics(baseline_holdout))
        # Make the later holdout the final tuned-model evaluation set.
        final_examples = holdout

    # Generate final predictions with an independent deterministic seed range.
    final_predictions = predict_examples(
        final_examples, final_weights, args.iterations, args.seed + 2_000_000
    )
    # Label results according to whether they use a holdout or full backtest.
    label = (
        "Tuned weights - chronological holdout"
        if args.tune_trials > 0
        else "Default weights - full backtest"
    )
    # Report final evaluation metrics.
    print_metrics(label, calculate_metrics(final_predictions))
    # Repeat tuned coefficients next to final holdout results for convenience.
    if args.tune_trials > 0:
        print_weights(final_weights)

    # Write optional per-game CSV output.
    if args.predictions_csv:
        write_predictions(args.predictions_csv, final_predictions)
        print(f"\nWrote predictions to {args.predictions_csv}")
    # Write optional named model-weight JSON output.
    if args.weights_output:
        # Create any missing parent directories.
        args.weights_output.parent.mkdir(parents=True, exist_ok=True)
        # Pair names with values and serialize an indented newline-terminated file.
        args.weights_output.write_text(
            json.dumps(dict(zip(WEIGHT_NAMES, final_weights)), indent=2) + "\n",
            encoding="utf-8",
        )
        # Confirm the destination path to the command-line user.
        print(f"Wrote weights to {args.weights_output}")


# Run the asynchronous workflow and translate expected failures for the CLI.
def main() -> None:
    # Keep successful setup and error conversion in one top-level boundary.
    try:
        # Parse arguments and execute the async workflow to completion.
        asyncio.run(run(parse_args()))
    # Present validation and database errors without an internal traceback.
    except (RuntimeError, ValueError, asyncpg.PostgresError) as error:
        raise SystemExit(f"backtest failed: {error}") from error


# Execute the CLI only when this file is run directly.
if __name__ == "__main__":
    # Delegate process behavior to the guarded main function.
    main()
