# backtest_api.pyx
"""Low-latency API entry points for matchup inputs and weight tuning."""

# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True
# cython: initializedcheck=False

import asyncio
import os
import sys
import time

import numpy as np
cimport numpy as cnp
from cython.parallel cimport prange

cnp.import_array()

cdef int STAT_COUNT = 20

# Weight tuning depends on the season snapshot, not the requested matchup.
# Cache completed results and share an in-flight task so concurrent requests
# never tune the same snapshot more than once.
_model_weights_cache = {}
_model_weight_tasks = {}
_games_cache = {}
_games_load_tasks = {}
GAMES_CACHE_TTL_SECONDS = max(
    1.0, float(os.getenv("BACKTEST_GAMES_CACHE_TTL_SECONDS", "300"))
)

# Model weights describe a season snapshot. They must not be retrained for
# every request-specific recent-games window; the request window only affects
# the matchup inputs built below. This also matches the cache key warmed by
# api.lifespan at startup.
MODEL_WEIGHT_RECENT_GAMES = sys.maxsize


cdef double _sum_column(
    double[:, ::1] rows, Py_ssize_t column
) noexcept nogil:
    cdef Py_ssize_t i
    cdef double total = 0.0
    for i in range(rows.shape[0]):
        total = total + rows[i, column]
    return total


cdef cnp.ndarray[cnp.float64_t, ndim=1] _mean_rows(
    double[:, ::1] rows,
):
    cdef Py_ssize_t row_count = rows.shape[0]
    cdef Py_ssize_t j
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = np.empty(
        STAT_COUNT, dtype=np.float64
    )
    cdef double[::1] output = result

    with nogil:
        for j in prange(
            STAT_COUNT,
            schedule="static",
            use_threads_if=row_count * STAT_COUNT >= 4096,
        ):
            output[j] = _sum_column(rows, j) / row_count
    return result


cdef cnp.ndarray[cnp.float64_t, ndim=1] _sum_rows(
    double[:, ::1] rows,
):
    cdef Py_ssize_t row_count = rows.shape[0]
    cdef Py_ssize_t j
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = np.empty(
        STAT_COUNT, dtype=np.float64
    )
    cdef double[::1] output = result

    with nogil:
        for j in prange(
            STAT_COUNT,
            schedule="static",
            use_threads_if=row_count * STAT_COUNT >= 4096,
        ):
            output[j] = _sum_column(rows, j)
    return result


cdef void _recompute_percentages(double[::1] stats) noexcept nogil:
    cdef Py_ssize_t i
    stats[3] = stats[1] / stats[2] if stats[2] > 0.0 else 0.0
    stats[6] = stats[4] / stats[5] if stats[5] > 0.0 else 0.0
    stats[9] = stats[7] / stats[8] if stats[8] > 0.0 else 0.0
    for i in range(STAT_COUNT - 1):
        if stats[i] < 0.0:
            stats[i] = 0.0


cdef cnp.ndarray[cnp.float64_t, ndim=1] _team_input(
    double[:, ::1] history,
    double[:, ::1] matchup,
    Py_ssize_t recent_games,
    double matchup_adjustment,
    double matchup_prior_games,
):
    cdef Py_ssize_t history_start = max(0, history.shape[0] - recent_games)
    cdef Py_ssize_t matchup_start = max(0, matchup.shape[0] - recent_games)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] result = _mean_rows(
        history[history_start:]
    )
    cdef cnp.ndarray[cnp.float64_t, ndim=1] matchup_mean
    cdef double[::1] output = result
    cdef double[::1] matched
    cdef double shrinkage
    cdef Py_ssize_t j

    if matchup.shape[0] and matchup_adjustment != 0.0:
        matchup_mean = _mean_rows(matchup[matchup_start:])
        matched = matchup_mean
        shrinkage = matchup.shape[0] - matchup_start
        shrinkage /= shrinkage + max(0.0, matchup_prior_games)
        with nogil:
            for j in range(STAT_COUNT):
                output[j] += (
                    matchup_adjustment * shrinkage * (matched[j] - output[j])
                )
    with nogil:
        _recompute_percentages(output)
    return result


cdef cnp.ndarray[cnp.float64_t, ndim=1] _league_averages(
    double[:, ::1] stats_rows,
    double[:, ::1] opponent_rows,
):
    cdef cnp.ndarray[cnp.float64_t, ndim=1] stats_array = _sum_rows(stats_rows)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_array = _sum_rows(
        opponent_rows
    )
    cdef double[::1] stats = stats_array
    cdef double[::1] opponent = opponent_array
    cdef double action_total = stats[2] + 0.44 * stats[8] + stats[16]
    cdef double rebound_chances = stats[10] + opponent[11]
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


cdef cnp.ndarray[cnp.float64_t, ndim=1] _defensive_factors(
    double[:, ::1] own_rows,
    double[:, ::1] opponent_rows,
    Py_ssize_t recent_games,
):
    cdef Py_ssize_t start = max(0, own_rows.shape[0] - recent_games)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] own_array = _sum_rows(
        own_rows[start:]
    )
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_array = _sum_rows(
        opponent_rows[start:]
    )
    cdef double[::1] own = own_array
    cdef double[::1] opponent = opponent_array
    cdef double actions = opponent[2] + 0.44 * opponent[8] + opponent[16]
    cdef double rebound_chances = own[11] + opponent[10]
    return np.array(
        [
            (opponent[1] + 0.5 * opponent[4]) / opponent[2]
            if opponent[2]
            else 0.545,
            opponent[16] / actions if actions else 0.127,
            opponent[8] / opponent[2] if opponent[2] else 0.250,
            own[11] / rebound_chances if rebound_chances else 0.695,
        ],
        dtype=np.float64,
    )


cdef double _expected_pace(
    double[::1] team_paces,
    double[::1] opponent_paces,
    double[:, ::1] team_rows,
    Py_ssize_t recent_games,
) noexcept nogil:
    cdef Py_ssize_t i
    cdef Py_ssize_t team_start = max(0, team_paces.shape[0] - recent_games)
    cdef Py_ssize_t opponent_start = max(
        0, opponent_paces.shape[0] - recent_games
    )
    cdef double total = 0.0
    cdef Py_ssize_t count = 0
    cdef double possessions = 0.0

    for i in range(team_start, team_paces.shape[0]):
        if team_paces[i] > 0.0:
            total += team_paces[i]
            count += 1
    for i in range(opponent_start, opponent_paces.shape[0]):
        if opponent_paces[i] > 0.0:
            total += opponent_paces[i]
            count += 1
    if count:
        return total / count

    for i in range(max(0, team_rows.shape[0] - recent_games), team_rows.shape[0]):
        possessions += (
            team_rows[i, 2]
            + 0.44 * team_rows[i, 8]
            + team_rows[i, 16]
            - team_rows[i, 10]
        )
    possessions /= min(team_rows.shape[0], recent_games)
    return max(1.0, possessions)


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
    cdef list team_stats = []
    cdef list team_opponent_stats = []
    cdef list team_paces = []
    cdef list team_matchup = []
    cdef list opponent_stats = []
    cdef list opponent_opponent_stats = []
    cdef list opponent_paces = []
    cdef list opponent_matchup = []
    cdef list all_stats = []
    cdef list all_opponent_stats = []
    cdef object game, row, other
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_opponent_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_opponent_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] all_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] all_opponent_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] team_matchup_array
    cdef cnp.ndarray[cnp.float64_t, ndim=2] opponent_matchup_array
    cdef cnp.ndarray[cnp.float64_t, ndim=1] team_pace_array
    cdef cnp.ndarray[cnp.float64_t, ndim=1] opponent_pace_array
    cdef double pace

    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    for game in games:
        for row, other in ((game.home, game.away), (game.away, game.home)):
            all_stats.append(row.stats)
            all_opponent_stats.append(other.stats)
            if row.team == team:
                team_stats.append(row.stats)
                team_opponent_stats.append(other.stats)
                team_paces.append(row.pace if row.pace is not None else 0.0)
                if other.team == opponent:
                    team_matchup.append(row.stats)
            elif row.team == opponent:
                opponent_stats.append(row.stats)
                opponent_opponent_stats.append(other.stats)
                opponent_paces.append(row.pace if row.pace is not None else 0.0)
                if other.team == team:
                    opponent_matchup.append(row.stats)
    error_code = 2
    if (
        len(team_stats) < min_prior_games
        or len(opponent_stats) < min_prior_games
        or not all_stats
    ):
        return error_code

    team_array = np.ascontiguousarray(team_stats, dtype=np.float64)
    team_opponent_array = np.ascontiguousarray(
        team_opponent_stats, dtype=np.float64
    )
    opponent_array = np.ascontiguousarray(opponent_stats, dtype=np.float64)
    opponent_opponent_array = np.ascontiguousarray(
        opponent_opponent_stats, dtype=np.float64
    )
    all_array = np.ascontiguousarray(all_stats, dtype=np.float64)
    all_opponent_array = np.ascontiguousarray(
        all_opponent_stats, dtype=np.float64
    )
    if team_matchup:
        team_matchup_array = np.ascontiguousarray(team_matchup, dtype=np.float64)
    else:
        team_matchup_array = np.empty((0, STAT_COUNT), dtype=np.float64)
    if opponent_matchup:
        opponent_matchup_array = np.ascontiguousarray(opponent_matchup, dtype=np.float64)
    else:
        opponent_matchup_array = np.empty((0, STAT_COUNT), dtype=np.float64)    
    team_pace_array = np.ascontiguousarray(team_paces, dtype=np.float64)
    opponent_pace_array = np.ascontiguousarray(opponent_paces, dtype=np.float64)

    pace = _expected_pace(
        team_pace_array,
        opponent_pace_array,
        team_array,
        recent_games,
    )

    import backtest_mc_sim as backtest
    return backtest.MatchupTeamInputs(
        team_stats=_team_input(
            team_array,
            team_matchup_array,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        opponent_stats=_team_input(
            opponent_array,
            opponent_matchup_array,
            recent_games,
            matchup_adjustment,
            matchup_prior_games,
        ),
        pace=pace,
        league_averages=_league_averages(all_array, all_opponent_array),
        team_defense=_defensive_factors(
            team_array, team_opponent_array, recent_games
        ),
        opponent_defense=_defensive_factors(
            opponent_array, opponent_opponent_array, recent_games
        ),
    )


async def calculate_matchup_team_inputs(
    connection,
    str season,
    str season_type,
    str team,
    str opponent,
    Py_ssize_t recent_games=20,
):
    """Fetch a season asynchronously, then aggregate it in native code."""
    import backtest_mc_sim as backtest
    canonical = backtest.normalize_season_type(season_type)
    season_id = backtest.derive_season_id(season, canonical)
    games = await backtest.load_games(connection, canonical, season_id)
    return build_matchup_team_inputs(games, team, opponent, recent_games)


cdef void _evaluate_candidate(
    object backtest,
    object examples,
    object adjustment_weights,
    int iterations,
    int seed,
    double* score,
    double* scale,
    double* intercept,
) except *:
    cdef tuple raw_weights = tuple(adjustment_weights) + (1.0, 0.0)
    cdef object raw_predictions = backtest.predict_examples(
        examples, raw_weights, iterations, seed
    )
    cdef tuple calibration = backtest.fit_score_calibration(raw_predictions)
    cdef object predictions = backtest.apply_score_calibration(
        raw_predictions, calibration[0], calibration[1]
    )

    score[0] = backtest.calculate_metrics(predictions).score_mae
    scale[0] = calibration[0]
    intercept[0] = calibration[1]


def tune_model_weights_parallel(
    examples,
    int trials=25,
    int iterations=750,
    int seed=20260709,
):
    """Score independent weight candidates concurrently with OpenMP."""
    import backtest_mc_sim as backtest
    cdef list candidates
    cdef Py_ssize_t count, i, best_index
    cdef cnp.ndarray[cnp.float64_t, ndim=1] scores_array
    cdef cnp.ndarray[cnp.float64_t, ndim=1] scales_array
    cdef cnp.ndarray[cnp.float64_t, ndim=1] intercepts_array
    cdef double[::1] scores
    cdef double[::1] scales
    cdef double[::1] intercepts

    if trials < 0:
        raise ValueError("trials cannot be negative")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not examples:
        return np.ascontiguousarray(backtest.DEFAULT_WEIGHTS, dtype=np.float64)

    candidates = list(backtest.candidate_weights(trials, seed))
    count = len(candidates)
    scores_array = np.empty(count, dtype=np.float64)
    scales_array = np.empty(count, dtype=np.float64)
    intercepts_array = np.empty(count, dtype=np.float64)
    scores = scores_array
    scales = scales_array
    intercepts = intercepts_array

    with nogil:
        for i in prange(
            count, schedule="dynamic", use_threads_if=count > 1
        ):
            with gil:
                _evaluate_candidate(
                    backtest,
                    examples,
                    candidates[i],
                    iterations,
                    seed,
                    &scores[i],
                    &scales[i],
                    &intercepts[i],
                )

    best_index = 0
    for i in range(1, count):
        if scores[i] < scores[best_index]:
            best_index = i
    return np.ascontiguousarray(
        tuple(candidates[best_index])
        + (scales[best_index], intercepts[best_index]),
        dtype=np.float64,
    )


def _build_and_tune_model_weights(
    games,
    Py_ssize_t recent_games,
    int min_prior_games,
    int tune_trials,
    int tuning_iterations,
    int seed,
):
    import backtest_mc_sim as backtest
    examples = backtest.build_examples(
        games,
        recent_games,
        min_prior_games,
        matchup_adjustment=1.0,
        matchup_prior_games=5.0,
    )
    examples = examples[-backtest.API_MAX_GAMES:]
    if len(examples) >= 10:
        split = max(
            1,
            min(
                len(examples) - 1,
                int(len(examples) * backtest.API_TRAIN_FRACTION),
            ),
        )
        examples = examples[:split]
    return tune_model_weights_parallel(
        examples,
        tune_trials,
        tuning_iterations,
        seed,
    )


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
    cdef object cached = _model_weights_cache.get(cache_key)
    cdef object task
    cdef object weights
    if cached is not None:
        return cached

    task = _model_weight_tasks.get(cache_key)
    if task is None:
        task = asyncio.create_task(
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
        _model_weight_tasks[cache_key] = task
    try:
        weights = await task
    finally:
        if _model_weight_tasks.get(cache_key) is task:
            _model_weight_tasks.pop(cache_key, None)
    _model_weights_cache[cache_key] = weights
    return weights


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
    cdef object last_game = games[len(games) - 1] if games else None
    return (
        canonical_season_type,
        season_id,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
        len(games),
        last_game.game_id if last_game is not None else None,
        last_game.game_date if last_game is not None else None,
        float(last_game.home.stats[18]) if last_game is not None else None,
        float(last_game.away.stats[18]) if last_game is not None else None,
    )


async def _cached_games(connection, object backtest, str canonical, str season_id):
    cdef tuple cache_key = (canonical, season_id)
    cdef object cached = _games_cache.get(cache_key)
    cdef double now = time.monotonic()
    cdef object task
    cdef object games
    if cached is not None and now - cached[0] < GAMES_CACHE_TTL_SECONDS:
        return cached[1]

    task = _games_load_tasks.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            backtest.load_games(connection, canonical, season_id)
        )
        _games_load_tasks[cache_key] = task
    try:
        games = await task
    finally:
        if _games_load_tasks.get(cache_key) is task:
            _games_load_tasks.pop(cache_key, None)
    _games_cache[cache_key] = (time.monotonic(), games)
    return games


def clear_model_weights_cache():
    """Clear historical games and tuning results for tests and reloads."""
    _model_weights_cache.clear()
    _model_weight_tasks.clear()
    _games_cache.clear()
    _games_load_tasks.clear()


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
    import backtest_mc_sim as backtest
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    canonical = backtest.normalize_season_type(season_type)
    season_id = backtest.derive_season_id(season, canonical)
    games = await _cached_games(connection, backtest, canonical, season_id)
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
    """Retune one season and atomically replace its cached snapshot."""
    import backtest_mc_sim as backtest
    cdef object games
    cdef object weights
    cdef tuple cache_key
    cdef tuple games_key
    cdef object old_key
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    canonical = backtest.normalize_season_type(season_type)
    season_id = backtest.derive_season_id(season, canonical)
    games = await backtest.load_games(connection, canonical, season_id)
    weights = await asyncio.to_thread(
        _build_and_tune_model_weights,
        games,
        recent_games,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )
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

    # Publish only after tuning succeeds. Requests retain the prior snapshot
    # throughout the refresh, and obsolete snapshots do not accumulate.
    for old_key in list(_model_weights_cache):
        if old_key[:7] == cache_key[:7]:
            _model_weights_cache.pop(old_key, None)
    _model_weights_cache[cache_key] = weights
    games_key = (canonical, season_id)
    _games_cache[games_key] = (time.monotonic(), games)
    return weights


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
):
    """Fetch historical rows once and calculate both API model inputs."""
    import backtest_mc_sim as backtest
    if recent_games <= 0 or min_prior_games <= 0:
        raise ValueError("recent_games and min_prior_games must be positive")

    canonical = backtest.normalize_season_type(season_type)
    season_id = backtest.derive_season_id(season, canonical)
    games = await _cached_games(connection, backtest, canonical, season_id)
    matchup_inputs = build_matchup_team_inputs(
        games,
        team,
        opponent,
        recent_games,
        min_prior_games,
    )
    error_code = 2
    if isinstance(matchup_inputs, int):
        return error_code, error_code
    model_weights = await _cached_model_weights(
        games,
        canonical,
        season_id,
        MODEL_WEIGHT_RECENT_GAMES,
        min_prior_games,
        tune_trials,
        tuning_iterations,
        seed,
    )
    return matchup_inputs, model_weights
