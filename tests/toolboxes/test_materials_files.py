"""Materials toolbox and lab data file functions (readmatrix, readtable, writematrix, ...)."""

import math

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics
from engstudio.toolboxes.materials import functions as mt


def synthetic_curve(E=200e9, sy=250e6, su=400e6):
    """Elastic line, then a linear hardening branch to su, then necking down to fracture."""
    e_el = np.linspace(0, sy / E, 30)[:-1]
    e_pl = np.linspace(sy / E, 0.15, 60)
    s_pl = sy + (su - sy) * (e_pl - sy / E) / (0.15 - sy / E)
    e_n = np.linspace(0.15, 0.25, 20)[1:]
    s_n = su - 50e6 * (e_n - 0.15) / 0.10
    return np.r_[e_el, e_pl, e_n], np.r_[E * e_el, s_pl, s_n]


def test_material_database():
    s = mt.material("steel")
    assert s.E == 200e9 and s.G == pytest.approx(200e9 / 2.6) and s.rho == 7850
    assert mt.material("aluminium").Sy == 276e6


def test_tensile_test_recovers_properties():
    e, s = synthetic_curve()
    r = mt.tensile_test(e, s)
    assert r.E == pytest.approx(200e9, rel=1e-6)
    assert r.Su == pytest.approx(400e6) and r.strain_at_Su == pytest.approx(0.15)
    # yield: hardening line crosses the 0.2 % offset line slightly above 250 MPa
    slope = 150e6 / (0.15 - 250e6 / 200e9)
    ey = (250e6 - slope * 250e6 / 200e9 + 200e9 * 0.002) / (200e9 - slope)
    assert r.Sy == pytest.approx(200e9 * (ey - 0.002), rel=1e-3)
    assert r.elongation == pytest.approx(0.25) and r.toughness > 0.2 * 300e6


def test_fatigue_and_composites():
    assert mt.fatigue_sf(100e6, 0, 200e6, 400e6) == pytest.approx(2)
    assert mt.fatigue_sf(100e6, 100e6, 200e6, 400e6) == pytest.approx(1 / (0.5 + 0.25))
    assert mt.fatigue_sf(100e6, 100e6, 200e6, 400e6, 300e6, "soderberg") == pytest.approx(
        1 / (0.5 + 1 / 3))
    n = mt.fatigue_sf(100e6, 100e6, 200e6, 400e6, None, "gerber")
    assert n * 0.5 + (n * 0.25) ** 2 == pytest.approx(1)
    N = mt.basquin_life(300e6, 900e6, -0.1)
    assert 900e6 * (2 * N) ** -0.1 == pytest.approx(300e6)
    el, et = mt.rule_of_mixtures(230e9, 3.5e9, 0.6)
    assert el == pytest.approx(0.6 * 230e9 + 0.4 * 3.5e9) and et < el
    assert mt.thermal_stress(200e9, 12e-6, 50) == pytest.approx(-120e6)


# ------------------------------------------------------------------------ lab data files
@pytest.fixture()
def kernel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    k = InProcessKernelClient(threaded=False)
    yield k
    k.shutdown()


def run(k, code, ok=True):
    events = []
    k.subscribe(events.append)
    k.execute(code, None)
    errors = [d.message for e in events if isinstance(e, Diagnostics) for d in e.items]
    if ok:
        assert not errors, errors
    return k._interp.workspace, errors


def test_readmatrix_skips_header_rows(kernel, tmp_path):
    (tmp_path / "lab.csv").write_text("time,load\ns,N\n0,1.5\n1,2.5\n2,NaN\n3,4\n")
    ws, _ = run(kernel, "A = readmatrix('lab.csv'); n = size(A, 1);")
    assert ws["A"].shape == (4, 2) and ws["n"].item() == 4
    assert ws["A"][1, 1] == 2.5 and math.isnan(ws["A"][2, 1])


def test_write_then_read_roundtrip_csv_and_excel(kernel, tmp_path):
    ws, _ = run(kernel, "M = [16 2 3 13; 5 11 10 8; 9 7 6 12; 4 14 15 1];"
                        " writematrix(M, 'm.csv'); writematrix(M, 'm.xlsx');"
                        " B = readmatrix('m.csv'); C = readmatrix('m.xlsx');"
                        " csvwrite('c.csv', M); D = csvread('c.csv', 1, 2);"
                        " E = xlsread('m.xlsx');")
    assert np.array_equal(ws["B"], ws["M"]) and np.array_equal(ws["C"], ws["M"])
    assert np.array_equal(ws["D"], ws["M"][1:, 2:]) and np.array_equal(ws["E"], ws["M"])
    assert (tmp_path / "m.xlsx").exists()


def test_readtable_and_writetable(kernel, tmp_path):
    (tmp_path / "spec.csv").write_text("Specimen,Diameter (mm),Load\nA,10,5000\nB,12,7200\n")
    ws, _ = run(kernel, "T = readtable('spec.csv'); d = T.Diameter__mm_; L = T.Load;"
                        " s = T.Specimen{2}; writetable(T, 'out.xlsx'); U = readtable('out.xlsx');"
                        " f = fieldnames(U);")
    assert ws["d"].ravel().tolist() == [10, 12] and ws["L"].shape == (2, 1)
    assert ws["s"].to_str() == "B"
    assert ws["U"].get("Load").ravel().tolist() == [5000, 7200]


def test_file_errors_are_clear(kernel):
    _, errors = run(kernel, "A = readmatrix('missing.csv');", ok=False)
    assert errors and "not found" in errors[0]
    _, errors = run(kernel, "writematrix([1 2], 'x.doc');", ok=False)
    assert errors and "unsupported" in errors[0]
