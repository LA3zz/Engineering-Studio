"""Single running instance: later launches hand their files to the first one."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import uuid

from engstudio.gui.app_main import _files
from engstudio.gui.single_instance import SingleInstance, server_name


def test_forward_from_another_process_reaches_the_listener(qtbot):
    import subprocess
    import sys
    name = f"engstudio-test-{uuid.uuid4().hex[:8]}"
    first = SingleInstance(name)
    got: list[list[str]] = []
    assert first.listen(got.append)
    code = ("import sys; from PySide6.QtCore import QCoreApplication; "
            "from engstudio.gui.single_instance import SingleInstance; "
            "app = QCoreApplication([]); "
            f"sys.exit(0 if SingleInstance({name!r}).try_forward(sys.argv[1:]) else 3)")
    proc = subprocess.Popen([sys.executable, "-c", code, r"C:\a b\x.m", "y.m"])
    qtbot.waitUntil(lambda: proc.poll() is not None, timeout=20000)
    assert proc.returncode == 0
    qtbot.waitUntil(lambda: got == [[r"C:\a b\x.m", "y.m"]], timeout=3000)
    first.close()


def test_no_listener_means_start_normally():
    assert SingleInstance(f"engstudio-none-{uuid.uuid4().hex[:8]}").try_forward(["x.m"]) is False


def test_server_name_is_per_user_and_safe():
    name = server_name()
    assert name.startswith("engstudio-") and all(c.isalnum() or c == "-" for c in name)


def test_file_arguments(tmp_path):
    script = tmp_path / "s.m"
    script.write_text("x = 1", encoding="utf-8")
    assert _files(["prog", "--stub", str(script), str(tmp_path / "missing.m")]) == [
        str(script.resolve())]
