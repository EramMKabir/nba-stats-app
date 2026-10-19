# mc_sim.pyx

# Function: Estimate one NBA team's score through parallel Monte Carlo draws.

# Inputs: Offensive and defensive team statistics, pace, league averages,
# optional defensive factors, optional model weights, and an optional seed.

# Output: The average simulated points scored by the offensive team.

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

# Libraries

import numpy as np
cimport numpy as cnp
from cython.parallel cimport prange
from libc.stdlib cimport malloc, free, rand, srand
from libc.math cimport log as c_log, sqrt as c_sqrt, pow as c_pow, round
from openmp cimport omp_get_thread_num, omp_get_max_threads

# Initialize NumPy's C API before constructing typed arrays.
cnp.import_array()

# Seed the C RNG once on module import (used only to initialise per-thread
# xorshift states; the global rand() is never called inside the parallel
# region).
import time as _time
# Seed libc randomness for calls that do not provide a reproducible seed.
srand(<unsigned int>(<long long>(_time.time() * 1000000)))


# ── Per-thread RNG state (xorshift64*) ────────────────────────────────────
#    Simple, fast, and statistically adequate for Monte Carlo simulation.
#    Each thread gets its own RngState so no locks are needed.

# Store independent random and normal-cache state for one OpenMP thread.
cdef struct RngState:
    # Hold the current xorshift64* state value.
    unsigned long long s
    # Cache the second variate produced by the polar normal transform.
    double spare_normal
    # Record whether spare_normal is ready to be consumed.
    int has_spare_normal
    # Separate adjacent thread states onto cache-line-sized storage.
    char padding[40]


# Initialize one thread-local xorshift state through SplitMix64 scrambling.
cdef inline void rng_init(RngState *st, unsigned long long seed) noexcept nogil:
    """Seed an RngState via SplitMix64 ( avalanche — no zero states)."""
    # Reserve the intermediate SplitMix64 value.
    cdef unsigned long long z
    # Offset the seed by the SplitMix64 golden-ratio constant.
    z = seed + <unsigned long long>0x9E3779B97F4A7C15
    # Apply the first xor-shift and avalanche multiplier.
    z = (z ^ (z >> 30)) * <unsigned long long>0xBF58476D1CE4E5B9
    # Apply the second xor-shift and avalanche multiplier.
    z = (z ^ (z >> 27)) * <unsigned long long>0x94D049BB133111EB
    # Complete diffusion with the final xor-shift.
    z = z ^ (z >> 31)
    # Xorshift cannot advance from an all-zero state.
    if z == 0:
        z = 1
    # Publish the safe scrambled state.
    st.s = z
    # Start with no cached normal variate.
    st.has_spare_normal = 0


# Advance one thread's xorshift state and return a uniform value in [0, 1).
cdef inline double uniform(RngState *st) noexcept nogil:
    """Return a uniform random double in [0, 1) with 53 bits of precision."""
    # Copy state into a register for the xorshift operations.
    cdef unsigned long long x = st.s
    # Apply the xorshift64* bit-mixing sequence.
    x ^= x >> 12
    x ^= x << 25
    x ^= x >> 27
    # Save the advanced state before generating output.
    st.s = x
    # Multiply, select 53 bits, and scale them into a double fraction.
    return <double>((x * <unsigned long long>0x2545F4914F6CDD1D) >> 11) * (1.0 / 9007199254740992.0)


# ── Marsaglia polar standard normal ───────────────────────────────────────
# Draw one standard normal value with the Marsaglia polar method.
cdef inline double _normal(RngState *st) noexcept nogil:
    # Declare candidate coordinates and transform intermediates.
    cdef double x, y, radius_squared, multiplier

    # Reuse the cached partner from the previous accepted coordinate pair.
    if st.has_spare_normal:
        st.has_spare_normal = 0
        return st.spare_normal

    # Draw inside the unit circle while excluding its zero-radius center.
    while True:
        # Map two independent uniforms from [0, 1) to [-1, 1).
        x = 2.0 * uniform(st) - 1.0
        y = 2.0 * uniform(st) - 1.0
        # Calculate squared radius without an unnecessary square root.
        radius_squared = x * x + y * y
        # Accept only values supported by the polar transform.
        if radius_squared > 0.0 and radius_squared < 1.0:
            break

    # Calculate the common transform multiplier for both normal values.
    multiplier = c_sqrt(-2.0 * c_log(radius_squared) / radius_squared)
    # Cache one normal value for the next call.
    st.spare_normal = y * multiplier
    st.has_spare_normal = 1
    # Return the other normal value immediately.
    return x * multiplier


# ── Gamma(shape, 1) — Marsaglia & Tsang for shape ≥ 1 ─────────────────────
#    For shape < 1:  Gamma(a) = Gamma(a+1) · U^(1/a)
# Draw a Gamma variate with unit scale for beta-distribution construction.
cdef double _gamma(double a, RngState *st) noexcept nogil:
    # Declare algorithm constants, random draws, and the accepted result.
    cdef double d, c, x, v, u, res

    # Boost subunit shapes and transform the result back to Gamma(a).
    if a < 1.0:
        return _gamma(a + 1.0, st) * c_pow(uniform(st), 1.0 / a)

    # Precompute the Marsaglia-Tsang shifted shape.
    d = a - 0.3333333333333333          # a - 1/3
    # Precompute its normal-perturbation scale.
    c = 1.0 / c_sqrt(9.0 * d)

    # Repeat until one candidate passes an acceptance test.
    while True:
        # Draw a normal candidate that produces a positive transformed value.
        while True:
            x = _normal(st)
            v = 1.0 + c * x
            if v > 0.0:
                break
        # Cube the positive transformed normal candidate.
        v = v * v * v
        # Draw the independent uniform used by both acceptance tests.
        u = uniform(st)
        # Apply the fast squeeze acceptance test first.
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            res = d * v
            break
        # Apply the full logarithmic acceptance test when needed.
        if c_log(u) < 0.5 * x * x + d * (1.0 - v + c_log(v)):
            res = d * v
            break
    # Return the accepted unit-scale Gamma variate.
    return res

# ── Beta(a, b) via two independent Gamma draws ─────────────────────────────
# Draw a Beta variate as one Gamma value's share of their sum.
cdef inline double _beta(double alpha, double beta_param,
                          RngState *st) noexcept nogil:
    # Reserve the two independent Gamma variates.
    cdef double x, y
    # Draw the numerator using the alpha shape.
    x = _gamma(alpha, st)
    # Draw the complementary component using the beta shape.
    y = _gamma(beta_param, st)
    # Use a neutral midpoint for the theoretically degenerate zero sum.
    if x + y == 0.0:
        return 0.5
    # Normalize the first Gamma variate into a zero-to-one proportion.
    return x / (x + y)


# ── Inline clamp ───────────────────────────────────────────────────────────
# Restrict one native double to an inclusive lower and upper bound.
cdef inline double clamp(double v, double lo, double hi) noexcept nogil:
    # Return the lower bound when the value falls below it.
    if v < lo:
        return lo
    # Return the upper bound when the value exceeds it.
    if v > hi:
        return hi
    # Otherwise preserve the already valid value.
    return v


# ═══════════════════════════════════════════════════════════════════════════
#  Public API — parallel Monte Carlo simulation
# ═══════════════════════════════════════════════════════════════════════════
# Simulate repeated scoring outcomes and return their calibrated mean.
def run_monte_carlo_simulation(off_team_stats, def_team_stats,
                               pace, league_avgs, def_allowed_stats=None,
                               int iterations=10000, model_weights=None,
                               unsigned long long random_seed=0):
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
    model_weights  : array-like   Optional weights in this order:
                                  shot disruption, forced turnovers,
                                  defensive fouls, allowed FT rate,
                                  shot quality, allowed eFG%, DREB%,
                                  lineup plus-minus, score scale,
                                  score intercept
    random_seed    : int          Non-zero seed for reproducible results

    Returns
    -------
    float  Average points scored per simulated game
    """

    # ── Convert inputs to contiguous C-typed memory views ──────────────────
    # Normalize offensive statistics into contiguous double storage.
    cdef double[::1] off = np.ascontiguousarray(off_team_stats, dtype=np.float64)
    # Normalize the opposing team's statistics into the same representation.
    cdef double[::1] dfn = np.ascontiguousarray(def_team_stats, dtype=np.float64)
    # Normalize the five league baseline rates.
    cdef double[::1] lg  = np.ascontiguousarray(league_avgs,  dtype=np.float64)
    # Convert absent defensive factors into an empty optional vector.
    cdef double[::1] allowed = np.ascontiguousarray(
        [] if def_allowed_stats is None else def_allowed_stats,
        dtype=np.float64)
    # Convert absent model weights into an empty optional vector.
    cdef double[::1] weights = np.ascontiguousarray(
        [] if model_weights is None else model_weights,
        dtype=np.float64)
    # Cache optional-vector lengths for cheap native bounds decisions.
    cdef Py_ssize_t allowed_len = allowed.shape[0]
    cdef Py_ssize_t weights_len = weights.shape[0]
    # Convert pace once before entering native no-GIL code.
    cdef double c_pace = float(pace)

    # A mean cannot be calculated from zero or negative draws.
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    # Preserve safe score arithmetic when caller pace is nonpositive.
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
    cdef double shot_disruption_weight, forced_tov_weight
    cdef double defensive_foul_weight, allowed_ft_rate_weight
    cdef double shot_quality_weight, allowed_efg_weight
    cdef double dreb_weight, lineup_plus_minus_weight
    cdef double score_scale, score_intercept

    # Possession outcome probabilities
    cdef double prob_3pt, ft_rate, prob_ns_ft, prob_and1
    cdef double prob_sf2, prob_sf3, prob_initial_shot, miss_rate
    cdef double foul_no_fga_rate

    # Final score context
    cdef double sim_points, lineup_strength_adjustment

    # Beta shape parameters
    cdef double scale, fg2_a, fg2_b, fg3_a, fg3_b, ft_a, ft_b

    # Per-iteration state (automatically thread-private inside prange)
    cdef double game_fg2, game_fg3, game_ft, points = 0.0
    cdef double three_point_reward, two_point_reward
    cdef double shot_reward, retry_probability
    cdef double total_points = 0.0

    # These defaults preserve the production model. The backtest harness can
    # override them without requiring a recompile for every trial.
    # Resolve shot-disruption strength or use the production default.
    shot_disruption_weight = weights[0] if weights_len > 0 else 0.35
    # Resolve forced-turnover strength or use the production default.
    forced_tov_weight = weights[1] if weights_len > 1 else 0.50
    # Resolve defensive-foul strength or use the production default.
    defensive_foul_weight = weights[2] if weights_len > 2 else 0.10
    # Resolve allowed-free-throw-rate strength or use the production default.
    allowed_ft_rate_weight = weights[3] if weights_len > 3 else 0.50
    # Resolve offensive shot-quality strength or use the production default.
    shot_quality_weight = weights[4] if weights_len > 4 else 0.08
    # Resolve allowed-effective-field-goal strength or use the default.
    allowed_efg_weight = weights[5] if weights_len > 5 else 0.45
    # Resolve defensive-rebounding strength or use the production default.
    dreb_weight = weights[6] if weights_len > 6 else 0.60
    # Resolve lineup plus-minus strength or use the production default.
    lineup_plus_minus_weight = weights[7] if weights_len > 7 else 0.10
    # Resolve fitted score scaling while retaining backward compatibility.
    score_scale = weights[8] if weights_len > 8 else 1.0
    # Resolve fitted score offset while retaining backward compatibility.
    score_intercept = weights[9] if weights_len > 9 else 0.0

    # ── Extract offensive stats ────────────────────────────────────────────
    # Clamp made and attempted shooting counts to safe physical bounds.
    off_fgm  = max(0.0, off[1])
    off_fga  = max(1.0, off[2])
    off_fg3m = max(0.0, off[4])
    off_fg3a = max(0.0, off[5])
    off_ftm  = max(0.0, off[7])
    off_fta  = max(0.0, off[8])
    # Clamp possession-ending and rebounding counts to nonnegative values.
    off_tov  = max(0.0, off[16])
    off_oreb = max(0.0, off[10])
    # Clamp assists used as the shot-quality proxy.
    off_ast  = max(0.0, off[13])
    # Preserve signed offensive plus-minus as a lineup-strength signal.
    off_plus_minus = off[19]
    # Derive two-point makes by removing three-pointers from all field goals.
    off_fg2m = max(0.0, off_fgm - off_fg3m)
    # Derive two-point attempts with a positive denominator floor.
    off_fg2a = max(1.0, off_fga - off_fg3a)

    # ── Extract defensive stats ────────────────────────────────────────────
    # Read opponent activity counts with safe denominator/nonnegative bounds.
    def_fga  = max(1.0, dfn[2])
    def_dreb = max(0.0, dfn[11])
    def_stl  = max(0.0, dfn[14])
    def_blk  = max(0.0, dfn[15])
    def_pf   = max(0.0, dfn[17])
    # Preserve signed defensive-team plus-minus for relative lineup strength.
    def_plus_minus = dfn[19]

    # ── League averages ────────────────────────────────────────────────────
    # Use caller league rates when positive, otherwise stable NBA-like values.
    lg_fg_pct   = lg[0] if lg[0] > 0.0 else 0.471
    lg_fg3_pct  = lg[1] if lg[1] > 0.0 else 0.362
    lg_ft_pct   = lg[2] if lg[2] > 0.0 else 0.781
    lg_tov_pct  = lg[3] if lg[3] > 0.0 else 0.133
    lg_oreb_pct = lg[4] if lg[4] > 0.0 else 0.258
    # Define fixed baselines not included in the five-value league vector.
    lg_efg_pct  = 0.545
    lg_fta_rate = 0.250
    # Convert league offensive-rebound rate into defensive-rebound share.
    lg_dreb_pct = 1.0 - lg_oreb_pct

    # ── Offensive derived rates ────────────────────────────────────────────
    # Calculate baseline shooting percentages with league fallbacks.
    off_fg2_pct = off_fg2m / off_fg2a if off_fg2a > 0.0 else lg_fg_pct
    off_fg3_pct = off_fg3m / off_fg3a if off_fg3a > 0.0 else lg_fg3_pct
    off_ft_pct  = off_ftm  / off_fta  if off_fta  > 0.0 else lg_ft_pct

    # Estimate total offensive actions for turnover-rate calculation.
    off_total_actions = off_fga + off_tov + 0.44 * off_fta
    # Calculate offensive turnover rate or use the league baseline.
    off_tov_pct = off_tov / off_total_actions if off_total_actions > 0.0 else lg_tov_pct

    # Calculate missed field goals as potential offensive-rebound chances.
    off_fg_misses = off_fga - off_fgm
    # Calculate offensive-rebound rate or use the league baseline.
    off_oreb_pct  = off_oreb / off_fg_misses if off_fg_misses > 0.0 else lg_oreb_pct

    # Estimate possessions from shots, free throws, turnovers, and rebounds.
    est_possessions = off_fga + 0.44 * off_fta + off_tov - off_oreb
    # Replace implausibly small estimates with supplied or neutral pace.
    if est_possessions <= 1.0:
        est_possessions = pace if pace > 1.0 else 100.0
    # Convert field-goal volume into attempts per possession.
    fga_per_poss = off_fga / est_possessions if est_possessions > 0.0 else 0.88

    # ── Defensive derived rates ────────────────────────────────────────────    
    # Combine defensive and offensive rebounds into matchup rebound chances.
    def_total_reb = def_dreb + off_oreb if (def_dreb + off_oreb) > 0.0 else 1.0
    # Calculate the raw defensive-rebound share from basic box-score inputs.
    def_dreb_pct_raw = def_dreb / def_total_reb
    # Shrink that noisy proxy halfway toward the league baseline.
    def_dreb_pct_proxy = lg_dreb_pct + 0.50 * (def_dreb_pct_raw - lg_dreb_pct)
    # Limit proxy movement to ten percentage points around league average.
    def_dreb_pct_proxy = clamp(def_dreb_pct_proxy, lg_dreb_pct - 0.10, lg_dreb_pct + 0.10)


    # Prefer supplied effective-field-goal percentage allowed when valid.
    if allowed_len > 0 and allowed[0] > 0.0:
        def_efg_allowed = allowed[0]
    else:
        def_efg_allowed = lg_efg_pct

    # Prefer supplied forced-turnover rate when valid.
    if allowed_len > 1 and allowed[1] > 0.0:
        def_tov_forced_pct = allowed[1]
    else:
        def_tov_forced_pct = lg_tov_pct

    # Prefer supplied free-throw rate allowed when valid.
    if allowed_len > 2 and allowed[2] > 0.0:
        def_fta_rate_allowed = allowed[2]
    else:
        def_fta_rate_allowed = lg_fta_rate

    # Prefer supplied defensive-rebound rate, then fall back to the proxy.
    if allowed_len > 3 and allowed[3] > 0.0:
        def_dreb_pct = allowed[3]
    else:
        def_dreb_pct = def_dreb_pct_proxy

    # ── Defensive context ──────────────────────────────────────────────────
    # The offensive inputs are already minutes-weighted and matchup-adjusted.
    # Keep defensive effects modest so we do not double-count the matchup.
    # Combine steals and blocks into a basic disruption-per-attempt signal.
    def_disruption  = (def_stl + def_blk) / def_fga if def_fga > 0.0 else 0.0
    # Define a stable reference disruption rate.
    lg_disruption   = 0.12
    # Express this defense relative to the reference rate.
    disruption_factor = def_disruption / lg_disruption if lg_disruption > 0.0 else 1.0
    # Blend relative disruption according to the fitted weight and safe bounds.
    shot_disruption_factor = clamp(
        1.0 + shot_disruption_weight * (disruption_factor - 1.0),
        0.90, 1.10)

    # Express forced-turnover context relative to the league baseline.
    tov_allowed_factor = def_tov_forced_pct / lg_tov_pct if lg_tov_pct > 0.0 else 1.0
    # Blend and constrain the turnover effect.
    tov_allowed_factor = clamp(
        1.0 + forced_tov_weight * (tov_allowed_factor - 1.0),
        0.90, 1.10)
    # Combine shot and turnover disruption into one bounded context factor.
    disruption_factor = clamp(shot_disruption_factor * tov_allowed_factor, 0.88, 1.14)

    # Compare defensive fouls with a typical per-game baseline.
    def_foul_factor = def_pf / 18.5 if def_pf > 0.0 else 1.0
    # Apply the fitted basic-foul weight within conservative bounds.
    def_foul_factor = clamp(
        1.0 + defensive_foul_weight * (def_foul_factor - 1.0),
        0.96, 1.04)
    # Incorporate the more direct supplied free-throw rate allowed.
    def_foul_factor = def_foul_factor * (
        def_fta_rate_allowed / lg_fta_rate if lg_fta_rate > 0.0 else 1.0)
    # Apply its fitted weight and final plausible bounds.
    def_foul_factor = clamp(
        1.0 + allowed_ft_rate_weight * (def_foul_factor - 1.0),
        0.88, 1.12)

    # Use assist share as a simple offensive shot-quality signal.
    shot_quality_factor = off_ast / off_fgm if off_fgm > 0.0 else 0.60
    # Blend its deviation from the reference assist share.
    shot_quality_factor = clamp(
        1.0 + shot_quality_weight * (shot_quality_factor - 0.60),
        0.96, 1.04)

    # Express allowed effective shooting relative to league context.
    efg_allowed_factor = def_efg_allowed / lg_efg_pct if lg_efg_pct > 0.0 else 1.0
    # Blend the fitted effect and constrain its scoring influence.
    efg_allowed_factor = clamp(
        1.0 + allowed_efg_weight * (efg_allowed_factor - 1.0),
        0.93, 1.07)

    # ── Adjusted rates ─────────────────────────────────────────────────────
    # Adjust two-point accuracy for shot quality and opponent effective defense.
    adj_fg2_pct = off_fg2_pct * shot_quality_factor * efg_allowed_factor / shot_disruption_factor
    # Apply a softer shot-quality effect to three-point accuracy.
    adj_fg3_pct = off_fg3_pct * (0.5 + 0.5 * shot_quality_factor) * efg_allowed_factor / shot_disruption_factor
    # Adjust turnover probability by the combined defensive disruption context.
    adj_tov_pct = off_tov_pct * disruption_factor

    # Compare allowed offensive rebounds to the league offensive-rebound rate.
    # Convert defensive-rebound share into relative offensive-rebound allowance.
    dreb_allowed_factor = (1.0 - def_dreb_pct) / lg_oreb_pct if lg_oreb_pct > 0.0 else 1.0
    # Blend and constrain the fitted rebounding effect.
    dreb_allowed_factor = clamp(
        1.0 + dreb_weight * (dreb_allowed_factor - 1.0),
        0.70, 1.10)

    # Apply defense context only when the league denominator is meaningful.
    if lg_oreb_pct > 0.0:
        adj_oreb_pct = off_oreb_pct * dreb_allowed_factor
    else:
        adj_oreb_pct = off_oreb_pct

    # Constrain adjusted rates to plausible single-game ranges.
    adj_fg2_pct = clamp(adj_fg2_pct, 0.25, 0.65)
    adj_fg3_pct = clamp(adj_fg3_pct, 0.20, 0.50)
    adj_tov_pct = clamp(adj_tov_pct, 0.05, 0.25)
    adj_oreb_pct = clamp(adj_oreb_pct, 0.10, 0.45)
    off_ft_pct   = clamp(off_ft_pct, 0.50, 0.95)

    # ── Possession outcome probabilities ───────────────────────────────────
    # Calculate historical shot mix and free-throw volume.
    prob_3pt   = off_fg3a / off_fga if off_fga > 0.0 else 0.35
    ft_rate    = off_fta  / off_fga if off_fga > 0.0 else 0.25
    # Keep shot mix and defense-adjusted foul volume within plausible ranges.
    prob_3pt   = clamp(prob_3pt, 0.05, 0.65)
    ft_rate    = clamp(ft_rate * def_foul_factor, 0.05, 0.60)
    # Split free-throw rate into non-shooting, and-one, and shooting-foul events.
    prob_ns_ft = clamp(0.44 * ft_rate * 0.18, 0.005, 0.060)
    prob_and1  = clamp(ft_rate * 0.10, 0.005, 0.045)
    prob_sf2   = clamp(ft_rate * 0.62, 0.035, 0.260)
    prob_sf3   = clamp(ft_rate * 0.14, 0.005, 0.075)

    # Average adjusted two- and three-point miss probabilities by shot mix.
    miss_rate = 1.0 - (prob_3pt * adj_fg3_pct + (1.0 - prob_3pt) * adj_fg2_pct)
    # Prevent extreme inputs from producing unstable rebound retries.
    miss_rate = clamp(miss_rate, 0.25, 0.75)
    # Discount initial attempts to account for extra shots after offensive rebounds.
    extra_shot_factor = 1.0 - miss_rate * adj_oreb_pct
    # Keep the extra-shot correction away from zero.
    if extra_shot_factor <= 0.20:
        extra_shot_factor = 0.20
    # Estimate shooting fouls that consume possessions without recorded attempts.
    foul_no_fga_rate = prob_3pt * prob_sf3 + (1.0 - prob_3pt) * prob_sf2
    # Bound that adjustment to a plausible share of possessions.
    foul_no_fga_rate = clamp(foul_no_fga_rate, 0.02, 0.24)
    # Recover the chance a possession begins a field-goal attempt process.
    prob_initial_shot = fga_per_poss * extra_shot_factor / (1.0 - foul_no_fga_rate)
    # Keep initial-shot probability within plausible possession bounds.
    prob_initial_shot = clamp(prob_initial_shot, 0.50, 0.92)

    # Preserve probability mass when primary outcomes would exceed one.
    if adj_tov_pct + prob_ns_ft + prob_initial_shot > 0.995:
        prob_initial_shot = 0.995 - adj_tov_pct - prob_ns_ft
        # Retain a reasonable minimum even for extreme turnover/foul inputs.
        if prob_initial_shot < 0.45:
            prob_initial_shot = 0.45

    # ── Beta distribution shape parameters ────────────────────────────────
    # Scale historical volume so beta variation remains game-like.
    scale = max(1.0, off_fga / 65.0)
    # Convert made and missed two-point counts into beta shapes.
    fg2_a = max(2.0, off_fg2m / scale)
    fg2_b = max(2.0, (off_fg2a - off_fg2m) / scale)
    # Convert made and missed three-point counts into beta shapes.
    fg3_a = max(2.0, off_fg3m / scale)
    fg3_b = max(2.0, (off_fg3a - off_fg3m) / scale)
    # Convert made and missed free-throw counts into beta shapes.
    ft_a  = max(2.0, off_ftm / scale)
    ft_b  = max(2.0, (off_fta - off_ftm) / scale)

    # ══════════════════════════════════════════════════════════════════════
    #  Per-thread RNG initialisation
    # ══════════════════════════════════════════════════════════════════════
    # Ask OpenMP for the maximum number of worker threads.
    cdef int nthreads = omp_get_max_threads()
    # Allocate one padded random-state record per worker.
    cdef RngState *rng_states = <RngState *>malloc(
        nthreads * sizeof(RngState))
    # Raise immediately if native state allocation fails.
    if rng_states == NULL:
        raise MemoryError("Failed to allocate per-thread RNG states")

    # Each thread gets a unique seed drawn from the already-seeded libc RNG
    # Declare initialization index and shared base seed.
    cdef int j
    cdef unsigned long long base_seed
    # Prefer the caller's explicit reproducible seed.
    if random_seed != 0:
        base_seed = random_seed
    # Otherwise combine libc draws into a wider nondeterministic seed.
    else:
        base_seed = (<unsigned long long>rand()
                     | (<unsigned long long>rand() << 15)
                     | (<unsigned long long>rand() << 30)
                     | (<unsigned long long>rand() << 45))
    # Initialize every thread with a well-separated deterministic offset.
    for j in range(nthreads):
        rng_init(&rng_states[j], base_seed
                 + <unsigned long long>j
                 * <unsigned long long>0x9E3779B97F4A7C15)

    # Reserve per-iteration access to the current thread's state and id.
    cdef RngState *my_rng
    cdef int tid

    # ══════════════════════════════════════════════════════════════════════
    #  Main simulation loop — OpenMP parallel, GIL released
    #  Cython auto-detects `total_points += points` as a reduction.
    #  All other per-iteration variables are automatically thread-private.
    # ══════════════════════════════════════════════════════════════════════
    # Release the GIL for the complete independent simulation workload.
    with nogil:
        # Divide deterministic iteration ranges among OpenMP threads.
        for i in prange(iterations, schedule='static'):

            # Pick this thread's private RNG state
            # Resolve the active worker's numeric id.
            tid = omp_get_thread_num()
            # Point at only that worker's padded RNG state.
            my_rng = &rng_states[tid]

            # Sample per-game percentages from Beta distributions
            # Draw independent two-point, three-point, and free-throw accuracy.
            game_fg2 = _beta(fg2_a, fg2_b, my_rng)
            game_fg3 = _beta(fg3_a, fg3_b, my_rng)
            game_ft  = _beta(ft_a,  ft_b,  my_rng)

            # Apply defensive adjustment
            # Scale sampled accuracy from offensive baseline to matchup context.
            if off_fg2_pct > 0.0:
                game_fg2 = game_fg2 * (adj_fg2_pct / off_fg2_pct)
            if off_fg3_pct > 0.0:
                game_fg3 = game_fg3 * (adj_fg3_pct / off_fg3_pct)

            # Bound sampled percentages after matchup scaling.
            game_fg2 = clamp(game_fg2, 0.20, 0.70)
            game_fg3 = clamp(game_fg3, 0.15, 0.55)
            game_ft  = clamp(game_ft,  0.40, 0.98)

            # Integrate out possession-level randomness. The function only
            # returns a mean, so sampling every event adds variance and work
            # without changing its conditional expected value.
            # Calculate expected points from a three-point shot process.
            three_point_reward = (
                prob_sf3 * 3.0 * game_ft
                + (1.0 - prob_sf3) * game_fg3
                * (3.0 + prob_and1 * game_ft))
            # Calculate expected points from a two-point shot process.
            two_point_reward = (
                prob_sf2 * 2.0 * game_ft
                + (1.0 - prob_sf2) * game_fg2
                * (2.0 + prob_and1 * game_ft))
            # Weight both rewards by the offense's shot mix.
            shot_reward = (
                prob_3pt * three_point_reward
                + (1.0 - prob_3pt) * two_point_reward)

            # An offensive rebound retries the same shot process, giving a
            # geometric series with multiplier retry_probability.
            # Calculate the chance of a missed, non-fouled shot being rebounded.
            retry_probability = adj_oreb_pct * (
                prob_3pt * (1.0 - prob_sf3) * (1.0 - game_fg3)
                + (1.0 - prob_3pt) * (1.0 - prob_sf2)
                * (1.0 - game_fg2))
            # Convert per-possession expected reward into expected game points.
            points = <double>c_pace * (
                prob_ns_ft * 2.0 * game_ft
                + prob_initial_shot * shot_reward
                / (1.0 - retry_probability))

            # Add this draw through Cython's OpenMP reduction variable.
            total_points += points

    # Release native RNG storage after all worker threads have finished.
    free(rng_states)
    # Average total expected points across all Monte Carlo draws.
    sim_points = total_points / <double>iterations

    # The simulation already generates a realistic single-game total.
    # Do not pull it back to season/matchup average scoring; that made low-
    # scoring Finals-style games drift too high.  Plus-minus is used only as a
    # small, clamped lineup-strength signal to help the two independent team
    # calls preserve the expected winner.
    # Compare offensive and defensive plus-minus through the fitted small weight.
    lineup_strength_adjustment = clamp(
        lineup_plus_minus_weight * (off_plus_minus - def_plus_minus),
        -3.5, 3.5)
    # Apply lineup context followed by fitted global score calibration.
    sim_points = score_scale * (
        sim_points + lineup_strength_adjustment
    ) + score_intercept
    # Scores cannot be negative even under extreme fitted calibration.
    if sim_points < 0.0:
        sim_points = 0.0

    # Return the final average score estimate as a Python float.
    return sim_points
