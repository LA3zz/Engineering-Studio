"""stats.t_quantile: Student-t table values (t(0.975, 10) = 2.2281, t(0.95, 5) = 2.0150)."""

import pytest

from engstudio.core.errors import ValidationError
from engstudio.engine import stats


def test_table_values():
    assert stats.t_quantile(0.975, 10) == pytest.approx(2.228138852, abs=1e-8)
    assert stats.t_quantile(0.95, 5) == pytest.approx(2.015048373, abs=1e-8)


def test_large_dof_approaches_normal_and_symmetry():
    assert stats.t_quantile(0.975, 1e7) == pytest.approx(1.959964, abs=1e-4)
    assert stats.t_quantile(0.025, 7) == pytest.approx(-stats.t_quantile(0.975, 7), abs=1e-12)


@pytest.mark.parametrize("p, dof", [(0.0, 5), (1.0, 5), (0.5, 0), (0.5, -1), (float("nan"), 3)])
def test_invalid_arguments(p, dof):
    with pytest.raises(ValidationError):
        stats.t_quantile(p, dof)
