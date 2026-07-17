#!/usr/bin/env python3
"""Leakage-free historical backtest and weight tuner for mc_sim."""

from __future__ import annotations

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


STAT_COUNT = 20
DEFAULT_WEIGHTS = (
    0.35,
    0.50,
    0.10,
    0.50,
    0.08,
    0.45,
    0.60,
    0.10,
    1.00,
    0.00,
)
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
)
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
SEASON_TYPES = {
    "preseason": ("preseason", "1"),
    "regular": ("regseason", "2"),
    "regular-season": ("regseason", "2"),
    "playoffs": ("poffsseason", "4"),
}

API_TUNE_TRIALS = 25
API_TUNING_ITERATIONS = 750
API_MIN_PRIOR_GAMES = 5
API_MAX_GAMES = 120
API_TRAIN_FRACTION = 0.70
API_WEIGHT_SEED = 20260709


@dataclass(frozen=True)
class TeamRow:
    game_id: str
    game_date: date
    team: str
    matchup: str
    stats: np.ndarray
    pace: float | None


@dataclass(frozen=True)
class Game:
    game_id: str
    game_date: date
    home: TeamRow
    away: TeamRow


@dataclass(frozen=True)
class HistoryRecord:
    opponent: str
    stats: np.ndarray
    opponent_stats: np.ndarray
    pace: float | None


@dataclass(frozen=True)
class BacktestExample:
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    home_stats: np.ndarray
    away_stats: np.ndarray
    pace: float
    league_averages: np.ndarray
    home_defense: np.ndarray
    away_defense: np.ndarray
    actual_home: float
    actual_away: float


@dataclass(frozen=True)
class MatchupTeamInputs:
    team_stats: np.ndarray
    opponent_stats: np.ndarray
    pace: float
    league_averages: np.ndarray
    team_defense: np.ndarray
    opponent_defense: np.ndarray


@dataclass(frozen=True)
class Prediction:
    example: BacktestExample
    predicted_home: float
    predicted_away: float


@dataclass(frozen=True)
class Metrics:
    games: int
    score_mae: float
    score_rmse: float
    score_bias: float
    total_mae: float
    margin_mae: float
    winner_accuracy: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay completed NBA games using only earlier games, evaluate "
            "mc_sim, and optionally tune its adjustment weights."
        )
    )
    parser.add_argument("--season", default="2025-26")
    parser.add_argument(
        "--season-type",
        choices=sorted(SEASON_TYPES),
        default="playoffs",
    )
    parser.add_argument("--season-id", help="Override the derived NBA season id")
    parser.add_argument("--recent-games", type=int, default=20)
    parser.add_argument("--min-prior-games", type=int, default=5)
    parser.add_argument("--matchup-adjustment", type=float, default=1.0)
    parser.add_argument("--matchup-prior-games", type=float, default=5.0)
    parser.add_argument("--iterations", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--max-games", type=int)
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument(
        "--tune-trials",
        type=int,
        default=0,
        help="Number of random weight candidates; zero evaluates defaults only",
    )
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--tuning-iterations", type=int, default=750)
    parser.add_argument("--predictions-csv", type=Path)
    parser.add_argument("--weights-output", type=Path)
    return parser.parse_args()


def derive_season_id(season: str, season_type: str) -> str:
    try:
        start_year = int(season[:4])
    except (TypeError, ValueError):
        raise ValueError("season must look like 2025-26") from None
    return f"{SEASON_TYPES[season_type][1]}{start_year}"


def normalize_season_type(season_type: str) -> str:
    """Translate frontend season labels to the backtest's canonical keys."""
    normalized = " ".join(
        season_type.strip().lower().replace("_", " ").replace("-", " ").split()
    )
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
    try:
        return aliases[normalized]
    except KeyError:
        raise ValueError(f"Unsupported season type: {season_type}") from None


async def connect_from_env() -> asyncpg.Connection:
    load_dotenv()
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    return await asyncpg.connect(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )


def _to_float(value: object) -> float:
    return float(value) if value is not None else 0.0


def _stats_from_row(row: asyncpg.Record) -> np.ndarray:
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
        dtype=np.float64,
    )
    if values.shape != (STAT_COUNT,):
        raise ValueError("Historical stat row did not contain 20 model inputs")
    return values


async def load_games(
    connection: asyncpg.Connection,
    season_type: str,
    season_id: str,
) -> list[Game]:
    suffix = SEASON_TYPES[season_type][0]
    game_id_prefix = f"00{SEASON_TYPES[season_type][1]}"
    holder = f"nbawlholder{suffix}"
    advanced = f"nbateamadvancedstats{suffix}"
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

    team_rows: list[TeamRow] = []
    for row in rows:
        team_rows.append(
            TeamRow(
                game_id=row["game_id"],
                game_date=row["game_date"],
                team=row["team_abbreviation"],
                matchup=row["matchup"],
                stats=_stats_from_row(row),
                pace=_to_float(row["pace"]) if row["pace"] is not None else None,
            )
        )

    games: list[Game] = []
    for game_id, grouped in groupby(team_rows, key=lambda row: row.game_id):
        pair = list(grouped)
        if len(pair) != 2:
            continue
        home = next((row for row in pair if " vs. " in row.matchup), None)
        if home is None:
            continue
        away = pair[0] if pair[1] is home else pair[1]
        games.append(Game(game_id, home.game_date, home, away))
    games.sort(key=lambda game: (game.game_date, game.game_id))
    return games


def _mean_stats(records: Sequence[HistoryRecord]) -> np.ndarray:
    return np.mean(np.stack([record.stats for record in records]), axis=0)


def _recompute_percentages(stats: np.ndarray) -> np.ndarray:
    result = np.array(stats, dtype=np.float64, copy=True)
    result[3] = result[1] / result[2] if result[2] > 0.0 else 0.0
    result[6] = result[4] / result[5] if result[5] > 0.0 else 0.0
    result[9] = result[7] / result[8] if result[8] > 0.0 else 0.0
    for index in range(STAT_COUNT - 1):
        result[index] = max(0.0, result[index])
    return result


def build_team_input(
    history: Sequence[HistoryRecord],
    opponent: str,
    recent_games: int,
    matchup_adjustment: float,
    matchup_prior_games: float,
) -> np.ndarray:
    recent = history[-recent_games:]
    base = _mean_stats(recent)
    matchup_records = [record for record in history if record.opponent == opponent]
    if matchup_records and matchup_adjustment:
        matchup_records = matchup_records[-recent_games:]
        matchup_mean = _mean_stats(matchup_records)
        shrinkage = len(matchup_records) / (
            len(matchup_records) + max(0.0, matchup_prior_games)
        )
        base = base + matchup_adjustment * shrinkage * (matchup_mean - base)
    return _recompute_percentages(base)


def league_averages(history: Sequence[HistoryRecord]) -> np.ndarray:
    stats = np.sum(np.stack([record.stats for record in history]), axis=0)
    opponent_stats = np.sum(
        np.stack([record.opponent_stats for record in history]), axis=0
    )
    action_total = stats[2] + 0.44 * stats[8] + stats[16]
    rebound_chances = stats[10] + opponent_stats[11]
    return np.array(
        [
            stats[1] / stats[2] if stats[2] else 0.471,
            stats[4] / stats[5] if stats[5] else 0.360,
            stats[7] / stats[8] if stats[8] else 0.783,
            stats[16] / action_total if action_total else 0.127,
            stats[10] / rebound_chances if rebound_chances else 0.305,
        ],
        dtype=np.float64,
    )


def defensive_four_factors(
    history: Sequence[HistoryRecord], recent_games: int
) -> np.ndarray:
    recent = history[-recent_games:]
    own = np.sum(np.stack([record.stats for record in recent]), axis=0)
    opponent = np.sum(
        np.stack([record.opponent_stats for record in recent]), axis=0
    )
    opponent_actions = opponent[2] + 0.44 * opponent[8] + opponent[16]
    defensive_rebound_chances = own[11] + opponent[10]
    return np.array(
        [
            (opponent[1] + 0.5 * opponent[4]) / opponent[2]
            if opponent[2]
            else 0.545,
            opponent[16] / opponent_actions if opponent_actions else 0.127,
            opponent[8] / opponent[2] if opponent[2] else 0.250,
            own[11] / defensive_rebound_chances
            if defensive_rebound_chances
            else 0.695,
        ],
        dtype=np.float64,
    )


def expected_pace(
    home_history: Sequence[HistoryRecord],
    away_history: Sequence[HistoryRecord],
    recent_games: int,
) -> float:
    paces = [
        record.pace
        for record in list(home_history[-recent_games:])
        + list(away_history[-recent_games:])
        if record.pace is not None and record.pace > 0.0
    ]
    if paces:
        return float(np.mean(paces))
    stats = _mean_stats(home_history[-recent_games:])
    return max(1.0, stats[2] + 0.44 * stats[8] + stats[16] - stats[10])


def build_matchup_team_inputs(
    games: Sequence[Game],
    team: str,
    opponent: str,
    recent_games: int,
    min_prior_games: int = API_MIN_PRIOR_GAMES,
    matchup_adjustment: float = 1.0,
    matchup_prior_games: float = 5.0,
) -> MatchupTeamInputs:
    histories: dict[str, list[HistoryRecord]] = defaultdict(list)
    all_history: list[HistoryRecord] = []

    for game in games:
        home_record = HistoryRecord(
            game.away.team, game.home.stats, game.away.stats, game.home.pace
        )
        away_record = HistoryRecord(
            game.home.team, game.away.stats, game.home.stats, game.away.pace
        )
        histories[game.home.team].append(home_record)
        histories[game.away.team].append(away_record)
        all_history.extend((home_record, away_record))

    team_history = histories[team]
    opponent_history = histories[opponent]
    if (
        len(team_history) < min_prior_games
        or len(opponent_history) < min_prior_games
        or not all_history
    ):
        raise ValueError("Not enough completed games for team aggregation")

    return MatchupTeamInputs(
        team_stats=build_team_input(
            team_history,
            opponent,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        opponent_stats=build_team_input(
            opponent_history,
            team,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        pace=expected_pace(team_history, opponent_history, recent_games),
        league_averages=league_averages(all_history),
        team_defense=defensive_four_factors(team_history, recent_games),
        opponent_defense=defensive_four_factors(opponent_history, recent_games),
    )


async def calculate_matchup_team_inputs(
    connection: asyncpg.Connection,
    season: str,
    season_type: str,
    team: str,
    opponent: str,
    recent_games: int = 20,
) -> MatchupTeamInputs:
    canonical_season_type = normalize_season_type(season_type)
    season_id = derive_season_id(season, canonical_season_type)
    games = await load_games(connection, canonical_season_type, season_id)
    return build_matchup_team_inputs(
        games,
        team,
        opponent,
        recent_games,
    )


def build_examples(
    games: Sequence[Game],
    recent_games: int,
    min_prior_games: int,
    matchup_adjustment: float,
    matchup_prior_games: float,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[BacktestExample]:
    histories: dict[str, list[HistoryRecord]] = defaultdict(list)
    all_history: list[HistoryRecord] = []
    examples: list[BacktestExample] = []

    for game_date, date_games_iter in groupby(games, key=lambda game: game.game_date):
        date_games = list(date_games_iter)
        for game in date_games:
            home_history = histories[game.home.team]
            away_history = histories[game.away.team]
            in_date_range = (
                (start_date is None or game_date >= start_date)
                and (end_date is None or game_date <= end_date)
            )
            if (
                in_date_range
                and len(home_history) >= min_prior_games
                and len(away_history) >= min_prior_games
                and all_history
            ):
                examples.append(
                    BacktestExample(
                        game_id=game.game_id,
                        game_date=game.game_date,
                        home_team=game.home.team,
                        away_team=game.away.team,
                        home_stats=build_team_input(
                            home_history,
                            game.away.team,
                            recent_games,
                            matchup_adjustment,
                            matchup_prior_games,
                        ),
                        away_stats=build_team_input(
                            away_history,
                            game.home.team,
                            recent_games,
                            matchup_adjustment,
                            matchup_prior_games,
                        ),
                        pace=expected_pace(
                            home_history, away_history, recent_games
                        ),
                        league_averages=league_averages(all_history),
                        home_defense=defensive_four_factors(
                            home_history, recent_games
                        ),
                        away_defense=defensive_four_factors(
                            away_history, recent_games
                        ),
                        actual_home=game.home.stats[18],
                        actual_away=game.away.stats[18],
                    )
                )

        # Update after all games on the date so same-day finals cannot leak.
        for game in date_games:
            home_record = HistoryRecord(
                game.away.team, game.home.stats, game.away.stats, game.home.pace
            )
            away_record = HistoryRecord(
                game.home.team, game.away.stats, game.home.stats, game.away.pace
            )
            histories[game.home.team].append(home_record)
            histories[game.away.team].append(away_record)
            all_history.extend((home_record, away_record))
    return examples


def predict_examples(
    examples: Sequence[BacktestExample],
    weights: Sequence[float],
    iterations: int,
    seed: int,
) -> list[Prediction]:
    predictions: list[Prediction] = []
    for index, example in enumerate(examples):
        game_seed = seed + index * 2 + 1
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
        predicted_away = mc_sim.run_monte_carlo_simulation(
            example.away_stats,
            example.home_stats,
            example.pace,
            example.league_averages,
            example.home_defense,
            iterations,
            weights,
            game_seed + 1,
        )
        predictions.append(Prediction(example, predicted_home, predicted_away))
    return predictions


def calculate_metrics(predictions: Sequence[Prediction]) -> Metrics:
    if not predictions:
        raise ValueError("No predictions to score")
    errors: list[float] = []
    signed_errors: list[float] = []
    squared_errors: list[float] = []
    total_errors: list[float] = []
    margin_errors: list[float] = []
    winner_hits: list[float] = []
    for prediction in predictions:
        example = prediction.example
        for predicted, actual in (
            (prediction.predicted_home, example.actual_home),
            (prediction.predicted_away, example.actual_away),
        ):
            difference = predicted - actual
            errors.append(abs(difference))
            signed_errors.append(difference)
            squared_errors.append(difference * difference)
        total_errors.append(
            abs(
                prediction.predicted_home
                + prediction.predicted_away
                - example.actual_home
                - example.actual_away
            )
        )
        predicted_margin = prediction.predicted_home - prediction.predicted_away
        actual_margin = example.actual_home - example.actual_away
        margin_errors.append(abs(predicted_margin - actual_margin))
        if actual_margin != 0.0:
            winner_hits.append(float((predicted_margin > 0.0) == (actual_margin > 0.0)))
    return Metrics(
        games=len(predictions),
        score_mae=float(np.mean(errors)),
        score_rmse=math.sqrt(float(np.mean(squared_errors))),
        score_bias=float(np.mean(signed_errors)),
        total_mae=float(np.mean(total_errors)),
        margin_mae=float(np.mean(margin_errors)),
        winner_accuracy=float(np.mean(winner_hits)) if winner_hits else math.nan,
    )


def candidate_weights(trials: int, seed: int) -> Iterable[tuple[float, ...]]:
    yield DEFAULT_WEIGHTS[:8]
    rng = random.Random(seed)
    for _ in range(trials):
        yield tuple(rng.uniform(low, high) for low, high in WEIGHT_RANGES)


def apply_score_calibration(
    predictions: Sequence[Prediction], scale: float, intercept: float
) -> list[Prediction]:
    return [
        Prediction(
            prediction.example,
            scale * prediction.predicted_home + intercept,
            scale * prediction.predicted_away + intercept,
        )
        for prediction in predictions
    ]


def fit_score_calibration(predictions: Sequence[Prediction]) -> tuple[float, float]:
    predicted = np.array(
        [
            score
            for prediction in predictions
            for score in (prediction.predicted_home, prediction.predicted_away)
        ],
        dtype=np.float64,
    )
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
    best_scale = 1.0
    best_intercept = float(np.median(actual - predicted))
    best_mae = math.inf
    for scale in np.linspace(0.75, 1.35, 121):
        intercept = float(np.median(actual - scale * predicted))
        intercept = min(30.0, max(-20.0, intercept))
        mae = float(np.mean(np.abs(scale * predicted + intercept - actual)))
        if mae < best_mae:
            best_scale = float(scale)
            best_intercept = intercept
            best_mae = mae
    return best_scale, best_intercept


def tune_model_weights(
    examples: Sequence[BacktestExample],
    trials: int = API_TUNE_TRIALS,
    iterations: int = API_TUNING_ITERATIONS,
    seed: int = API_WEIGHT_SEED,
) -> np.ndarray:
    """Choose the lowest-MAE weights for a set of completed-game examples."""
    if trials < 0:
        raise ValueError("trials cannot be negative")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not examples:
        return np.ascontiguousarray(DEFAULT_WEIGHTS, dtype=np.float64)

    best_weights = DEFAULT_WEIGHTS
    best_mae = math.inf
    for adjustment_weights in candidate_weights(trials, seed):
        raw_weights = tuple(adjustment_weights) + (1.0, 0.0)
        raw_predictions = predict_examples(examples, raw_weights, iterations, seed)
        scale, intercept = fit_score_calibration(raw_predictions)
        predictions = apply_score_calibration(raw_predictions, scale, intercept)
        score_mae = calculate_metrics(predictions).score_mae
        if score_mae < best_mae:
            best_mae = score_mae
            best_weights = tuple(adjustment_weights) + (scale, intercept)
    return np.ascontiguousarray(best_weights, dtype=np.float64)


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
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    canonical_season_type = normalize_season_type(season_type)
    season_id = derive_season_id(season, canonical_season_type)
    games = await load_games(connection, canonical_season_type, season_id)
    examples = build_examples(
        games,
        recent_games,
        min_prior_games,
        matchup_adjustment=1.0,
        matchup_prior_games=5.0,
    )
    examples = examples[-API_MAX_GAMES:]
    if len(examples) >= 10:
        split = max(
            1,
            min(len(examples) - 1, int(len(examples) * API_TRAIN_FRACTION)),
        )
        examples = examples[:split]

    # Monte Carlo tuning is CPU-bound. Keep it off the API event-loop thread.
    return await asyncio.to_thread(
        tune_model_weights,
        examples,
        tune_trials,
        tuning_iterations,
        seed,
    )


def print_metrics(label: str, metrics: Metrics) -> None:
    print(f"\n{label} ({metrics.games} games)")
    print(f"  Team score MAE:  {metrics.score_mae:6.2f}")
    print(f"  Team score RMSE: {metrics.score_rmse:6.2f}")
    print(f"  Score bias:      {metrics.score_bias:+6.2f}")
    print(f"  Game total MAE:  {metrics.total_mae:6.2f}")
    print(f"  Margin MAE:      {metrics.margin_mae:6.2f}")
    print(f"  Winner accuracy: {metrics.winner_accuracy:6.1%}")


def print_weights(weights: Sequence[float]) -> None:
    print("  Weights:")
    for name, value in zip(WEIGHT_NAMES, weights):
        print(f"    {name:22s} {value:.4f}")


def write_predictions(path: Path, predictions: Sequence[Prediction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
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
        for prediction in predictions:
            example = prediction.example
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


async def run(args: argparse.Namespace) -> None:
    if args.recent_games <= 0 or args.min_prior_games <= 0:
        raise ValueError("recent-games and min-prior-games must be positive")
    if args.iterations <= 0 or args.tuning_iterations <= 0:
        raise ValueError("iteration counts must be positive")
    if not 0.5 <= args.train_fraction < 1.0:
        raise ValueError("train-fraction must be at least 0.5 and below 1.0")

    season_id = args.season_id or derive_season_id(args.season, args.season_type)
    connection = await connect_from_env()
    try:
        games = await load_games(connection, args.season_type, season_id)
    finally:
        await connection.close()
    examples = build_examples(
        games,
        args.recent_games,
        args.min_prior_games,
        args.matchup_adjustment,
        args.matchup_prior_games,
        args.start_date,
        args.end_date,
    )
    if args.max_games is not None:
        examples = examples[-args.max_games :]
    if not examples:
        raise RuntimeError("No eligible games; lower min-prior-games or check the season")

    print(
        f"Loaded {len(games)} completed games for {args.season} "
        f"{args.season_type}; {len(examples)} are eligible."
    )
    print(
        "All rolling stats, pace, league averages, and defensive factors "
        "exclude the predicted game and every later game."
    )

    final_weights = DEFAULT_WEIGHTS
    final_examples = examples
    if args.tune_trials > 0:
        split = max(1, min(len(examples) - 1, int(len(examples) * args.train_fraction)))
        if len(examples) < 10:
            raise RuntimeError("At least 10 eligible games are required for tuning")
        training = examples[:split]
        holdout = examples[split:]
        print(
            f"Tuning {args.tune_trials + 1} candidates on {len(training)} "
            f"earlier games; {len(holdout)} later games remain untouched."
        )
        final_weights = tune_model_weights(
            training,
            args.tune_trials,
            args.tuning_iterations,
            args.seed,
        )
        best_metrics = calculate_metrics(
            predict_examples(
                training,
                final_weights,
                args.tuning_iterations,
                args.seed,
            )
        )
        print_metrics("Best training result", best_metrics)
        print_weights(final_weights)

        baseline_holdout = predict_examples(
            holdout, DEFAULT_WEIGHTS, args.iterations, args.seed + 1_000_000
        )
        print_metrics("Default weights - chronological holdout", calculate_metrics(baseline_holdout))
        final_examples = holdout

    final_predictions = predict_examples(
        final_examples, final_weights, args.iterations, args.seed + 2_000_000
    )
    label = (
        "Tuned weights - chronological holdout"
        if args.tune_trials > 0
        else "Default weights - full backtest"
    )
    print_metrics(label, calculate_metrics(final_predictions))
    if args.tune_trials > 0:
        print_weights(final_weights)

    if args.predictions_csv:
        write_predictions(args.predictions_csv, final_predictions)
        print(f"\nWrote predictions to {args.predictions_csv}")
    if args.weights_output:
        args.weights_output.parent.mkdir(parents=True, exist_ok=True)
        args.weights_output.write_text(
            json.dumps(dict(zip(WEIGHT_NAMES, final_weights)), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote weights to {args.weights_output}")


def main() -> None:
    try:
        asyncio.run(run(parse_args()))
    except (RuntimeError, ValueError, asyncpg.PostgresError) as error:
        raise SystemExit(f"backtest failed: {error}") from error


if __name__ == "__main__":
    main()
