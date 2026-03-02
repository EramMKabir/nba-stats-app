from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

extensions = [
    Extension("nba_stat_calculator", ["nba_stat_calculator.pyx"], include_dirs=[np.get_include()], extra_compile_args=['-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION', '-Wextra', '-g', '-O2'])
]

setup(
    ext_modules=cythonize(extensions,
        compiler_directives={
        "boundscheck": False,
        "wraparound": False,
        "nonecheck": False,
        "cdivision": True,
        "language_level": 3,
        "initializedcheck": False,
    },annotate=True,
    gdb_debug=True),
    include_dirs=[np.get_include()],
)
