# mc_sim.pyx
# Monte Carlo simulation engine — parallel Cython implementation.
#
# The outer iteration loop uses OpenMP (via Cython prange) for parallel
# execution across all available CPU cores.  Each thread owns its own RNG
# state (xorshift64*) for lock-free, race-free randomness.  Beta sampling
# uses Marsaglia & Tsang gamma variates.  The entire simulation loop runs
# with the GIL released.

# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True
# cython: initializedcheck=False

import numpy as np
cimport numpy as cnp
from cython.parallel cimport prange
from libc.stdlib cimport malloc, free, rand, srand
from libc.math cimport log as c_log, sqrt as c_sqrt, cos as c_cos, pow as c_pow, round
from openmp cimport omp_get_thread_num, omp_get_max_threads

cnp.import_array()

# Seed the C RNG once on module import (used only to initialise per-thread
# xorshift states; the global rand() is never called inside the parallel
# region).
import time as _time
srand(<unsigned int>(<long long>(_time.time() * 1000000)))


# ── Per-thread RNG state (xorshift64*) ────────────────────────────────────
#    Simple, fast, and statistically adequate for Monte Carlo simulation.
#    Each thread gets its own RngState so no locks are needed.

cdef struct RngState:
    unsigned long long s


cdef inline void rng_init(RngState *st, unsigned long long seed) noexcept nogil:
    """Seed an RngState via SplitMix64 ( avalanche — no zero states)."""
    cdef unsigned long long z
    z = seed + <unsigned long long>0x9E3779B97F4A7C15
    z = (z ^ (z >> 30)) * <unsigned long long>0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * <unsigned long long>0x94D049BB133111EB
    z = z ^ (z >> 31)
    if z == 0:
        z = 1
    st.s = z


cdef inline double uniform(RngState *st) noexcept nogil:
    """Return a uniform random double in [0, 1) with 53 bits of precision."""
    cdef unsigned long long x = st.s
    x ^= x >> 12
    x ^= x << 25
    x ^= x >> 27
    st.s = x
    return <double>((x * <unsigned long long>0x2545F4914F6CDD1D) >> 11) * (1.0 / 9007199254740992.0)


# ── Box-Muller standard normal ─────────────────────────────────────────────
cdef inline double _normal(RngState *st) noexcept nogil:
    cdef double u1, u2
    u1 = uniform(st)
    while u1 == 0.0:
        u1 = uniform(st)
    u2 = uniform(st)
    return c_sqrt(-2.0 * c_log(u1)) * c_cos(6.283185307179586 * u2)


# ── Gamma(shape, 1) — Marsaglia & Tsang for shape ≥ 1 ─────────────────────
#    For shape < 1:  Gamma(a) = Gamma(a+1) · U^(1/a)
cdef double _gamma(double a, RngState *st) noexcept nogil:
    cdef double d, c, x, v, u, res

    if a < 1.0:
        return _gamma(a + 1.0, st) * c_pow(uniform(st), 1.0 / a)

    d = a - 0.3333333333333333          # a - 1/3
    c = 1.0 / c_sqrt(9.0 * d)

    while True:
        while True:
            x = _normal(st)
            v = 1.0 + c * x
            if v > 0.0:
                break
        v = v * v * v
        u = uniform(st)
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            res = d * v
            break
        if c_log(u) < 0.5 * x * x + d * (1.0 - v + c_log(v)):
            res = d * v
            break
    return res

# ── Beta(a, b) via two independent Gamma draws ─────────────────────────────
cdef inline double _beta(double alpha, double beta_param,
                          RngState *st) noexcept nogil:
    cdef double x, y
    x = _gamma(alpha, st)
    y = _gamma(beta_param, st)
    if x + y == 0.0:
        return 0.5
    return x / (x + y)


# ── Inline clamp ───────────────────────────────────────────────────────────
cdef inline double clamp(double v, double lo, double hi) noexcept nogil:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


# ═══════════════════════════════════════════════════════════════════════════
#  Public API — parallel Monte Carlo simulation
# ═══════════════════════════════════════════════════════════════════════════
def run_monte_carlo_simulation(off_team_stats, def_team_stats,
                               pace, league_avgs, def_allowed_stats=None,
                               int iterations=10000):
    """Run Monte Carlo simulation to estimate team scoring.

    Parameters
    ----------
    off_team_stats : array-like   Offensive team stats (indexed by category)
    def_team_stats : array-like   Defensive team stats (indexed by category)
    pace           : int / float  Estimated number of possessions
    league_avgs    : array-like   League-average rates
    def_allowed_stats : array-like Defensive allowed rates:
                                  eFG% allowed, TOV forced rate,
                                  opponent FT rate allowed, DREB%
    iterations     : int          Number of simulation iterations

    Returns
    -------
    float  Average points scored per simulated game
    """

    # ── Convert inputs to contiguous C-typed memory views ──────────────────
    cdef double[::1] off = np.ascontiguousarray(off_team_stats, dtype=np.float64)
    cdef double[::1] dfn = np.ascontiguousarray(def_team_stats, dtype=np.float64)
    cdef double[::1] lg  = np.ascontiguousarray(league_avgs,  dtype=np.float64)
    cdef double[::1] allowed = np.ascontiguousarray(
        [] if def_allowed_stats is None else def_allowed_stats,
        dtype=np.float64)
    cdef Py_ssize_t allowed_len = allowed.shape[0]
    cdef int c_pace = <int>round(pace)

    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if c_pace <= 0:
        c_pace = 1

    # ── C-typed locals ─────────────────────────────────────────────────────
    # Stat extractions
    cdef double off_fgm, off_fga, off_fg3m, off_fg3a, off_ftm, off_fta
    cdef double off_tov, off_oreb, off_fg2m, off_fg2a, off_ast
    cdef double off_plus_minus, def_plus_minus
    cdef double def_fga
    cdef double def_dreb, def_stl, def_blk, def_pf

    # League averages
    cdef double lg_fg_pct, lg_fg3_pct, lg_ft_pct, lg_tov_pct, lg_oreb_pct
    cdef double lg_efg_pct, lg_fta_rate, lg_dreb_pct

    # Derived offensive rates
    cdef double off_fg2_pct, off_fg3_pct, off_ft_pct
    cdef double off_total_actions, off_tov_pct, off_fg_misses, off_oreb_pct
    cdef double est_possessions, fga_per_poss, extra_shot_factor

    # Derived defensive rates
    cdef double def_total_reb, def_dreb_pct, def_dreb_pct_proxy, def_dreb_pct_raw
    cdef double def_efg_allowed, def_tov_forced_pct, def_fta_rate_allowed

    # Disruption & adjustments
    cdef double def_disruption, lg_disruption, disruption_factor
    cdef double shot_disruption_factor
    cdef double def_foul_factor, shot_quality_factor
    cdef double efg_allowed_factor, tov_allowed_factor, dreb_allowed_factor
    cdef double adj_fg2_pct, adj_fg3_pct, adj_tov_pct, adj_oreb_pct

    # Possession outcome probabilities
    cdef double prob_3pt, ft_rate, prob_ns_ft, prob_and1
    cdef double prob_sf2, prob_sf3, prob_initial_shot, miss_rate
    cdef double foul_no_fga_rate

    # Final score context
    cdef double sim_points, lineup_strength_adjustment

    # Beta shape parameters
    cdef double scale, fg2_a, fg2_b, fg3_a, fg3_b, ft_a, ft_b

    # Per-iteration state (automatically thread-private inside prange)
    cdef double game_fg2, game_fg3, game_ft, points = 0.0, roll
    cdef int poss, shot_done
    cdef double total_points = 0.0

    # ── Extract offensive stats ────────────────────────────────────────────
    off_fgm  = max(0.0, off[1])
    off_fga  = max(1.0, off[2])
    off_fg3m = max(0.0, off[4])
    off_fg3a = max(0.0, off[5])
    off_ftm  = max(0.0, off[7])
    off_fta  = max(0.0, off[8])
    off_tov  = max(0.0, off[16])
    off_oreb = max(0.0, off[10])
    off_ast  = max(0.0, off[13])
    off_plus_minus = off[19]
    off_fg2m = max(0.0, off_fgm - off_fg3m)
    off_fg2a = max(1.0, off_fga - off_fg3a)

    # ── Extract defensive stats ────────────────────────────────────────────
    def_fga  = max(1.0, dfn[2])
    def_dreb = max(0.0, dfn[11])
    def_stl  = max(0.0, dfn[14])
    def_blk  = max(0.0, dfn[15])
    def_pf   = max(0.0, dfn[17])
    def_plus_minus = dfn[19]

    # ── League averages ────────────────────────────────────────────────────
    lg_fg_pct   = lg[0] if lg[0] > 0.0 else 0.471
    lg_fg3_pct  = lg[1] if lg[1] > 0.0 else 0.362
    lg_ft_pct   = lg[2] if lg[2] > 0.0 else 0.781
    lg_tov_pct  = lg[3] if lg[3] > 0.0 else 0.133
    lg_oreb_pct = lg[4] if lg[4] > 0.0 else 0.258
    lg_efg_pct  = 0.545
    lg_fta_rate = 0.250
    lg_dreb_pct = 1.0 - lg_oreb_pct

    # ── Offensive derived rates ────────────────────────────────────────────
    off_fg2_pct = off_fg2m / off_fg2a if off_fg2a > 0.0 else lg_fg_pct
    off_fg3_pct = off_fg3m / off_fg3a if off_fg3a > 0.0 else lg_fg3_pct
    off_ft_pct  = off_ftm  / off_fta  if off_fta  > 0.0 else lg_ft_pct

    off_total_actions = off_fga + off_tov + 0.44 * off_fta
    off_tov_pct = off_tov / off_total_actions if off_total_actions > 0.0 else lg_tov_pct

    off_fg_misses = off_fga - off_fgm
    off_oreb_pct  = off_oreb / off_fg_misses if off_fg_misses > 0.0 else lg_oreb_pct

    est_possessions = off_fga + 0.44 * off_fta + off_tov - off_oreb
    if est_possessions <= 1.0:
        est_possessions = pace if pace > 1.0 else 100.0
    fga_per_poss = off_fga / est_possessions if est_possessions > 0.0 else 0.88

    # ── Defensive derived rates ────────────────────────────────────────────    
    def_total_reb = def_dreb + off_oreb if (def_dreb + off_oreb) > 0.0 else 1.0
    def_dreb_pct_raw = def_dreb / def_total_reb
    def_dreb_pct_proxy = lg_dreb_pct + 0.50 * (def_dreb_pct_raw - lg_dreb_pct)
    def_dreb_pct_proxy = clamp(def_dreb_pct_proxy, lg_dreb_pct - 0.10, lg_dreb_pct + 0.10)


    if allowed_len > 0 and allowed[0] > 0.0:
        def_efg_allowed = allowed[0]
    else:
        def_efg_allowed = lg_efg_pct

    if allowed_len > 1 and allowed[1] > 0.0:
        def_tov_forced_pct = allowed[1]
    else:
        def_tov_forced_pct = lg_tov_pct

    if allowed_len > 2 and allowed[2] > 0.0:
        def_fta_rate_allowed = allowed[2]
    else:
        def_fta_rate_allowed = lg_fta_rate

    if allowed_len > 3 and allowed[3] > 0.0:
        def_dreb_pct = allowed[3]
    else:
        def_dreb_pct = def_dreb_pct_proxy

    # ── Defensive context ──────────────────────────────────────────────────
    # The offensive inputs are already minutes-weighted and matchup-adjusted.
    # Keep defensive effects modest so we do not double-count the matchup.
    def_disruption  = (def_stl + def_blk) / def_fga if def_fga > 0.0 else 0.0
    lg_disruption   = 0.12
    disruption_factor = def_disruption / lg_disruption if lg_disruption > 0.0 else 1.0
    shot_disruption_factor = clamp(1.0 + 0.35 * (disruption_factor - 1.0), 0.90, 1.10)

    tov_allowed_factor = def_tov_forced_pct / lg_tov_pct if lg_tov_pct > 0.0 else 1.0
    tov_allowed_factor = clamp(1.0 + 0.50 * (tov_allowed_factor - 1.0), 0.90, 1.10)
    disruption_factor = clamp(shot_disruption_factor * tov_allowed_factor, 0.88, 1.14)

    def_foul_factor = def_pf / 18.5 if def_pf > 0.0 else 1.0
    def_foul_factor = clamp(1.0 + 0.10 * (def_foul_factor - 1.0), 0.96, 1.04)
    def_foul_factor = def_foul_factor * (
        def_fta_rate_allowed / lg_fta_rate if lg_fta_rate > 0.0 else 1.0)
    def_foul_factor = clamp(1.0 + 0.50 * (def_foul_factor - 1.0), 0.88, 1.12)

    shot_quality_factor = off_ast / off_fgm if off_fgm > 0.0 else 0.60
    shot_quality_factor = clamp(1.0 + 0.08 * (shot_quality_factor - 0.60), 0.96, 1.04)

    efg_allowed_factor = def_efg_allowed / lg_efg_pct if lg_efg_pct > 0.0 else 1.0
    efg_allowed_factor = clamp(1.0 + 0.45 * (efg_allowed_factor - 1.0), 0.93, 1.07)

    # ── Adjusted rates ─────────────────────────────────────────────────────
    adj_fg2_pct = off_fg2_pct * shot_quality_factor * efg_allowed_factor / shot_disruption_factor
    adj_fg3_pct = off_fg3_pct * (0.5 + 0.5 * shot_quality_factor) * efg_allowed_factor / shot_disruption_factor
    adj_tov_pct = off_tov_pct * disruption_factor

    dreb_allowed_factor = (1.0 - def_dreb_pct) / (1.0 - lg_oreb_pct) if (1.0 - lg_oreb_pct) > 0.0 else 1.0
    dreb_allowed_factor = clamp(1.0 + 0.60 * (dreb_allowed_factor - 1.0), 0.70, 1.10)

    if lg_oreb_pct > 0.0:
        adj_oreb_pct = off_oreb_pct * dreb_allowed_factor
    else:
        adj_oreb_pct = off_oreb_pct

    adj_fg2_pct = clamp(adj_fg2_pct, 0.25, 0.65)
    adj_fg3_pct = clamp(adj_fg3_pct, 0.20, 0.50)
    adj_tov_pct = clamp(adj_tov_pct, 0.05, 0.25)
    adj_oreb_pct = clamp(adj_oreb_pct, 0.10, 0.45)
    off_ft_pct   = clamp(off_ft_pct, 0.50, 0.95)

    # ── Possession outcome probabilities ───────────────────────────────────
    prob_3pt   = off_fg3a / off_fga if off_fga > 0.0 else 0.35
    ft_rate    = off_fta  / off_fga if off_fga > 0.0 else 0.25
    prob_3pt   = clamp(prob_3pt, 0.05, 0.65)
    ft_rate    = clamp(ft_rate * def_foul_factor, 0.05, 0.60)
    prob_ns_ft = clamp(0.44 * ft_rate * 0.18, 0.005, 0.060)
    prob_and1  = clamp(ft_rate * 0.10, 0.005, 0.045)
    prob_sf2   = clamp(ft_rate * 0.62, 0.035, 0.260)
    prob_sf3   = clamp(ft_rate * 0.14, 0.005, 0.075)

    miss_rate = 1.0 - (prob_3pt * adj_fg3_pct + (1.0 - prob_3pt) * adj_fg2_pct)
    miss_rate = clamp(miss_rate, 0.25, 0.75)
    extra_shot_factor = 1.0 - miss_rate * adj_oreb_pct
    if extra_shot_factor <= 0.20:
        extra_shot_factor = 0.20
    foul_no_fga_rate = prob_3pt * prob_sf3 + (1.0 - prob_3pt) * prob_sf2
    foul_no_fga_rate = clamp(foul_no_fga_rate, 0.02, 0.24)
    prob_initial_shot = fga_per_poss * extra_shot_factor / (1.0 - foul_no_fga_rate)
    prob_initial_shot = clamp(prob_initial_shot, 0.50, 0.92)

    if adj_tov_pct + prob_ns_ft + prob_initial_shot > 0.995:
        prob_initial_shot = 0.995 - adj_tov_pct - prob_ns_ft
        if prob_initial_shot < 0.45:
            prob_initial_shot = 0.45

    # ── Beta distribution shape parameters ────────────────────────────────
    scale = max(1.0, off_fga / 65.0)
    fg2_a = max(2.0, off_fg2m / scale)
    fg2_b = max(2.0, (off_fg2a - off_fg2m) / scale)
    fg3_a = max(2.0, off_fg3m / scale)
    fg3_b = max(2.0, (off_fg3a - off_fg3m) / scale)
    ft_a  = max(2.0, off_ftm / scale)
    ft_b  = max(2.0, (off_fta - off_ftm) / scale)

    # ══════════════════════════════════════════════════════════════════════
    #  Per-thread RNG initialisation
    # ══════════════════════════════════════════════════════════════════════
    cdef int nthreads = omp_get_max_threads()
    cdef RngState *rng_states = <RngState *>malloc(
        nthreads * sizeof(RngState))
    if rng_states == NULL:
        raise MemoryError("Failed to allocate per-thread RNG states")

    # Each thread gets a unique seed drawn from the already-seeded libc RNG
    cdef int j
    for j in range(nthreads):
        rng_init(&rng_states[j], <unsigned long long>rand()
                 | (<unsigned long long>rand() << 15)
                 | (<unsigned long long>rand() << 30)
                 | (<unsigned long long>rand() << 45))

    cdef RngState *my_rng
    cdef int tid

    # ══════════════════════════════════════════════════════════════════════
    #  Main simulation loop — OpenMP parallel, GIL released
    #  Cython auto-detects `total_points += points` as a reduction.
    #  All other per-iteration variables are automatically thread-private.
    # ══════════════════════════════════════════════════════════════════════
    with nogil:
        for i in prange(iterations, schedule='static'):

            # Pick this thread's private RNG state
            tid = omp_get_thread_num()
            my_rng = &rng_states[tid]

            # Sample per-game percentages from Beta distributions
            game_fg2 = _beta(fg2_a, fg2_b, my_rng)
            game_fg3 = _beta(fg3_a, fg3_b, my_rng)
            game_ft  = _beta(ft_a,  ft_b,  my_rng)

            # Apply defensive adjustment
            if off_fg2_pct > 0.0:
                game_fg2 = game_fg2 * (adj_fg2_pct / off_fg2_pct)
            if off_fg3_pct > 0.0:
                game_fg3 = game_fg3 * (adj_fg3_pct / off_fg3_pct)

            game_fg2 = clamp(game_fg2, 0.20, 0.70)
            game_fg3 = clamp(game_fg3, 0.15, 0.55)
            game_ft  = clamp(game_ft,  0.40, 0.98)

            points = 0.0
            poss = c_pace

            while poss > 0:
                roll = uniform(my_rng)

                # ── Turnover ────────────────────────────────────────────
                if roll < adj_tov_pct:
                    poss = poss - 1

                # ── Non-shooting free throws ────────────────────────────
                elif roll < adj_tov_pct + prob_ns_ft:
                    if uniform(my_rng) < game_ft:
                        points += 1.0
                    if uniform(my_rng) < game_ft:
                        points += 1.0
                    poss = poss - 1

                elif roll >= adj_tov_pct + prob_ns_ft + prob_initial_shot:
                    # Empty/late-clock possessions that produce no tracked
                    # box-score event keep simulated FGA volume calibrated.
                    poss = poss - 1

                # ── Field goal attempt ──────────────────────────────────
                else:
                    shot_done = 0
                    while shot_done == 0:
                        if uniform(my_rng) < prob_3pt:
                            # ── 3-point attempt ────────────────────────
                            if uniform(my_rng) < prob_sf3:
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                shot_done = 1
                            elif uniform(my_rng) < game_fg3:
                                points += 3.0
                                if uniform(my_rng) < prob_and1:
                                    if uniform(my_rng) < game_ft:
                                        points += 1.0
                                shot_done = 1
                            elif uniform(my_rng) >= adj_oreb_pct:
                                shot_done = 1
                        else:
                            # ── 2-point attempt ────────────────────────
                            if uniform(my_rng) < prob_sf2:
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                shot_done = 1
                            elif uniform(my_rng) < game_fg2:
                                points += 2.0
                                if uniform(my_rng) < prob_and1:
                                    if uniform(my_rng) < game_ft:
                                        points += 1.0
                                shot_done = 1
                            elif uniform(my_rng) >= adj_oreb_pct:
                                shot_done = 1
                    poss = poss - 1

            total_points += points

    free(rng_states)
    sim_points = total_points / <double>iterations

    # The event simulation already generates a realistic single-game total.
    # Do not pull it back to season/matchup average scoring; that made low-
    # scoring Finals-style games drift too high.  Plus-minus is used only as a
    # small, clamped lineup-strength signal to help the two independent team
    # calls preserve the expected winner.
    lineup_strength_adjustment = clamp(
        0.10 * (off_plus_minus - def_plus_minus), -3.5, 3.5)
    sim_points = sim_points + lineup_strength_adjustment
    if sim_points < 0.0:
        sim_points = 0.0

    return sim_points
