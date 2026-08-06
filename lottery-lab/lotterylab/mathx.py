"""Special functions and statistical distributions, pure standard library.

Everything in this module is implemented from scratch so that the whole
toolkit runs on a bare Python install with no ``pip install`` step.  The
test-suite cross-checks every function here against SciPy to a tight
tolerance, so the lack of dependencies costs no accuracy.

Algorithms follow the standard references (Numerical Recipes for the
incomplete gamma and beta functions, Acklam's rational approximation with
one Halley refinement for the normal quantile, Stephens' correction for
the Kolmogorov distribution).
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

__all__ = [
    "gammainc_lower",
    "gammainc_upper",
    "chi2_sf",
    "chi2_cdf",
    "norm_cdf",
    "norm_sf",
    "norm_ppf",
    "betainc",
    "binom_pmf",
    "binom_cdf",
    "binom_sf",
    "binom_test",
    "poisson_pmf",
    "poisson_cdf",
    "poisson_sf",
    "ks_sf",
    "benjamini_hochberg",
    "wilson_interval",
    "logsumexp",
    "log_binom",
    "mean",
    "variance",
    "stdev",
    "entropy_bits",
]

_EPS = 3.0e-16
_FPMIN = 1.0e-300
_MAXIT = 500


# --------------------------------------------------------------------------
# Incomplete gamma  ->  chi-square, Poisson
# --------------------------------------------------------------------------


def _gser(a: float, x: float) -> float:
    """Lower regularised incomplete gamma P(a, x) by series expansion."""
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(_MAXIT):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * _EPS:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a: float, x: float) -> float:
    """Upper regularised incomplete gamma Q(a, x) by continued fraction."""
    b = x + 1.0 - a
    c = 1.0 / _FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, _MAXIT + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = b + an / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def gammainc_lower(a: float, x: float) -> float:
    """Regularised lower incomplete gamma ``P(a, x)``."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammainc_lower requires a > 0 and x >= 0")
    if x == 0.0:
        return 0.0
    if x < a + 1.0:
        return _gser(a, x)
    return 1.0 - _gcf(a, x)


def gammainc_upper(a: float, x: float) -> float:
    """Regularised upper incomplete gamma ``Q(a, x) = 1 - P(a, x)``."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammainc_upper requires a > 0 and x >= 0")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


def chi2_sf(x: float, df: int) -> float:
    """Upper tail of the chi-square distribution: ``P(X > x)``.

    This is the p-value for a chi-square goodness-of-fit statistic.
    """
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if x <= 0.0:
        return 1.0
    return gammainc_upper(df / 2.0, x / 2.0)


def chi2_cdf(x: float, df: int) -> float:
    """Lower tail of the chi-square distribution: ``P(X <= x)``."""
    return 1.0 - chi2_sf(x, df)


# --------------------------------------------------------------------------
# Normal distribution
# --------------------------------------------------------------------------


def norm_cdf(z: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Standard normal cumulative distribution function."""
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return 0.5 * math.erfc(-(z - mu) / (sigma * math.sqrt(2.0)))


def norm_sf(z: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Standard normal survival function ``P(Z > z)``."""
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return 0.5 * math.erfc((z - mu) / (sigma * math.sqrt(2.0)))


# Acklam's rational approximation coefficients.
_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
      1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
      6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
      -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
      3.754408661907416e00)


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (the probit / quantile function)."""
    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError("p must lie in [0, 1]")

    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
            (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)

    # One Halley step lifts the approximation to full double precision.
    err = norm_cdf(x) - p
    u = err * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


# --------------------------------------------------------------------------
# Incomplete beta  ->  binomial tails
# --------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function ``I_x(a, b)``."""
    if x < 0.0 or x > 1.0:
        raise ValueError("x must lie in [0, 1]")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + b * math.log1p(-x) + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


# --------------------------------------------------------------------------
# Binomial
# --------------------------------------------------------------------------


def log_binom(n: int, k: int) -> float:
    """Natural log of the binomial coefficient ``C(n, k)``."""
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_pmf(k: int, n: int, p: float) -> float:
    """Binomial probability mass ``P(X = k)``."""
    if k < 0 or k > n:
        return 0.0
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    return math.exp(log_binom(n, k) + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_cdf(k: int, n: int, p: float) -> float:
    """Binomial cumulative probability ``P(X <= k)``.

    Uses the identity ``P(X <= k) = I_{1-p}(n-k, k+1)`` so the cost does not
    grow with ``n``.
    """
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return betainc(n - k, k + 1, 1.0 - p)


def binom_sf(k: int, n: int, p: float) -> float:
    """Binomial survival function ``P(X > k)``."""
    return 1.0 - binom_cdf(k, n, p)


def binom_test(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial test p-value.

    Uses the standard "sum of all outcomes no more likely than the observed
    one" definition, matching ``scipy.stats.binomtest(..., alternative='two-sided')``.
    """
    if n == 0:
        return 1.0
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must lie in [0, 1]")
    if p == 0.0:
        return 1.0 if k == 0 else 0.0
    if p == 1.0:
        return 1.0 if k == n else 0.0

    observed = binom_pmf(k, n, p)
    # Guard against floating-point ties being excluded by strict comparison.
    tol = 1.0 + 1.0e-7
    mode = int(math.floor((n + 1) * p))

    if k == mode:
        return 1.0

    if k < mode:
        # Find the largest j > mode whose pmf is still <= observed.
        lo, hi = mode, n
        if binom_pmf(n, n, p) > observed * tol:
            other = n + 1
        else:
            while lo < hi:
                mid = (lo + hi) // 2
                if binom_pmf(mid, n, p) > observed * tol:
                    lo = mid + 1
                else:
                    hi = mid
            other = lo
        total = binom_cdf(k, n, p) + binom_sf(other - 1, n, p)
    else:
        # Find the smallest j < mode whose pmf is still <= observed.
        lo, hi = 0, mode
        if binom_pmf(0, n, p) > observed * tol:
            other = -1
        else:
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if binom_pmf(mid, n, p) > observed * tol:
                    hi = mid - 1
                else:
                    lo = mid
            other = lo
        total = binom_cdf(other, n, p) + binom_sf(k - 1, n, p)

    return min(1.0, max(0.0, total))


# --------------------------------------------------------------------------
# Poisson
# --------------------------------------------------------------------------


def poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass ``P(X = k)``."""
    if k < 0:
        return 0.0
    if lam == 0.0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def poisson_cdf(k: int, lam: float) -> float:
    """Poisson cumulative probability ``P(X <= k)``."""
    if k < 0:
        return 0.0
    if lam == 0.0:
        return 1.0
    return gammainc_upper(k + 1, lam)


def poisson_sf(k: int, lam: float) -> float:
    """Poisson survival function ``P(X > k)``."""
    if k < 0:
        return 1.0
    if lam == 0.0:
        return 0.0
    return gammainc_lower(k + 1, lam)


# --------------------------------------------------------------------------
# Kolmogorov-Smirnov
# --------------------------------------------------------------------------


def ks_sf(d: float, n: int) -> float:
    """Asymptotic p-value for a one-sample KS statistic ``d`` with ``n`` points.

    Applies Stephens' small-sample correction, which is accurate to about
    three decimal places for ``n >= 5``.
    """
    if d <= 0.0:
        return 1.0
    if d >= 1.0:
        return 0.0
    en = math.sqrt(n)
    lam = (en + 0.12 + 0.11 / en) * d
    if lam < 0.2:
        return 1.0
    total = 0.0
    for j in range(1, 101):
        term = 2.0 * (-1.0) ** (j - 1) * math.exp(-2.0 * j * j * lam * lam)
        total += term
        if abs(term) < 1.0e-12 * abs(total) or abs(term) < 1.0e-15:
            break
    return min(1.0, max(0.0, total))


# --------------------------------------------------------------------------
# Multiple testing and intervals
# --------------------------------------------------------------------------


def benjamini_hochberg(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg FDR-adjusted p-values (q-values).

    Running one test per ball across a 49-ball lottery means roughly two
    "significant" results at alpha = 0.05 purely by chance.  Adjusting for
    that is the difference between an audit and a fishing expedition.
    """
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        idx = order[rank]
        value = pvalues[idx] * n / (rank + 1)
        prev = min(prev, value)
        adjusted[idx] = min(1.0, prev)
    return adjusted


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.

    Preferred over the normal approximation because it stays inside [0, 1]
    and behaves sensibly for the small counts typical of per-ball analysis.
    """
    if trials == 0:
        return (0.0, 1.0)
    z = norm_ppf(1.0 - (1.0 - confidence) / 2.0)
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = (phat + z * z / (2 * trials)) / denom
    half = z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def logsumexp(values: Iterable[float]) -> float:
    """Numerically stable ``log(sum(exp(v)))``."""
    vals = [v for v in values if v > -math.inf]
    if not vals:
        return -math.inf
    peak = max(vals)
    return peak + math.log(sum(math.exp(v - peak) for v in vals))


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean."""
    if not values:
        raise ValueError("mean of an empty sequence")
    return sum(values) / len(values)


def variance(values: Sequence[float], sample: bool = True) -> float:
    """Variance, sample (``n-1``) by default."""
    n = len(values)
    if n < 2:
        return 0.0
    mu = mean(values)
    ss = sum((v - mu) ** 2 for v in values)
    return ss / (n - 1 if sample else n)


def stdev(values: Sequence[float], sample: bool = True) -> float:
    """Standard deviation."""
    return math.sqrt(variance(values, sample))


def entropy_bits(counts: Sequence[float]) -> float:
    """Shannon entropy of a count vector, in bits."""
    total = sum(counts)
    if total <= 0:
        return 0.0
    acc = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            acc -= p * math.log2(p)
    return acc
