# backtest_api.pyx

# Function: Build low-latency matchup inputs, tune model weights, and cache
# complete historical snapshots for API requests.

# Inputs: Completed games, season identifiers, matchup teams, history-window
# settings, and model-tuning parameters.

# Output: MatchupTeamInputs objects and validated model-weight arrays.

"""Low-latency API entry points for matchup inputs and weight tuning."""

# Compile hot loops without Python index and None checks.
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True
# cython: initializedcheck=False

# Libraries

import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from datetime import date, datetime

import numpy as np
cimport numpy as cnp
from cython.parallel cimport prange

# Initialize NumPy's C API before any typed arrays are used.
cnp.import_array()

# Every model input vector contains exactly 20 team statistics.
cdef int STAT_COUNT = 20

# Weight tuning depends on the season snapshot, not the requested matchup.
# Cache completed results and share an in-flight task so concurrent requests
# never tune the same snapshot more than once.
# Store completed tuned weights by their full season-and-snapshot key.
_model_weights_cache = {}
# Store in-progress tuning tasks so concurrent requests await the same work.
_model_weight_tasks = {}
# Store loaded games and their fingerprints by canonical season key.
_games_cache = {}
# Store in-progress database loads so concurrent requests share one query.
_games_load_tasks = {}
# Increment this version whenever the persisted weight format becomes invalid.
MODEL_WEIGHTS_VERSION = 3
# Persist weights in a JSON file next to the compiled extension.
MODEL_WEIGHTS_PATH = Path(__file__).with_name("model_weights.json")


# Read and validate the top-level structure of persisted model weights.
def _read_saved_model_weights():
    # Treat missing, malformed, or outdated persistence as an empty cache.
    try:
        # Parse the complete JSON document from the configured path.
        saved = json.loads(MODEL_WEIGHTS_PATH.read_text())
        # Accept only the current version with a mapping of season entries.
        if saved["version"] == MODEL_WEIGHTS_VERSION and isinstance(saved["seasons"], dict):
            # Return the season mapping without its file-format wrapper.
            return saved["seasons"]
    # Ignore filesystem, JSON, shape, and type failures so requests can retune.
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # An empty mapping signals that no reusable saved entry exists.
    return {}


# Load persistence once when the extension module is imported.
_saved_model_weights = _read_saved_model_weights()


# Hash all model-relevant values in a completed-games snapshot.
def _games_fingerprint(games):
    # Create a fresh SHA-256 digest for this ordered snapshot.
    digest = hashlib.sha256()
    # Incorporate each game's identity, context, pace, and stat bytes.
    for game in games:
        # Normalize non-array metadata into a deterministic JSON tuple.
        metadata = (game.game_id, str(game.game_date), game.home.team,
                    game.away.team, game.home.pace, game.away.pace)
        # Use compact JSON separators so formatting never changes the digest.
        digest.update(json.dumps(metadata, separators=(",", ":")).encode())
        # Include every home statistic in its exact float representation.
        digest.update(game.home.stats.tobytes())
        # Include every away statistic in its exact float representation.
        digest.update(game.away.stats.tobytes())
    # Return a portable hexadecimal identity for cache and persistence keys.
    return digest.hexdigest()


# Extract every tuning setting that determines a saved weight vector.
def _weight_settings(cache_key):
    # Import lazily to avoid circular imports during extension initialization.
    import backtest_mc_sim as backtest
    # Combine request settings with backtest constants that affect fitting.
    return list(cache_key[2:7]) + [backtest.API_MAX_GAMES,
                                 backtest.API_TRAIN_FRACTION,
                                 len(backtest.DEFAULT_WEIGHTS)]


# Build a compact persistence key for one season, configuration, and snapshot.
def _saved_weights_key(cache_key):
    """Keep separate weights for each history window and as-of snapshot."""
    # Serialize tuning settings and the games fingerprint deterministically.
    identity = json.dumps([_weight_settings(cache_key), cache_key[7]],
                          separators=(",", ":")).encode()
    # Prefix the identity hash with readable canonical season information.
    return ":".join(cache_key[:2]) + ":" + hashlib.sha256(identity).hexdigest()


# Restore one saved vector only when its snapshot, settings, shape, and values match.
def _saved_weights(cache_key):
    # Import defaults lazily for expected-vector-length validation.
    import backtest_mc_sim as backtest
    # Resolve the candidate entry, using an empty mapping when absent.
    saved = _saved_model_weights.get(_saved_weights_key(cache_key), {})
    # Any malformed entry is equivalent to a cache miss.
    try:
        # Require both the exact source snapshot and every fitting setting.
        if saved["snapshot"] == cache_key[7] and saved["settings"] == _weight_settings(cache_key):
            # Convert JSON numbers into the contiguous doubles required by Cython.
            weights = np.ascontiguousarray(saved["weights"], dtype=np.float64)
            # Reject wrong-length vectors and non-finite model coefficients.
            if (weights.shape == (len(backtest.DEFAULT_WEIGHTS),)
                    and np.isfinite(weights).all()):
                # Return the fully validated persisted vector.
                return weights
    # Invalid JSON-derived shapes or fields must trigger safe retuning.
    except (ValueError, KeyError, TypeError):
        pass
    # None clearly distinguishes a miss from a valid NumPy array.
    return None


# Persist one validated weight vector through an atomic temporary-file replace.
def _save_model_weights(cache_key, weights):
    # Import expected defaults lazily to avoid module-import cycles.
    import backtest_mc_sim as backtest
    # Normalize caller data into a contiguous double-precision vector.
    weights = np.ascontiguousarray(weights, dtype=np.float64)
    # Never persist arrays that the prediction API cannot safely consume.
    if (weights.shape != (len(backtest.DEFAULT_WEIGHTS),)
            or not np.isfinite(weights).all()):
        return
    # Update the in-memory persistence representation before writing it.
    _saved_model_weights[_saved_weights_key(cache_key)] = {
        # Retain source identity and settings so future loads can revalidate them.
        "snapshot": cache_key[7], "settings": _weight_settings(cache_key),
        # Convert NumPy scalars into JSON-serializable Python numbers.
        "weights": weights.tolist(),
    }
    # Track the temporary path so cleanup works after partial failures.
    temporary = None
    # A failed write must not interrupt live prediction requests.
    try:
        # Create the temporary file in the destination directory for atomic rename.
        with tempfile.NamedTemporaryFile(
            mode="w", dir=MODEL_WEIGHTS_PATH.parent,
            prefix=".model_weights-", delete=False,
        ) as output:
            # Preserve the generated path after the file handle closes.
            temporary = Path(output.name)
            # Serialize the versioned cache deterministically and reject NaN values.
            json.dump({"version": MODEL_WEIGHTS_VERSION,
                       "seasons": _saved_model_weights}, output,
                      indent=2, sort_keys=True, allow_nan=False)
            # End the file with a conventional newline for readable diffs.
            output.write("\n")
        # Atomically publish the complete file over any previous version.
        temporary.replace(MODEL_WEIGHTS_PATH)
    # Read-only deployments may predict successfully without disk persistence.
    except OSError:
        pass  # Predictions still work when the checkout is read-only.
    # Remove a leftover temporary file after either success or failure.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

# Full-season warmup default; requests tune and cache their own history window.
# Use the largest platform index so slicing naturally includes every game.
MODEL_WEIGHT_RECENT_GAMES = sys.maxsize


# Sum one statistic column across every supplied row without acquiring the GIL.
cdef double _sum_column(
    double[:, ::1] rows, Py_ssize_t column
) noexcept nogil:
    # Declare the row index as a native C-sized integer.
    cdef Py_ssize_t i
    # Accumulate in double precision from a zero identity.
    cdef double total = 0.0
    # Visit each historical row for the requested statistic.
    for i in range(rows.shape[0]):
        # Add the typed-memory-view value without Python-object overhead.
        total = total + rows[i, column]
    # Return the completed native sum to the caller.
    return total


# Calculate the arithmetic mean of each model-stat column.
cdef cnp.ndarray[cnp.float64_t, ndim=1] _mean_rows(
    double[:, ::1] rows,
):
    # Cache the divisor before entering native parallel loops.
    cdef Py_ssize_t row_count = rows.shape[0]
    # Declare the column index in native storage.
    cdef Py_ssize_t j
    # Allocate the fixed-width result as an uninitialized NumPy vector.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = np.empty(
        STAT_COUNT, dtype=np.float64
    )
    # Expose the result through a contiguous typed memory view.
    cdef double[::1] output = result

    # Release the GIL while independent statistic columns are aggregated.
    with nogil:
        # Parallelize only when the row-column workload justifies thread overhead.
        for j in prange(
            STAT_COUNT,
            schedule="static",
            use_threads_if=row_count * STAT_COUNT >= 4096,
        ):
            # Divide each column total by the common row count.
            output[j] = _sum_column(rows, j) / row_count
    # Return the NumPy owner of the populated memory view.
    return result


# Calculate the total of each model-stat column.
cdef cnp.ndarray[cnp.float64_t, ndim=1] _sum_rows(
    double[:, ::1] rows,
):
    # Cache row count for the OpenMP activation threshold.
    cdef Py_ssize_t row_count = rows.shape[0]
    # Declare the native loop index for statistic columns.
    cdef Py_ssize_t j
    # Allocate one double value for every model statistic.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = np.empty(
        STAT_COUNT, dtype=np.float64
    )
    # Expose contiguous output storage to the no-GIL loop.
    cdef double[::1] output = result

    # Perform column sums without Python interpreter overhead.
    with nogil:
        # Use static scheduling because every column processes equal row counts.
        for j in prange(
            STAT_COUNT,
            schedule="static",
            use_threads_if=row_count * STAT_COUNT >= 4096,
        ):
            # Store each independent column total in its output slot.
            output[j] = _sum_column(rows, j)
    # Return the fully populated NumPy vector.
    return result


# Recalculate rate fields from component counts and clamp negative raw stats.
cdef void _recompute_percentages(double[::1] stats) noexcept nogil:
    # Declare the native index used by the nonnegative-value pass.
    cdef Py_ssize_t i
    # Recompute overall field-goal percentage from made and attempted shots.
    stats[3] = stats[1] / stats[2] if stats[2] > 0.0 else 0.0
    # Recompute three-point percentage from its component counts.
    stats[6] = stats[4] / stats[5] if stats[5] > 0.0 else 0.0
    # Recompute free-throw percentage from its component counts.
    stats[9] = stats[7] / stats[8] if stats[8] > 0.0 else 0.0
    # Clamp all fields except signed plus-minus to physically valid values.
    for i in range(STAT_COUNT - 1):
        if stats[i] < 0.0:
            stats[i] = 0.0


# Blend recent overall form with a shrunken head-to-head adjustment.
cdef cnp.ndarray[cnp.float64_t, ndim=1] _team_input(
    double[:, ::1] history,
    double[:, ::1] matchup,
    Py_ssize_t recent_games,
    double matchup_adjustment,
    double matchup_prior_games,
):
    # Select the start of the requested window without crossing array bounds.
    cdef Py_ssize_t history_start = max(0, history.shape[0] - recent_games)
    # Independently select the corresponding head-to-head window.
    cdef Py_ssize_t matchup_start = max(0, matchup.shape[0] - recent_games)
    # Use recent overall history as the baseline team vector.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = _mean_rows(
        history[history_start:]
    )
    # Reserve storage for the optional head-to-head average.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] matchup_mean
    # Expose the baseline result for in-place native updates.
    cdef double[::1] output = result
    # Hold a typed view of the head-to-head mean when one exists.
    cdef double[::1] matched
    # Store the sample-size shrinkage applied to matchup differences.
    cdef double shrinkage
    # Declare the native statistic index.
    cdef Py_ssize_t j

    # Skip adjustment when no matchup history exists or its weight is disabled.
    if matchup.shape[0] and matchup_adjustment != 0.0:
        # Average only the requested number of recent head-to-head games.
        matchup_mean = _mean_rows(matchup[matchup_start:])
        # Expose the matchup average through a contiguous memory view.
        matched = matchup_mean
        # Count the records that actually contributed to the matchup mean.
        shrinkage = matchup.shape[0] - matchup_start
        # Pull small samples toward the overall baseline using the prior size.
        shrinkage /= shrinkage + max(0.0, matchup_prior_games)
        # Update independent statistic columns without holding the GIL.
        with nogil:
            for j in range(STAT_COUNT):
                # Add the weighted difference between matchup and overall form.
                output[j] += (
                    matchup_adjustment * shrinkage * (matched[j] - output[j])
                )
    # Restore percentage consistency after blending count-based fields.
    with nogil:
        _recompute_percentages(output)
    # Return the adjusted 20-stat vector.
    return result


# Calculate league shooting, turnover, and rebound baselines from totals.
cdef cnp.ndarray[cnp.float64_t, ndim=1] _league_averages(
    double[:, ::1] stats_rows,
    double[:, ::1] opponent_rows,
):
    # Sum every team's own box-score statistics.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] stats_array = _sum_rows(stats_rows)
    # Sum the corresponding opponent box-score statistics.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_array = _sum_rows(
        opponent_rows
    )
    # Expose both totals as efficient typed memory views.
    cdef double[::1] stats = stats_array
    cdef double[::1] opponent = opponent_array
    # Approximate total offensive actions for turnover-rate calculation.
    cdef double action_total = stats[2] + 0.44 * stats[8] + stats[16]
    # Combine offensive and opposing defensive rebounds into rebound chances.
    cdef double rebound_chances = stats[10] + opponent[11]
    # Return model baselines with league-like fallbacks for empty denominators.
    return np.array(
        [
            # Overall field-goal percentage.
            stats[1] / stats[2] if stats[2] else 0.471,
            # Three-point percentage.
            stats[4] / stats[5] if stats[5] else 0.360,
            # Free-throw percentage.
            stats[7] / stats[8] if stats[8] else 0.783,
            # Turnovers per estimated offensive action.
            stats[16] / action_total if action_total else 0.127,
            # Offensive rebounds per available rebound chance.
            stats[10] / rebound_chances if rebound_chances else 0.305,
        ],
        # Keep output compatible with Cython double memory views.
        dtype=np.float64,
    )


# Derive recent opponent-facing defensive four factors for one team.
cdef cnp.ndarray[cnp.float64_t, ndim=1] _defensive_factors(
    double[:, ::1] own_rows,
    double[:, ::1] opponent_rows,
    Py_ssize_t recent_games,
):
    # Restrict both own and opponent totals to the configured recent window.
    cdef Py_ssize_t start = max(0, own_rows.shape[0] - recent_games)
    # Sum the team's recent box-score values.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] own_array = _sum_rows(
        own_rows[start:]
    )
    # Sum what opponents produced in those same games.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_array = _sum_rows(
        opponent_rows[start:]
    )
    # Expose totals through typed views for scalar factor calculations.
    cdef double[::1] own = own_array
    cdef double[::1] opponent = opponent_array
    # Estimate opponent actions for the forced-turnover denominator.
    cdef double actions = opponent[2] + 0.44 * opponent[8] + opponent[16]
    # Combine own defensive and opponent offensive rebounds into chances.
    cdef double rebound_chances = own[11] + opponent[10]
    # Return effective shooting, turnovers, free throws, and defensive rebounding.
    return np.array(
        [
            # Opponent effective field-goal percentage allowed.
            (opponent[1] + 0.5 * opponent[4]) / opponent[2]
            if opponent[2]
            else 0.545,
            # Opponent turnover rate forced by this defense.
            opponent[16] / actions if actions else 0.127,
            # Opponent free-throw attempts per field-goal attempt.
            opponent[8] / opponent[2] if opponent[2] else 0.250,
            # Share of available defensive rebounds secured by this team.
            own[11] / rebound_chances if rebound_chances else 0.695,
        ],
        # Preserve the double-precision format expected by the simulator.
        dtype=np.float64,
    )


# Estimate matchup pace from both teams' recent pace values or box-score actions.
cdef double _expected_pace(
    double[::1] team_paces,
    double[::1] opponent_paces,
    double[:, ::1] team_rows,
    Py_ssize_t recent_games,
) noexcept nogil:
    # Declare the native loop index used for both teams' histories.
    cdef Py_ssize_t i
    # Select the requested recent slice of the first team's pace history.
    cdef Py_ssize_t team_start = max(0, team_paces.shape[0] - recent_games)
    # Select the requested recent slice of the opponent's pace history.
    cdef Py_ssize_t opponent_start = max(
        0, opponent_paces.shape[0] - recent_games
    )
    # Accumulate only known positive pace observations.
    cdef double total = 0.0
    # Track the valid-value count for a combined arithmetic mean.
    cdef Py_ssize_t count = 0
    # Reserve a fallback estimate based on offensive possessions.
    cdef double possessions = 0.0

    # Add valid recent pace values from the requested team.
    for i in range(team_start, team_paces.shape[0]):
        if team_paces[i] > 0.0:
            total += team_paces[i]
            count += 1
    # Add valid recent pace values from the opponent.
    for i in range(opponent_start, opponent_paces.shape[0]):
        if opponent_paces[i] > 0.0:
            total += opponent_paces[i]
            count += 1
    # Prefer the observed two-team pace mean when at least one value exists.
    if count:
        return total / count

    # Estimate possessions from recent team box scores when pace is unavailable.
    for i in range(max(0, team_rows.shape[0] - recent_games), team_rows.shape[0]):
        possessions += (
            team_rows[i, 2]
            + 0.44 * team_rows[i, 8]
            + team_rows[i, 16]
            - team_rows[i, 10]
        )
    # Average by the number of team rows included in the fallback window.
    possessions /= min(team_rows.shape[0], recent_games)
    # Never return a nonpositive pace to the simulator.
    return max(1.0, possessions)


# Aggregate one completed season snapshot into all inputs for a future matchup.
def build_matchup_team_inputs(
    games,
    str team,
    str opponent,
    Py_ssize_t recent_games,
    int min_prior_games=1,
    double matchup_adjustment=1.0,
    double matchup_prior_games=5.0,
):
    """Build matchup arrays using OpenMP-backed C aggregation loops."""
    # Collect the requested team's own historical stat rows.
    cdef list team_stats = []
    # Collect opponents' stats from each requested-team game.
    cdef list team_opponent_stats = []
    # Collect recorded pace values from the requested team's games.
    cdef list team_paces = []
    # Collect requested-team rows specifically against this opponent.
    cdef list team_matchup = []
    # Collect the opponent's own historical stat rows.
    cdef list opponent_stats = []
    # Collect opposing stats from each opponent game.
    cdef list opponent_opponent_stats = []
    # Collect recorded pace values from the opponent's games.
    cdef list opponent_paces = []
    # Collect opponent rows specifically against the requested team.
    cdef list opponent_matchup = []
    # Collect all team rows for league-average calculation.
    cdef list all_stats = []
    # Collect the opposing side of every league row.
    cdef list all_opponent_stats = []
    # Reuse object references while iterating games from both perspectives.
    cdef object game, row, other
    # Reserve typed arrays for requested-team history.
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_opponent_array
    # Reserve typed arrays for opponent history.
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_opponent_array
    # Reserve typed arrays for league-wide totals.
    cdef cnp.ndarray[cnp.float64_t, ndim=2] all_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] all_opponent_array
    # Reserve typed arrays for head-to-head histories.
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_matchup_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_matchup_array
    # Reserve contiguous pace arrays for native averaging.
    cdef cnp.ndarray[cnp.float64_t, ndim=1] team_pace_array
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_pace_array
    # Store the final expected matchup pace.
    cdef double pace

    # Reject invalid windows before any slicing or division occurs.
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    # Walk every completed game from both teams' perspectives.
    for game in games:
        for row, other in ((game.home, game.away), (game.away, game.home)):
            # Every perspective contributes to league own/opponent totals.
            all_stats.append(row.stats)
            all_opponent_stats.append(other.stats)
            # Route requested-team history into its specialized collections.
            if row.team == team:
                team_stats.append(row.stats)
                team_opponent_stats.append(other.stats)
                # Represent missing pace as zero so native code can skip it.
                team_paces.append(row.pace if row.pace is not None else 0.0)
                # Preserve head-to-head rows for the matchup-specific adjustment.
                if other.team == opponent:
                    team_matchup.append(row.stats)
            # Route opponent history into the mirrored collections.
            elif row.team == opponent:
                opponent_stats.append(row.stats)
                opponent_opponent_stats.append(other.stats)
                # Normalize missing opponent pace to the same zero sentinel.
                opponent_paces.append(row.pace if row.pace is not None else 0.0)
                # Preserve the opponent's head-to-head rows against this team.
                if other.team == team:
                    opponent_matchup.append(row.stats)
    # Match the calling API's established insufficient-history sentinel.
    error_code = 2
    # Require minimum histories for both teams plus nonempty league context.
    if (
        len(team_stats) < min_prior_games
        or len(opponent_stats) < min_prior_games
        or not all_stats
    ):
        return error_code

    # Convert Python lists into contiguous doubles for Cython aggregation.
    team_array = np.ascontiguousarray(team_stats, dtype=np.float64)
    # Keep opponent results aligned with the requested team's rows.
    team_opponent_array = np.ascontiguousarray(
        team_opponent_stats, dtype=np.float64
    )
    # Convert the selected opponent's own history.
    opponent_array = np.ascontiguousarray(opponent_stats, dtype=np.float64)
    # Convert the opponents faced in that history.
    opponent_opponent_array = np.ascontiguousarray(
        opponent_opponent_stats, dtype=np.float64
    )
    # Convert every league perspective for shared rate baselines.
    all_array = np.ascontiguousarray(all_stats, dtype=np.float64)
    # Convert the matching opponent perspective for rebound baselines.
    all_opponent_array = np.ascontiguousarray(
        all_opponent_stats, dtype=np.float64
    )
    # Preserve a two-dimensional shape even when no head-to-head rows exist.
    if team_matchup:
        team_matchup_array = np.ascontiguousarray(team_matchup, dtype=np.float64)
    else:
        team_matchup_array = np.empty((0, STAT_COUNT), dtype=np.float64)
    # Mirror the empty-shape guarantee for the selected opponent.
    if opponent_matchup:
        opponent_matchup_array = np.ascontiguousarray(opponent_matchup, dtype=np.float64)
    else:
        opponent_matchup_array = np.empty((0, STAT_COUNT), dtype=np.float64)    
    # Convert both pace histories into native one-dimensional arrays.
    team_pace_array = np.ascontiguousarray(team_paces, dtype=np.float64)
    opponent_pace_array = np.ascontiguousarray(opponent_paces, dtype=np.float64)

    # Combine both recent pace histories with a box-score fallback.
    pace = _expected_pace(
        team_pace_array,
        opponent_pace_array,
        team_array,
        recent_games,
    )

    # Import the result dataclass lazily to avoid extension import cycles.
    import backtest_mc_sim as backtest
    # Package all model features into the shared public result type.
    return backtest.MatchupTeamInputs(
        # Blend the requested team's recent and head-to-head performance.
        team_stats=_team_input(
            team_array,
            team_matchup_array,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        # Build the opponent vector through the same symmetric calculation.
        opponent_stats=_team_input(
            opponent_array,
            opponent_matchup_array,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        # Supply the scalar two-team expected pace.
        pace=pace,
        # Supply league rates calculated from every historical team row.
        league_averages=_league_averages(all_array, all_opponent_array),
        # Supply recent defensive factors for the requested team.
        team_defense=_defensive_factors(
            team_array, team_opponent_array, recent_games
        ),
        # Supply recent defensive factors for the selected opponent.
        opponent_defense=_defensive_factors(
            opponent_array, opponent_opponent_array, recent_games
        ),
    )


# Find the newest player-stat season containing rows for both matchup teams.
async def _latest_matchup_season_id(
    connection,
    object backtest,
    str canonical_season_type,
    str team,
    str opponent,
):
    # Resolve the player-stat table used by the matching season phase.
    suffix = backtest.SEASON_TYPES[canonical_season_type][0]
    table = f"nbaplayerstats{suffix}"
    # Match the player-stat query's latest-common-season selection exactly.
    season_id = await connection.fetchval(
        f"""
        SELECT season_id
        FROM {table}
        WHERE matchup LIKE $1 OR matchup LIKE $2
        GROUP BY season_id
        HAVING COUNT(*) FILTER (WHERE matchup LIKE $1) > 0
           AND COUNT(*) FILTER (WHERE matchup LIKE $2) > 0
        ORDER BY MAX(game_date) DESC
        LIMIT 1
        """,
        team + "%",
        opponent + "%",
    )
    # Preserve None so callers can return the established no-data sentinel.
    return str(season_id) if season_id is not None else None


# Load one season through the shared cache and aggregate a requested matchup.
async def calculate_matchup_team_inputs(
    connection,
    str season,
    str season_type,
    str team,
    str opponent,
    Py_ssize_t recent_games=20,
):
    """Fetch a season asynchronously, then aggregate it in native code."""
    # Import normalization, id derivation, loading, and result types lazily.
    import backtest_mc_sim as backtest
    # Translate frontend season text into a canonical database key.
    canonical = backtest.normalize_season_type(season_type)
    # Preserve validation of the frontend season even though data may fall back.
    backtest.derive_season_id(season, canonical)
    # Use the same newest season shared by both teams as the player-stat query.
    season_id = await _latest_matchup_season_id(
        connection, backtest, canonical, team, opponent
    )
    # Match the established insufficient-history sentinel when no season exists.
    if season_id is None:
        return 2
    # Reuse a completed or in-flight load for this season snapshot.
    games = await _cached_games(connection, backtest, canonical, season_id)
    # Run the CPU-efficient native aggregation on the loaded games.
    return build_matchup_team_inputs(games, team, opponent, recent_games)


# Delegate tuning to the single chronological Python implementation.
def tune_model_weights_parallel(
    examples,
    int trials=25,
    int iterations=750,
    int seed=20260709,
):
    """Use the same chronological selection/refit objective as the backtest.

    The simulation itself still uses OpenMP. Keeping one tuning implementation
    prevents production from silently selecting a different model.
    """
    # Import the authoritative selection/refit implementation lazily.
    import backtest_mc_sim as backtest
    # Preserve all caller parameters while the underlying simulator uses OpenMP.
    return backtest.tune_model_weights(examples, trials, iterations, seed)


# Convert games into examples, cap history size, and tune one weight vector.
def _build_and_tune_model_weights(
    games,
    Py_ssize_t recent_games,
    int min_prior_games,
    int tune_trials,
    int tuning_iterations,
    int seed,
):
    # Import feature-building constants and helpers without a top-level cycle.
    import backtest_mc_sim as backtest
    # Validate tuning counts before building potentially expensive examples.
    if tune_trials < 0 or tuning_iterations <= 0:
        raise ValueError("trials cannot be negative and iterations must be positive")
    # Build leakage-free examples with the production matchup adjustment.
    examples = backtest.build_examples(
        games,
        recent_games,
        min_prior_games,
        matchup_adjustment=1.0,
        matchup_prior_games=5.0,
    )
    # Bound tuning cost to the newest configured number of eligible games.
    examples = examples[-backtest.API_MAX_GAMES:]
    # Select and refit model weights using the requested search parameters.
    return tune_model_weights_parallel(
        examples,
        tune_trials,
        tuning_iterations,
        seed,
    )


# Return cached weights or coordinate exactly one tuning task per snapshot key.
async def _cached_model_weights(
    games,
    str canonical_season_type,
    str season_id,
    Py_ssize_t recent_games,
    int min_prior_games,
    int tune_trials,
    int tuning_iterations,
    int seed,
):
    # Build the complete key from season, settings, and source-data fingerprint.
    cdef tuple cache_key = _model_weights_cache_key(
        games,
        canonical_season_type,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )
    # Check the fastest in-process completed-result cache first.
    cdef object cached = _model_weights_cache.get(cache_key)
    # Reserve a reference to a new or already running shared task.
    cdef object task
    # Reserve the completed weight vector returned by that task.
    cdef object weights
    # Return the exact completed object on an in-memory cache hit.
    if cached is not None:
        return cached
    # Fall back to a validated vector restored from JSON persistence.
    cached = _saved_weights(cache_key)
    if cached is not None:
        # Promote the restored vector into the faster in-memory cache.
        _model_weights_cache[cache_key] = cached
        return cached

    # Reuse any tuning task already created by a concurrent request.
    task = _model_weight_tasks.get(cache_key)
    # Create the off-loop tuning task only for the first cache miss.
    if task is None:
        # Wrap the worker coroutine so all requesters can await one Task.
        task = asyncio.create_task(
            # Move CPU-bound feature fitting and simulation off the event loop.
            asyncio.to_thread(
                _build_and_tune_model_weights,
                games,
                recent_games,
                min_prior_games,
                tune_trials,
                tuning_iterations,
                seed,
            )
        )
        # Publish the in-flight task before yielding to concurrent requests.
        _model_weight_tasks[cache_key] = task
    # Ensure task bookkeeping is cleaned after success, failure, or cancellation.
    try:
        # Await the shared tuning result.
        weights = await task
    finally:
        # Remove only this task, protecting a newer replacement from stale cleanup.
        if _model_weight_tasks.get(cache_key) is task:
            _model_weight_tasks.pop(cache_key, None)
    # Remove older fingerprints for the same season and tuning configuration.
    for old_key in list(_model_weights_cache):
        if old_key[:7] == cache_key[:7]:
            _model_weights_cache.pop(old_key, None)
    # Publish the newly completed vector for normal requests.
    _model_weights_cache[cache_key] = weights
    # Persist the validated result for reuse after process restart.
    _save_model_weights(cache_key, weights)
    # Return the same object stored in the cache.
    return weights


# Build the immutable cache key for one games snapshot and tuning configuration.
cdef tuple _model_weights_cache_key(
    games,
    str canonical_season_type,
    str season_id,
    Py_ssize_t recent_games,
    int min_prior_games,
    int tune_trials,
    int tuning_iterations,
    int seed,
):
    # Look for a matching cached games object with an already calculated hash.
    cdef object snapshot = _games_cache.get((canonical_season_type, season_id))
    # Reuse its hash by identity or calculate one for an independent game list.
    cdef object fingerprint = (
        snapshot[1] if snapshot is not None and snapshot[0] is games
        else _games_fingerprint(games)
    )
    # Return all values that can change the fitted model output.
    return (
        canonical_season_type,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
        fingerprint,
    )


# Return one cached season snapshot while sharing concurrent database loads.
async def _cached_games(connection, object backtest, str canonical, str season_id):
    # Identify loaded games by canonical season type and database season id.
    cdef tuple cache_key = (canonical, season_id)
    # Check for a previously published games snapshot.
    cdef object cached = _games_cache.get(cache_key)
    # Reserve a reference to an in-progress shared loading task.
    cdef object task
    # Reserve the completed list of Game objects.
    cdef object games
    # The 30-minute background refresh publishes games and weights together.
    # Requests keep the prior snapshot until that replacement is ready.
    # Return the games portion of the cached (games, fingerprint) pair.
    if cached is not None:
        return cached[0]

    # Reuse an in-flight load started by another request for the same season.
    task = _games_load_tasks.get(cache_key)
    # Start a database-loading task only on the first concurrent miss.
    if task is None:
        task = asyncio.create_task(
            # Delegate the actual query and row grouping to the backtest module.
            backtest.load_games(connection, canonical, season_id)
        )
        # Publish the task before awaiting so other callers can find it.
        _games_load_tasks[cache_key] = task
    # Clean shared-task state regardless of the loader's outcome.
    try:
        # Await the existing or newly created load.
        games = await task
    finally:
        # Avoid deleting a newer task that might have replaced this one.
        if _games_load_tasks.get(cache_key) is task:
            _games_load_tasks.pop(cache_key, None)
    # Cache the loaded object together with its model-relevant fingerprint.
    _games_cache[cache_key] = (games, _games_fingerprint(games))
    # Return the freshly loaded historical snapshot.
    return games


# Reset every volatile cache used by tests, reloads, or explicit invalidation.
def clear_model_weights_cache():
    """Clear historical games and tuning results for tests and reloads."""
    # Remove all completed tuned-weight entries.
    _model_weights_cache.clear()
    # Drop references to any tracked tuning tasks.
    _model_weight_tasks.clear()
    # Remove all completed games snapshots and fingerprints.
    _games_cache.clear()
    # Drop references to any tracked database-loading tasks.
    _games_load_tasks.clear()


# Calculate or reuse model weights for one requested season snapshot.
async def calculate_model_weights(
    connection,
    str season,
    str season_type,
    Py_ssize_t recent_games=20,
    int min_prior_games=1,
    int tune_trials=25,
    int tuning_iterations=750,
    int seed=20260709,
):
    """Fetch/build examples and tune candidates in the Cython worker."""
    # Import normalization and historical loading helpers lazily.
    import backtest_mc_sim as backtest
    # Reject invalid history requirements before cache lookup or database work.
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    # Normalize the frontend season label into the backtest's canonical form.
    canonical = backtest.normalize_season_type(season_type)
    # Derive the database season id from the year and canonical phase.
    season_id = backtest.derive_season_id(season, canonical)
    # Load or reuse the complete season snapshot.
    games = await _cached_games(connection, backtest, canonical, season_id)
    # Return weights keyed by this snapshot and every requested fitting setting.
    return await _cached_model_weights(
        games,
        canonical,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )


# Explicitly reload a season and publish new weights only when fully ready.
async def refresh_model_weights(
    connection,
    str season,
    str season_type,
    Py_ssize_t recent_games=20,
    int min_prior_games=1,
    int tune_trials=25,
    int tuning_iterations=750,
    int seed=20260709,
):
    """Reload one season and retune only when its snapshot has changed."""
    # Import the authoritative loader and fitting helpers lazily.
    import backtest_mc_sim as backtest
    # Reserve the newly loaded games snapshot.
    cdef object games
    # Reserve cached, saved, or newly tuned weights.
    cdef object weights
    # Reserve the full season/settings/fingerprint cache key.
    cdef tuple cache_key
    # Reserve the shorter key used by the games snapshot cache.
    cdef tuple games_key
    # Declare iteration storage for obsolete weight keys.
    cdef object old_key
    # Reject invalid windows before initiating the explicit reload.
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    # Normalize the request and derive its database season id.
    canonical = backtest.normalize_season_type(season_type)
    season_id = backtest.derive_season_id(season, canonical)
    # Bypass the normal games cache so refresh observes current database rows.
    games = await backtest.load_games(connection, canonical, season_id)
    # Fingerprint the new rows and combine them with all fitting settings.
    cache_key = _model_weights_cache_key(
        games,
        canonical,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )
    # Reuse in-memory weights when the reloaded snapshot is unchanged.
    weights = _model_weights_cache.get(cache_key)
    # After restart, try the validated persisted representation next.
    if weights is None:
        weights = _saved_weights(cache_key)
    # Only a genuinely new snapshot/configuration requires CPU-bound retuning.
    if weights is None:
        # Run tuning outside the API event loop.
        weights = await asyncio.to_thread(
            _build_and_tune_model_weights,
            games,
            recent_games,
            min_prior_games,
            tune_trials,
            tuning_iterations,
            seed,
        )
        # Persist newly computed weights for later restarts.
        _save_model_weights(cache_key, weights)

    # Publish only after tuning succeeds. Requests retain the prior snapshot
    # throughout the refresh, and obsolete snapshots do not accumulate.
    # Remove prior fingerprints for the same season and tuning configuration.
    for old_key in list(_model_weights_cache):
        if old_key[:7] == cache_key[:7]:
            _model_weights_cache.pop(old_key, None)
    # Publish the completed new weights before exposing their games snapshot.
    _model_weights_cache[cache_key] = weights
    # Build the key used for request-time games lookup.
    games_key = (canonical, season_id)
    # Atomically replace the visible games snapshot with its matching hash.
    _games_cache[games_key] = (games, cache_key[7])
    # Return the newly published or safely reused vector.
    return weights


# Build matchup features and weights from one internally consistent snapshot.
async def calculate_matchup_inputs_and_model_weights(
    connection,
    str season,
    str season_type,
    str team,
    str opponent,
    Py_ssize_t recent_games=20,
    int min_prior_games=1,
    int tune_trials=25,
    int tuning_iterations=750,
    int seed=20260709,
    prediction_date=None,
):
    """Fetch historical rows once and calculate both API model inputs."""
    # Import season and model helpers lazily to avoid circular initialization.
    import backtest_mc_sim as backtest
    # Validate both window sizes before loading or filtering data.
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    # Normalize the frontend label and validate the requested season format.
    canonical = backtest.normalize_season_type(season_type)
    backtest.derive_season_id(season, canonical)
    # Keep team inputs aligned with the player query's latest common season.
    season_id = await _latest_matchup_season_id(
        connection, backtest, canonical, team, opponent
    )
    # Preserve the combined endpoint's established no-data response.
    if season_id is None:
        return 2, 2
    # Fetch one cached snapshot for both feature building and weight fitting.
    games = await _cached_games(connection, backtest, canonical, season_id)
    # Optionally construct a historical as-of view for a pregame prediction.
    if prediction_date is not None:
        # Parse an ISO date string supplied by an API client.
        if isinstance(prediction_date, str):
            prediction_date = date.fromisoformat(prediction_date)
        # Discard time-of-day when a datetime object is supplied.
        elif isinstance(prediction_date, datetime):
            prediction_date = prediction_date.date()
        # Reject other types rather than silently applying an invalid filter.
        if not isinstance(prediction_date, date):
            raise ValueError("prediction_date must be a date or ISO date string")
        # Both features and fitted weights must use the same pregame snapshot.
        # Exclude the predicted date itself and every later completed game.
        games = [game for game in games if game.game_date < prediction_date]
    # Aggregate team, opponent, league, defense, and pace inputs.
    matchup_inputs = build_matchup_team_inputs(
        games,
        team,
        opponent,
        recent_games,
        min_prior_games,
    )
    # Preserve the API's established insufficient-history return code.
    error_code = 2
    # Propagate the same failure code for both halves of the combined response.
    if isinstance(matchup_inputs, int):
        return error_code, error_code
    # Fit or retrieve weights from exactly the games used for these features.
    model_weights = await _cached_model_weights(
        games,
        canonical,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )
    # Return the coherent feature object and model vector together.
    return matchup_inputs, model_weights
