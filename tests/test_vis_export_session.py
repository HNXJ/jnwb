"""
tests/test_vis_export_session.py -- what save_and_seal does when kaleido's export fails.

kaleido's two synchronous render entry points are replaced by fakes, so these tests need no
browser. The fakes follow kaleido's order: a one-shot render returns its bytes and the session's
close then discards them if the close times out; a multi-file session writes each file before it
closes. Each call to an entry point stands for one kaleido session.
"""

from __future__ import annotations

import threading
import warnings
from pathlib import Path

import pytest

pytest.importorskip("plotly")
pytest.importorskip("kaleido")
import kaleido  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

from jnwb.vis.canvas import PlotlyPublicationCanvas  # noqa: E402

SHUTDOWN = "Couldn't close or kill browser subprocess"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><text>figure</text></svg>'
PNG = b"\x89PNG\r\n\x1a\n" + b"figure"
ARGUMENT = {
    "QUESTION": "Does the export survive a failed session?",
    "DATA": "Synthetic test figure",
    "ESTIMAND": "Not applicable: the figure is a fixed line",
    "INFERENCE UNIT": "Not applicable",
    "RESULT": "Placeholder result for an export test",
    "LICENSED CLAIM": "Placeholder licensed claim",
    "BARRED CLAIM": "Placeholder barred claim",
    "SOURCE ARTIFACTS": ["export_test_source.json"],
}


class FakeKaleido:
    """Stands in for kaleido's `calc_fig_sync` and `write_fig_from_object_sync`.

    `render_error` raises from a render. `empty_format` renders no bytes for that format.
    `shutdown_error` is raised when the session closes. Every entry-point call is recorded in
    `sessions`.
    """

    def __init__(self, monkeypatch):
        self.sessions: list[str] = []
        self.render_error = None
        self.empty_format = None
        self.shutdown_error = None
        monkeypatch.setattr(kaleido, "calc_fig_sync", self.calc_fig_sync)
        monkeypatch.setattr(kaleido, "write_fig_from_object_sync", self.write_fig_from_object_sync)

    def _render(self, fmt):
        if self.render_error is not None:
            raise self.render_error
        if fmt == self.empty_format:
            return b""
        return SVG if fmt == "svg" else PNG

    def calc_fig_sync(self, fig, opts=None, topojson=None, kopts=None):
        """One render per session. A failed close raises, and the bytes are lost with it."""
        self.sessions.append("calc_fig_sync")
        data = self._render(opts["format"])
        if self.shutdown_error is not None:
            raise self.shutdown_error
        return data

    def write_fig_from_object_sync(self, specs, kopts=None):
        """Every spec in one session. Each file is written before the session closes."""
        self.sessions.append("write_fig_from_object_sync")
        for spec in specs:
            Path(spec["path"]).write_bytes(self._render(spec["opts"]["format"]))
        if self.shutdown_error is not None:
            raise self.shutdown_error


def _canvas():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=80.0, rows=1, cols=1)
    canvas.fig.add_trace(go.Scatter(x=[0, 1, 2], y=[10, 20, 15], mode="lines+markers"))
    return canvas


def _bounded(call, seconds=20.0):
    """Runs `call` on a daemon thread and returns its outcome. Fails if it outlives `seconds`."""
    out = {}

    def run():
        try:
            out["value"] = call()
        except BaseException as err:  # noqa: BLE001 -- reported below, on the test's thread
            out["error"] = err

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), f"the call was still running after {seconds} s"
    return out


def test_one_save_opens_one_export_session(tmp_path, monkeypatch):
    fake = FakeKaleido(monkeypatch)
    _canvas().save_and_seal(tmp_path, "figure", ARGUMENT)
    assert len(fake.sessions) == 1, fake.sessions


def test_an_export_error_reaches_the_caller_and_seals_nothing(tmp_path, monkeypatch):
    fake = FakeKaleido(monkeypatch)
    fake.render_error = RuntimeError("render failed")
    with pytest.raises(RuntimeError, match="render failed"):
        _canvas().save_and_seal(tmp_path, "figure", ARGUMENT)
    assert fake.sessions, "the export never reached kaleido"
    assert not (tmp_path / "figure_argument.json").exists()


@pytest.mark.parametrize("shutdown", [False, True])
def test_a_missing_export_raises_and_seals_nothing(tmp_path, monkeypatch, shutdown):
    fake = FakeKaleido(monkeypatch)
    fake.empty_format = "png"
    if shutdown:
        fake.shutdown_error = RuntimeError(SHUTDOWN)
    match = SHUTDOWN if shutdown else "Export verification failed"
    with pytest.raises(RuntimeError, match=match):
        _canvas().save_and_seal(tmp_path, "figure", ARGUMENT)
    assert fake.sessions, "the export never reached kaleido"
    assert not (tmp_path / "figure_argument.json").exists()


def test_a_shutdown_timeout_after_the_files_are_written_keeps_them(tmp_path, monkeypatch):
    fake = FakeKaleido(monkeypatch)
    fake.shutdown_error = RuntimeError(SHUTDOWN)
    with pytest.warns(RuntimeWarning, match="shutdown timed out"):
        paths = _canvas().save_and_seal(tmp_path, "figure", ARGUMENT)
    assert fake.sessions, "the export never reached kaleido"
    assert paths["svg"].read_bytes() == SVG
    assert paths["png"].read_bytes() == PNG
    assert paths["html"].exists()
    assert paths["argument"].exists()


def test_files_from_an_earlier_call_are_never_sealed(tmp_path, monkeypatch):
    for name in ("figure.svg", "figure.png", "figure_argument.json"):
        (tmp_path / name).write_bytes(b"OLD")
    fake = FakeKaleido(monkeypatch)
    fake.empty_format = "png"
    fake.shutdown_error = RuntimeError(SHUTDOWN)
    with pytest.raises(RuntimeError, match=SHUTDOWN):
        _canvas().save_and_seal(tmp_path, "figure", ARGUMENT)
    assert fake.sessions, "the export never reached kaleido"
    assert (tmp_path / "figure.png").read_bytes() == b"", "the earlier call's PNG survived"
    assert not (tmp_path / "figure_argument.json").exists()


@pytest.mark.parametrize("first", ["render", "shutdown"])
def test_the_call_after_a_failed_export_succeeds_promptly(tmp_path, monkeypatch, first):
    fake = FakeKaleido(monkeypatch)
    if first == "render":
        fake.render_error = RuntimeError("render failed")
    else:
        fake.shutdown_error = RuntimeError(SHUTDOWN)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            _canvas().save_and_seal(tmp_path / "first", "figure", ARGUMENT)
        except RuntimeError:
            pass
    fake.render_error = None
    fake.shutdown_error = None
    out = _bounded(lambda: _canvas().save_and_seal(tmp_path / "second", "figure", ARGUMENT))
    assert "error" not in out, out
    assert out["value"]["png"].read_bytes() == PNG
