"""Control-system values and builtins in the interpreter (Phase 6, C2)."""

import math

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Stdout
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_control import install_control, poly_text
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import LtiValue, class_of


@pytest.fixture
def interp():
    it = Interpreter()
    install_core(it)
    install_extra(it)
    install_control(it)
    return it


def run(it, code):
    it.execute(code, None)
    return it.workspace


def num(ws, name):
    return np.asarray(ws[name], dtype=complex if ws[name].dtype.kind == "c" else float)


def coeffs(ws, name):
    n, d = ws[name].system.data[0], ws[name].system.data[1]
    return (n / d[0]).tolist(), (d / d[0]).tolist()


def test_tf_value_class_and_size(interp):
    ws = run(interp, "G = tf(1, [1 2 1]); c = class(G); z = zpk(G); S = ss(G);")
    assert isinstance(ws["G"], LtiValue) and ws["c"].to_str() == "tf"
    assert class_of(ws["z"]) == "zpk" and class_of(ws["S"]) == "ss"


def test_tf_s_expression(interp):
    ws = run(interp, "s = tf('s'); H = 10/(s + 1)^3; G = (s + 2)/(s^2 + 3*s + 2);")
    assert coeffs(ws, "H") == (pytest.approx([10]), pytest.approx([1, 3, 3, 1]))
    n, d = coeffs(ws, "G")
    assert n == pytest.approx([1, 2]) and d == pytest.approx([1, 3, 2])


def test_operators(interp):
    ws = run(interp, "G = tf(1, [1 1]); A = 2*G; B = G + G; C = G - 1; D = -G; E = G*G;"
                     " F = G/2; I = G^0;")
    assert coeffs(ws, "A")[0] == pytest.approx([2])
    assert num(run(interp, "x = dcgain(B);"), "x").item() == pytest.approx(2)
    assert num(run(interp, "x = dcgain(C);"), "x").item() == pytest.approx(0)
    assert num(run(interp, "x = dcgain(D);"), "x").item() == pytest.approx(-1)
    assert coeffs(ws, "E")[1] == pytest.approx([1, 2, 1])
    assert num(run(interp, "x = dcgain(F);"), "x").item() == pytest.approx(0.5)
    assert num(run(interp, "x = dcgain(I);"), "x").item() == pytest.approx(1)


def test_feedback_series_parallel_and_pid(interp):
    ws = run(interp, "G = tf(1, [1 1]); T = feedback(G, 1); P = parallel(G, 1);"
                     " Q = series(G, tf(2, [1 0])); C = pid(1, 2, 3); K = pidstd(2, 4, 0.5);")
    assert coeffs(ws, "T") == (pytest.approx([1]), pytest.approx([1, 2]))
    assert ws["C"].system.data[0].tolist() == [3, 1, 2]
    assert ws["K"].system.data[0].tolist() == pytest.approx([1, 2, 0.5])
    assert coeffs(ws, "Q")[1] == pytest.approx([1, 1, 0])


def test_pole_zero_dcgain_damp_isstable(interp):
    ws = run(interp, "G = tf([1 3], [1 3 2]); p = pole(G); z = zero(G); k = dcgain(G);"
                     " [wn, zeta] = damp(tf(4, [1 1.2 4])); a = isstable(G);"
                     " b = isstable(tf(1, [1 -1]));")
    assert sorted(num(ws, "p").ravel()) == pytest.approx([-2, -1])
    assert num(ws, "z").ravel() == pytest.approx([-3]) and num(ws, "k").item() == 1.5
    assert num(ws, "wn").ravel() == pytest.approx([2, 2])
    assert num(ws, "zeta").ravel() == pytest.approx([0.3, 0.3])
    assert bool(ws["a"].item()) and not bool(ws["b"].item())


def test_stepinfo_struct(interp):
    ws = run(interp, "info = stepinfo(tf(1, [1 2 2])); os = info.Overshoot;")
    zeta = 1 / math.sqrt(2)
    assert num(ws, "os").item() == pytest.approx(
        100 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2)), rel=1e-3)


def test_margin_outputs(interp):
    ws = run(interp, "[gm, pm, wcg, wcp] = margin(tf(10, [1 3 3 1]));")
    assert num(ws, "gm").item() == pytest.approx(0.8, rel=1e-4)
    assert num(ws, "wcg").item() == pytest.approx(math.sqrt(3), rel=1e-4)


def test_c2d_and_data_accessors(interp):
    ws = run(interp, "Gd = c2d(tf(1, [1 1]), 0.1); [n, d, ts] = tfdata(Gd);"
                     " [z, p, k] = zpkdata(zpk([-3], [-1 -2], 5));"
                     " [A, B, C, D] = ssdata(tf(1, [1 2]));"
                     " o = order(tf(1, [1 2 3])); t = isdt(Gd);")
    assert num(ws, "ts").item() == pytest.approx(0.1)
    assert (num(ws, "d") / num(ws, "d")[0, 0]).ravel() == pytest.approx([1, -math.exp(-0.1)])
    assert num(ws, "k").item() == 5 and num(ws, "A").item() == -2
    assert num(ws, "o").item() == 2 and bool(ws["t"].item())


def test_minreal_cancels(interp):
    ws = run(interp, "M = minreal(tf([1 1], [1 3 2]));")
    assert coeffs(ws, "M") == (pytest.approx([1]), pytest.approx([1, 2]))


def test_display_text_through_kernel():
    k = InProcessKernelClient(threaded=False)
    out = []
    k.subscribe(lambda e: out.append(e.text) if isinstance(e, Stdout) else None)
    k.execute("G = tf(1, [1 2 1])\nZ = zpk([-3], [-1 -2], 5)\nGd = c2d(G, 0.1)", None)
    text = "".join(out)
    assert "s^2 + 2 s + 1" in text and "Continuous-time transfer function." in text
    assert "5 (s+3)" in text and "(s+1) (s+2)" in text
    assert "Sample time: 0.1 seconds" in text
    k.shutdown()


@pytest.mark.parametrize("coeffs_, text", [
    ([1, 2, 1], "s^2 + 2 s + 1"), ([1, 0, -4], "s^2 - 4"), ([-1, 0], "-s"),
    ([0.5, 2, 1], "0.5 s^2 + 2 s + 1"), ([3], "3"),
])
def test_poly_text(coeffs_, text):
    assert poly_text(np.array(coeffs_, dtype=float), "s") == text


@pytest.mark.parametrize("code, msg", [
    ("tf('q')", "tf\\('s'\\)"),
    ("pole(5)", "must be a system"),
    ("G = tf(1, [1 1]); H = G^0.5;", "integers"),
    ("G = tf(1, [1 1]); H = G*[1 2];", "only scalars"),
    ("c2d(tf(1, [1 1]), 0.1, 'bogus')", "method"),
    ("feedback(tf(1, [1 1]), tf(1, [1 1], 0.1))", "sample times"),
])
def test_errors(interp, code, msg):
    with pytest.raises(EngStudioError, match=msg):
        run(interp, code)


def test_pidtune_command(interp):
    ws = run(interp, "G = tf(1, [1 3 3 1]); [C, info] = pidtune(G, 'PI'); T = feedback(C*G, 1);"
                     " ok = isstable(T); pm = info.PhaseMargin;")
    assert class_of(ws["C"]) == "tf" and bool(ws["ok"].item())
    assert num(ws, "pm").item() == pytest.approx(60, abs=8)
    with pytest.raises(EngStudioError, match="type must be"):
        run(interp, "pidtune(tf(1, [1 1]), 'PIDX')")
