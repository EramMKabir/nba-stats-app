from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np
import os
import sys

# ── OpenMP flags (macOS with Homebrew libomp) ──────────────────────────────
# Apple Clang does not ship OpenMP headers/libraries.  If Homebrew's libomp
# is installed we add the include/lib paths and the -Xpreprocessor -fopenmp
# flags that Apple's compiler driver requires.  On Linux the same -fopenmp
# flag works out of the box with GCC.
omp_prefix = "/opt/homebrew/opt/libomp"
omp_compile_args = []
omp_link_args = []
omp_include_dirs = []
omp_library_dirs = []

if sys.platform == "darwin":
    if os.path.isdir(omp_prefix):
        omp_compile_args = ["-Xpreprocessor", "-fopenmp"]
        omp_link_args = ["-Xpreprocessor", "-fopenmp", "-lomp"]
        omp_include_dirs = [os.path.join(omp_prefix, "include")]
        omp_library_dirs = [os.path.join(omp_prefix, "lib")]
    # If libomp is not installed, prange will silently fall back to serial
    # execution — print a warning so the user knows.
    else:
        print(
            "WARNING: libomp not found at /opt/homebrew/opt/libomp.  "
            "OpenMP parallelism will be DISABLED (serial fallback).  "
            "Install with:  brew install libomp"
        )
else:
    omp_compile_args = ["-fopenmp"]
    omp_link_args = ["-fopenmp"]

# ══════════════════════════════════════════════════════════════════════════
#  Extension definitions
# ══════════════════════════════════════════════════════════════════════════

compiler_directives = {
    "boundscheck": False,
    "wraparound": False,
    "nonecheck": False,
    "cdivision": True,
    "language_level": 3,
    "initializedcheck": False,
}

extensions = [
    # ── nba_stat_calculator ──────────────────────────────────────────────
    # Uses prange() for the per-player parallel loop.
    Extension(
        "nba_stat_calculator",
        ["nba_stat_calculator.pyx"],
        include_dirs=[np.get_include()] + omp_include_dirs,
        library_dirs=omp_library_dirs,
        extra_compile_args=[
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
            "-Wextra",
            "-g",
            "-O2",
        ] + omp_compile_args,
        extra_link_args=omp_link_args,
    ),

    # ── mc_sim ───────────────────────────────────────────────────────────
    # Monte Carlo simulation — 10 000-iteration prange loop with per-thread
    # xorshift64* RNG states for lock-free, race-free parallelism.
    Extension(
        "mc_sim",
        ["mc_sim.pyx"],
        include_dirs=[np.get_include()] + omp_include_dirs,
        library_dirs=omp_library_dirs,
        extra_compile_args=[
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
            "-Wextra",
            "-g",
            "-O2",
        ] + omp_compile_args,
        extra_link_args=omp_link_args,
    ),
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives=compiler_directives,
        annotate=True,
        gdb_debug=True,
    ),
    include_dirs=[np.get_include()],
)
