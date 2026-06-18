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
from libc.math cimport log as c_log, sqrt as c_sqrt, cos as c_cos, pow as c_pow
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
                               pace, league_avgs, int iterations=10000):
    """Run Monte Carlo simulation to estimate team scoring.

    Parameters
    ----------
    off_team_stats : array-like   Offensive team stats (indexed by category)
    def_team_stats : array-like   Defensive team stats (indexed by category)
    pace           : int / float  Estimated number of possessions
    league_avgs    : array-like   League-average rates
    iterations     : int          Number of simulation iterations

    Returns
    -------
    float  Average points scored per simulated game
    """

    # ── Convert inputs to contiguous C-typed memory views ──────────────────
    cdef double[::1] off = np.ascontiguousarray(off_team_stats, dtype=np.float64)
    cdef double[::1] dfn = np.ascontiguousarray(def_team_stats, dtype=np.float64)
    cdef double[::1] lg  = np.ascontiguousarray(league_avgs,  dtype=np.float64)
    cdef int c_pace = <int>pace

    # ── C-typed locals ─────────────────────────────────────────────────────
    # Stat extractions
    cdef double off_fgm, off_fga, off_fg3m, off_fg3a, off_ftm, off_fta
    cdef double off_tov, off_oreb, off_fg2m, off_fg2a
    cdef double def_fga
    cdef double def_dreb, def_stl, def_blk

    # League averages
    cdef double lg_fg_pct, lg_fg3_pct, lg_ft_pct, lg_tov_pct, lg_oreb_pct

    # Derived offensive rates
    cdef double off_fg2_pct, off_fg3_pct, off_ft_pct
    cdef double off_total_actions, off_tov_pct, off_fg_misses, off_oreb_pct

    # Derived defensive rates
    cdef double def_total_reb, def_dreb_pct

    # Disruption & adjustments
    cdef double def_disruption, lg_disruption, disruption_factor
    cdef double adj_fg2_pct, adj_fg3_pct, adj_tov_pct, adj_oreb_pct

    # Possession outcome probabilities
    cdef double prob_3pt, ft_rate, prob_ns_ft, prob_and1, prob_sf

    # Beta shape parameters
    cdef double scale, fg2_a, fg2_b, fg3_a, fg3_b, ft_a, ft_b

    # Per-iteration state (automatically thread-private inside prange)
    cdef double game_fg2, game_fg3, game_ft, points = 0.0, roll
    cdef int poss
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
    off_fg2m = max(0.0, off_fgm - off_fg3m)
    off_fg2a = max(1.0, off_fga - off_fg3a)

    # ── Extract defensive stats ────────────────────────────────────────────
    def_fga  = max(1.0, dfn[2])
    def_dreb = max(0.0, dfn[11])
    def_stl  = max(0.0, dfn[14])
    def_blk  = max(0.0, dfn[15])

    # ── League averages ────────────────────────────────────────────────────
    lg_fg_pct   = lg[0] if lg[0] > 0.0 else 0.471
    lg_fg3_pct  = lg[1] if lg[1] > 0.0 else 0.362
    lg_ft_pct   = lg[2] if lg[2] > 0.0 else 0.781
    lg_tov_pct  = lg[3] if lg[3] > 0.0 else 0.133
    lg_oreb_pct = lg[4] if lg[4] > 0.0 else 0.258

    # ── Offensive derived rates ────────────────────────────────────────────
    off_fg2_pct = off_fg2m / off_fg2a if off_fg2a > 0.0 else lg_fg_pct
    off_fg3_pct = off_fg3m / off_fg3a if off_fg3a > 0.0 else lg_fg3_pct
    off_ft_pct  = off_ftm  / off_fta  if off_fta  > 0.0 else lg_ft_pct

    off_total_actions = off_fga + off_tov + 0.44 * off_fta
    off_tov_pct = off_tov / off_total_actions if off_total_actions > 0.0 else lg_tov_pct

    off_fg_misses = off_fga - off_fgm
    off_oreb_pct  = off_oreb / off_fg_misses if off_fg_misses > 0.0 else lg_oreb_pct

    # ── Defensive derived rates ────────────────────────────────────────────    
    def_total_reb = def_dreb + off_oreb if (def_dreb + off_oreb) > 0.0 else 1.0
    def_dreb_pct  = def_dreb / def_total_reb

    # ── Disruption factor ──────────────────────────────────────────────────
    def_disruption  = (def_stl + def_blk) / def_fga if def_fga > 0.0 else 0.0
    lg_disruption   = 0.12
    disruption_factor = def_disruption / lg_disruption if lg_disruption > 0.0 else 1.0
    disruption_factor = clamp(disruption_factor, 0.85, 1.15)

    # ── Adjusted rates ─────────────────────────────────────────────────────
    adj_fg2_pct = off_fg2_pct / disruption_factor
    adj_fg3_pct = off_fg3_pct / disruption_factor
    adj_tov_pct = off_tov_pct * disruption_factor

    if (1.0 - lg_oreb_pct) > 0.0:
        adj_oreb_pct = off_oreb_pct * (1.0 - def_dreb_pct) / (1.0 - lg_oreb_pct)
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
    prob_ns_ft = ft_rate * 0.15
    prob_and1  = ft_rate * 0.05
    prob_sf    = ft_rate * 0.20

    # ── Beta distribution shape parameters ────────────────────────────────
    scale = max(1.0, off_fga / 90.0)
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

                # ── Field goal attempt ──────────────────────────────────
                else:
                    if uniform(my_rng) < prob_3pt:
                        # ── 3-point attempt ────────────────────────────
                        if uniform(my_rng) < game_fg3:
                            # Made 3-pointer
                            points += 3.0
                            if uniform(my_rng) < prob_and1:
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                            poss = poss - 1
                        else:
                            # Missed 3-pointer
                            if uniform(my_rng) < prob_sf:
                                # Shooting foul — 3 FTs
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                poss = poss - 1
                            elif uniform(my_rng) < adj_oreb_pct:
                                pass   # Offensive rebound — same possession
                            else:
                                poss = poss - 1
                    else:
                        # ── 2-point attempt ────────────────────────────
                        if uniform(my_rng) < game_fg2:
                            # Made 2-pointer
                            points += 2.0
                            if uniform(my_rng) < prob_and1:
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                            poss = poss - 1
                        else:
                            # Missed 2-pointer
                            if uniform(my_rng) < prob_sf:
                                # Shooting foul — 2 FTs
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                if uniform(my_rng) < game_ft:
                                    points += 1.0
                                poss = poss - 1
                            elif uniform(my_rng) < adj_oreb_pct:
                                pass   # Offensive rebound — same possession
                            else:
                                poss = poss - 1

            total_points += points

    free(rng_states)
    return total_points / <double>iterations
