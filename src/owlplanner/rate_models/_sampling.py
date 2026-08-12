"""
Correlated normal draws that a seed can actually reproduce.

``Generator.multivariate_normal`` factorizes the covariance by SVD unless told
otherwise, and an SVD is only determined up to conventions that differ between LAPACK
builds. Two machines given the same seed and the same covariance therefore draw
different numbers -- not by a sign, but entirely -- so a pinned ``rate_seed`` reproduces
a series only on the machine that produced it.

A Cholesky factor of a positive-definite matrix is unique, so asking for that instead
makes a seeded series reproducible anywhere. It is what ``vector_ar`` and ``garch_dcc``
already do by hand. The one thing it cannot do is factorize a singular covariance,
which SVD handles; a component estimated from very few observations can land there, so
this falls back rather than failing, and says so.

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import warnings

import numpy as np


def multivariate_normal(rng, mean, cov, size=None):
    """Draw correlated normals reproducibly across platforms.

    Drop-in for ``rng.multivariate_normal(mean, cov, size)``. Uses the Cholesky factor,
    which is unique, and falls back to the default factorization with a warning when the
    covariance is not positive definite.
    """
    try:
        return rng.multivariate_normal(mean, cov, size=size, method="cholesky")
    except np.linalg.LinAlgError:
        warnings.warn(
            "Covariance is not positive definite, so the correlated draw falls back to an "
            "SVD factorization. The series is still valid, but a given seed will only "
            "reproduce it on this machine.",
            RuntimeWarning,
            stacklevel=2,
        )
        return rng.multivariate_normal(mean, cov, size=size, method="svd")
