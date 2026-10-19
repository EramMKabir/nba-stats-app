# setup.py

# Function: Build the project's Cython extension modules with NumPy and
# optional OpenMP support.

# Inputs: The current platform, the optional LIBOMP_PREFIX environment
# variable, and the three local .pyx source files.

# Output: Compiled extension modules for the NBA stat calculator, Monte Carlo
# simulator, and backtest API.

# Libraries

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
# Start with no detected OpenMP installation on platforms that do not need one.
omp_prefix = None
# Collect extra compiler flags without mutating an Extension after creation.
omp_compile_args = []
# Collect the matching linker flags for the detected OpenMP runtime.
omp_link_args = []
# Collect any nonstandard directory that contains the OpenMP headers.
omp_include_dirs = []
# Collect any nonstandard directory that contains the OpenMP library.
omp_library_dirs = []

# Apple Clang needs an external libomp installation and macOS-specific flags.
if sys.platform == "darwin":
    # Check an explicit override first, followed by standard Homebrew prefixes.
    omp_prefix_candidates = [
        # Let developers point the build at a custom libomp installation.
        os.environ.get("LIBOMP_PREFIX"),
        # Use the default Apple Silicon Homebrew prefix when its header exists.
        "/opt/homebrew/opt/libomp",
        # Fall back to the Intel macOS Homebrew prefix.
        "/usr/local/opt/libomp",
    ]
    # Select the first candidate that actually contains the required header.
    omp_prefix = next(
        (path for path in omp_prefix_candidates
         if path and os.path.isfile(os.path.join(path, "include", "omp.h"))),
        # Leave OpenMP disabled when none of the candidates is usable.
        None,
    )

    # Configure Apple Clang only after a valid libomp prefix is confirmed.
    if omp_prefix is not None:
        # Forward the OpenMP flag through Apple's compiler preprocessor.
        omp_compile_args = ["-Xpreprocessor", "-fopenmp"]
        # Enable OpenMP at link time and link against the libomp runtime.
        omp_link_args = ["-Xpreprocessor", "-fopenmp", "-lomp"]
        # Add the detected libomp header directory to compiler searches.
        omp_include_dirs = [os.path.join(omp_prefix, "include")]
        # Add the detected libomp binary directory to linker searches.
        omp_library_dirs = [os.path.join(omp_prefix, "lib")]
    # If libomp is not installed, prange will silently fall back to serial
    # execution — print a warning so the user knows.
    else:
        # Explain why compiled prange loops will execute serially on this host.
        print(
            "WARNING: libomp was not found.  "
            "OpenMP parallelism will be DISABLED (serial fallback).  "
            "Install with:  brew install libomp"
        )
# GCC-compatible platforms generally provide OpenMP through one shared flag.
else:
    # Enable OpenMP compilation on non-macOS platforms.
    omp_compile_args = ["-fopenmp"]
    # Enable and link the OpenMP runtime on non-macOS platforms.
    omp_link_args = ["-fopenmp"]

# ══════════════════════════════════════════════════════════════════════════
#  Extension definitions
# ══════════════════════════════════════════════════════════════════════════

# Apply the same safety and performance directives to every Cython module.
compiler_directives = {
    # Trust index validity so Cython omits bounds checks in hot loops.
    "boundscheck": False,
    # Disable negative-index wrapping to remove another per-access branch.
    "wraparound": False,
    # Skip generated None checks for typed values used by the extensions.
    "nonecheck": False,
    # Use native C division semantics in performance-critical calculations.
    "cdivision": True,
    # Compile all source using Python 3 language rules.
    "language_level": 3,
    # Avoid generated checks for initialized C local variables.
    "initializedcheck": False,
}

# Describe every native module that setuptools should compile.
extensions = [
    # ── nba_stat_calculator ──────────────────────────────────────────────
    # Uses prange() for the per-player parallel loop.
    Extension(
        # Publish the compiled module under the name imported by Python code.
        "nba_stat_calculator",
        # Compile the stat calculator's Cython source file.
        ["nba_stat_calculator.pyx"],
        # Expose NumPy plus any detected OpenMP headers to the compiler.
        include_dirs=[np.get_include()] + omp_include_dirs,
        # Expose the optional libomp directory to the linker.
        library_dirs=omp_library_dirs,
        # Combine common diagnostics and optimization with OpenMP flags.
        extra_compile_args=[
            # Prevent use of NumPy's deprecated C API.
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
            # Enable additional compiler warnings.
            "-Wextra",
            # Retain debug symbols for native debugging.
            "-g",
            # Use balanced optimization for the larger stat-calculation module.
            "-O2",
        ] + omp_compile_args,
        # Link OpenMP only when the current platform supports it.
        extra_link_args=omp_link_args,
    ),

    # ── mc_sim ───────────────────────────────────────────────────────────
    # Monte Carlo simulation — 10 000-iteration prange loop with per-thread
    # xorshift64* RNG states for lock-free, race-free parallelism.
    Extension(
        # Publish the simulator under the module name used by the API.
        "mc_sim",
        # Compile the Monte Carlo engine's Cython source file.
        ["mc_sim.pyx"],
        # Provide NumPy and OpenMP header search paths.
        include_dirs=[np.get_include()] + omp_include_dirs,
        # Provide the optional OpenMP library search path.
        library_dirs=omp_library_dirs,
        # Favor maximum optimization for the simulation's tight numeric loops.
        extra_compile_args=[
            # Prevent use of NumPy's deprecated C API.
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
            # Enable additional compiler warnings.
            "-Wextra",
            # Preserve symbols for diagnosing native failures.
            "-g",
            # Apply aggressive optimization to repeated simulation work.
            "-O3",
        ] + omp_compile_args,
        # Link the OpenMP runtime whenever it was enabled above.
        extra_link_args=omp_link_args,
    ),

    # API-specific historical aggregation and parallel weight search.
    Extension(
        # Publish native aggregation helpers under the API's import name.
        "backtest_api",
        # Compile the API bridge's Cython implementation.
        ["backtest_api.pyx"],
        # Make NumPy and optional OpenMP headers available.
        include_dirs=[np.get_include()] + omp_include_dirs,
        # Make the optional OpenMP library available to the linker.
        library_dirs=omp_library_dirs,
        # Optimize the aggregation loops while retaining useful diagnostics.
        extra_compile_args=[
            # Prevent use of NumPy's deprecated C API.
            "-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION",
            # Enable additional compiler warnings.
            "-Wextra",
            # Retain native debug symbols.
            "-g",
            # Apply aggressive optimization to aggregation and tuning helpers.
            "-O3",
            # Suppress false-positive initialization warnings from generated C.
            "-Wno-uninitialized",
        ] + omp_compile_args,
        # Link against OpenMP when the runtime was detected.
        extra_link_args=omp_link_args,
    ),
]

# Hand the configured extensions to setuptools for the active build command.
setup(
    # Translate the .pyx files using the shared compiler directives.
    ext_modules=cythonize(
        # Build each extension definition declared above.
        extensions,
        # Apply uniform Cython safety and optimization settings.
        compiler_directives=compiler_directives,
        # Generate annotated HTML that highlights Python interaction overhead.
        annotate=True,
        # Emit Cython debug metadata for native debuggers.
        gdb_debug=True,
    ),
    # Also expose NumPy headers to setuptools' overall build configuration.
    include_dirs=[np.get_include()],
)
