"""Validation tests for engine.stats. References are hand calculations and table values:
t(0.975, 4 dof) = 2.7764451052 (Student-t table), classic data set 2,4,4,4,5,5,7,9
(mean 5, population variance 4), and the MATLAB quantile convention ((i - 0.5)/n)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine import stats

CLASSIC = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
X5 = [1.0, 2.0, 3.0, 4.0, 5.0]
T975_4 = 2.7764451052


def test_basic_moments() -> None:
    assert stats.mean(CLASSIC) == pytest.approx(5.0, abs=1e-15)
    assert stats.var(CLASSIC, ddof=0) == pytest.approx(4.0, abs=1e-14)
    assert stats.std(CLASSIC, ddof=0) == pytest.approx(2.0, abs=1e-14)
    assert stats.var(CLASSIC) == pytest.approx(32.0 / 7.0, abs=1e-14)  # sample, ddof=1 default
    assert stats.std(CLASSIC) == pytest.approx(math.sqrt(32.0 / 7.0), abs=1e-14)
    assert stats.rms([3.0, 4.0]) == pytest.approx(math.sqrt(12.5), abs=1e-14)
    assert stats.sem(X5) == pytest.approx(math.sqrt(2.5) / math.sqrt(5), abs=1e-14)


def test_median_odd_even() -> None:
    assert stats.median([3.0, 1.0, 2.0]) == 2.0
    assert stats.median([4.0, 1.0, 3.0, 2.0]) == 2.5


def test_skewness_kurtosis_hand_values() -> None:
    # [0,0,0,4]: mean 1, m2 = 3, m3 = 6, m4 = 21
    assert stats.skewness([0.0, 0.0, 0.0, 4.0]) == pytest.approx(6.0 / 3.0**1.5, abs=1e-14)
    assert stats.kurtosis([0.0, 0.0, 0.0, 4.0]) == pytest.approx(21.0 / 9.0, abs=1e-14)
    assert stats.skewness(X5) == pytest.approx(0.0, abs=1e-14)
    assert stats.kurtosis(X5) == pytest.approx(1.7, abs=1e-14)  # m4 = 6.8, m2 = 2


def test_quantile_methods() -> None:
    assert stats.quantile(X5, 0.25) == pytest.approx(2.0, abs=1e-14)  # R-7
    assert stats.quantile(X5, 0.25, method="matlab") == pytest.approx(1.75, abs=1e-14)
    assert stats.quantile(X5, 0.5, method="matlab") == pytest.approx(3.0, abs=1e-14)
    assert stats.quantile(X5, 0.02, method="matlab") == 1.0  # flat before first point
    assert stats.quantile(X5, 1.0) == 5.0
    out = stats.quantile(X5, [0.0, 0.5, 1.0])
    np.testing.assert_allclose(out, [1.0, 3.0, 5.0])
    assert stats.iqr(X5) == pytest.approx(2.0, abs=1e-14)  # 4 - 2


def test_zscore() -> None:
    z = stats.zscore(X5)
    assert z.mean() == pytest.approx(0.0, abs=1e-14)
    assert np.std(z, ddof=1) == pytest.approx(1.0, abs=1e-14)


def test_summary() -> None:
    s = stats.summary(X5)
    assert (s.n, s.min, s.q1, s.median, s.q3, s.max) == (5, 1.0, 2.0, 3.0, 4.0, 5.0)
    assert s.mean == pytest.approx(3.0) and s.std == pytest.approx(math.sqrt(2.5))


def test_histogram() -> None:
    x = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
    counts, edges = stats.histogram(x, 4)
    np.testing.assert_array_equal(counts, [1, 2, 3, 4])
    np.testing.assert_allclose(edges, [1.0, 1.75, 2.5, 3.25, 4.0])
    c2, _ = stats.histogram(x, [0.0, 2.5, 5.0])
    np.testing.assert_array_equal(c2, [3, 7])


def test_cov_and_pearson() -> None:
    x, y = X5, [2.2, 2.8, 3.6, 4.5, 5.1]
    sxy = sum((a - 3.0) * (b - 3.64) for a, b in zip(x, y, strict=True))
    sxx = 10.0
    syy = sum((b - 3.64) ** 2 for b in y)
    assert stats.cov(x, y) == pytest.approx(sxy / 4.0, abs=1e-13)
    r = stats.pearsonr(x, y)
    assert r.r == pytest.approx(sxy / math.sqrt(sxx * syy), abs=1e-13)
    assert r.n == 5 and 0.0 <= r.p_value < 0.01
    perfect = stats.pearsonr(x, [2 * a + 1 for a in x])
    assert perfect.r == 1.0 and perfect.p_value == 0.0
    assert stats.pearsonr(x, [-a for a in x]).r == -1.0


def test_pearson_pvalue_from_t_critical_value() -> None:
    """n = 5 (3 dof): r = 0.8783 gives t = 3.182446 (table), so p = 0.05."""
    t = 3.182446305
    r = t / math.sqrt(t * t + 3.0)
    # build data with exactly this correlation: y = r*zx + sqrt(1-r^2)*w, w orthogonal to zx
    zx = np.array([-2.0, -1.0, 0.0, 1.0, 2.0]) / math.sqrt(10.0)
    w = np.array([1.0, -2.0, 0.0, 2.0, -1.0])
    w -= w.mean()
    w -= zx * (w @ zx)
    w /= np.linalg.norm(w)
    y = r * zx + math.sqrt(1.0 - r * r) * w
    res = stats.pearsonr(zx, y)
    assert res.r == pytest.approx(r, abs=1e-12)
    assert res.p_value == pytest.approx(0.05, abs=1e-7)


def test_confidence_interval_mean() -> None:
    m, lo, hi = stats.confidence_interval_mean(X5)
    half = T975_4 * math.sqrt(2.5) / math.sqrt(5)
    np.testing.assert_allclose([m, lo, hi], [3.0, 3.0 - half, 3.0 + half], atol=1e-9)
    _, lo99, hi99 = stats.confidence_interval_mean(X5, 0.99)
    assert hi99 - lo99 > hi - lo


def test_ttest_1samp_critical_value() -> None:
    mu = 3.0 - T975_4 * math.sqrt(0.5)  # sem = sqrt(0.5) -> t = table critical value
    r = stats.ttest_1samp(X5, mu)
    assert r.statistic == pytest.approx(T975_4, abs=1e-9)
    assert r.dof == 4.0
    assert r.p_value == pytest.approx(0.05, abs=1e-8)
    assert stats.ttest_1samp(X5, 0.0).statistic == pytest.approx(3.0 / math.sqrt(0.5))


def test_ttest_alternatives_consistent() -> None:
    two = stats.ttest_1samp(X5, 1.0)
    gt = stats.ttest_1samp(X5, 1.0, alternative="greater")
    lt = stats.ttest_1samp(X5, 1.0, alternative="less")
    assert two.p_value == pytest.approx(2.0 * gt.p_value, abs=1e-14)
    assert gt.p_value + lt.p_value == pytest.approx(1.0, abs=1e-14)


def test_ttest_ind_welch_and_pooled_hand_values() -> None:
    x, y = X5, [2.0, 4.0, 6.0, 8.0, 10.0]  # means 3, 6; variances 2.5, 10
    w = stats.ttest_ind(x, y)
    assert w.statistic == pytest.approx(-3.0 / math.sqrt(2.5), abs=1e-12)
    assert w.dof == pytest.approx(6.25 / (0.0625 + 1.0), abs=1e-12)  # Welch-Satterthwaite
    p = stats.ttest_ind(x, y, equal_var=True)
    assert p.statistic == pytest.approx(w.statistic, abs=1e-12)  # equal n: same t
    assert p.dof == 8.0
    assert p.p_value < w.p_value  # more dof, same t -> smaller p


def test_ttest_paired_matches_one_sample_on_differences() -> None:
    a = [10.0, 12.0, 9.0, 14.0, 11.0]
    b = [9.0, 11.0, 9.5, 12.0, 10.0]
    p = stats.ttest_paired(a, b)
    o = stats.ttest_1samp(np.array(a) - np.array(b), 0.0)
    assert p.statistic == pytest.approx(o.statistic, abs=1e-14)
    assert p.p_value == pytest.approx(o.p_value, abs=1e-14)
    assert p.dof == 4.0


def test_inputs_not_mutated() -> None:
    x = np.array([3.0, 1.0, 2.0])
    stats.quantile(x, 0.5)
    stats.median(x)
    np.testing.assert_array_equal(x, [3.0, 1.0, 2.0])


def test_validation() -> None:
    with pytest.raises(ValidationError, match="at least"):
        stats.var([1.0])
    assert stats.var([1.0], ddof=0) == 0.0
    with pytest.raises(ValidationError, match="ddof"):
        stats.var(X5, ddof=2)
    with pytest.raises(ValidationError, match="NaN"):
        stats.mean([1.0, float("nan")])
    with pytest.raises(ValidationError, match="empty"):
        stats.mean([])
    with pytest.raises(ValidationError, match="complex"):
        stats.mean([1j, 2.0])
    with pytest.raises(ValidationError, match="zero variance"):
        stats.skewness([2.0, 2.0, 2.0])
    with pytest.raises(ValidationError, match="zero variance"):
        stats.zscore([2.0, 2.0])
    with pytest.raises(ValidationError, match="zero variance"):
        stats.ttest_1samp([2.0, 2.0, 2.0], 1.0)
    with pytest.raises(ValidationError, match="both samples"):
        stats.ttest_ind([1.0, 1.0], [2.0, 2.0])
    with pytest.raises(ValidationError, match="\\[0, 1\\]"):
        stats.quantile(X5, 1.5)
    with pytest.raises(ValidationError, match="method"):
        stats.quantile(X5, 0.5, method="r6")
    with pytest.raises(ValidationError, match="level"):
        stats.confidence_interval_mean(X5, 1.0)
    with pytest.raises(ValidationError, match="alternative"):
        stats.ttest_1samp(X5, 0.0, alternative="both")
    with pytest.raises(ValidationError, match="at least 3"):
        stats.pearsonr([1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValidationError, match="constant"):
        stats.pearsonr(X5, [1.0] * 5)
    with pytest.raises(DimensionError):
        stats.cov(X5, [1.0, 2.0])
    with pytest.raises(ValidationError, match="bins"):
        stats.histogram(X5, 0)
    with pytest.raises(ValidationError, match="strictly increasing"):
        stats.histogram(X5, [0.0, 2.0, 2.0])
