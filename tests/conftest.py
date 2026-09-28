"""Suite-wide configuration.

A test marked ``requires_git_checkout`` reads this repository's own git data: tracked files,
ignore rules, the index's line endings, the HEAD commit. A source export (``git archive``, the
archive GitHub serves for a tag, a deposit made from one) has no ``.git``, so those tests skip
there instead of failing on a ``git`` call. In a clone or a linked worktree ``.git`` exists and
they run; a broken git installation then still fails them.

Mark a module with ``pytestmark = pytest.mark.requires_git_checkout`` when every test in it reads
git data, otherwise mark the tests that do. A test that builds its own repository in a temporary
directory needs no mark.
"""

from __future__ import annotations

import threading
import time
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARK = "requires_git_checkout"

#: Tests in this xdist group export through kaleido, which renders in a headless browser.
BROWSER_EXPORT_GROUP = "browser_export"
BROWSER_SHUTDOWN_TIMEOUT = "Couldn't close or kill browser subprocess"
#: How long the session browser may take to render its first figure before the suite fails.
BROWSER_START_SECONDS = 300
#: kaleido's default limit on one render (``Kaleido(timeout=90)``), plus a margin for its queue.
BROWSER_RENDER_SECONDS = 90 + 30
BROWSER_STOP_SECONDS = 60
FIRST_FIGURE = {"data": [{"type": "scatter", "x": [0, 1], "y": [0, 1]}], "layout": {}}


class SessionBrowserFailed(RuntimeError):
    """kaleido's session browser died, or gave no answer within its bound."""


def bounded(call, seconds, what, alive=lambda: True, cause=lambda: None):
    """Returns ``call()`` run on a daemon thread, or raises :class:`SessionBrowserFailed` once
    ``seconds`` pass or ``alive()`` turns false. A thread left blocked is abandoned."""
    answer = {}

    def run():
        try:
            answer["value"] = call()
        except BaseException as err:  # noqa: BLE001 -- re-raised below on the caller's thread
            answer["error"] = err

    thread = threading.Thread(target=run, daemon=True, name=f"bounded {what}")
    thread.start()
    deadline = time.monotonic() + seconds
    while True:
        thread.join(0.25)
        if not thread.is_alive():
            break
        if not alive():
            raise SessionBrowserFailed(f"kaleido's session browser died during {what}") from cause()
        if time.monotonic() > deadline:
            raise SessionBrowserFailed(f"kaleido's session browser gave no {what} in {seconds} s")
    if "error" in answer:
        raise answer["error"]
    return answer.get("value")


def install_session_browser(server) -> dict:
    """Records how kaleido's server thread ends and bounds every call made to it.

    This uses kaleido's private server (``kaleido._global_server``, its ``_server``, ``_thread``
    and ``call_function``, as of kaleido 1.2): a public call to it blocks forever once the server
    thread has died, for instance when the browser died and a render raised ``CancelledError``.
    The bound of each call is ``server.call_function.seconds``. Returns where the ending is kept.
    """
    ended = {}
    serve, call = server._server, server.call_function

    async def recorded(*args, **kwargs):
        try:
            return await serve(*args, **kwargs)
        except BaseException as err:
            ended["error"] = err
            raise

    def alive():
        thread = getattr(server, "_thread", None)
        return thread is not None and thread.is_alive()

    def call_function(cmd, *args, **kwargs):
        return bounded(lambda: call(cmd, *args, **kwargs), call_function.seconds, cmd,
                       alive=alive, cause=lambda: ended.get("error"))

    call_function.seconds = BROWSER_RENDER_SECONDS
    server._server, server.call_function = recorded, call_function
    return ended


def uninstall_session_browser(server) -> None:
    for name in ("_server", "call_function"):
        vars(server).pop(name, None)


def first_figure(calc_fig_sync) -> bytes:
    figure = calc_fig_sync(FIRST_FIGURE, opts={"format": "svg", "width": 100, "height": 100})
    if not figure:
        raise SessionBrowserFailed("kaleido's session browser returned an empty figure")
    return figure


def stop_browser(kaleido, seconds=BROWSER_STOP_SECONDS) -> None:
    """Stops kaleido's session browser; a shutdown that only timed out warns instead of failing.

    The browser closes in kaleido's own thread, so its error reaches ``threading.excepthook``
    rather than this caller. choreographer allows the browser 3 s to exit and 6 s after a kill;
    a loaded Windows machine can take longer, and the process exits afterwards anyway.
    """
    caught = []
    previous = threading.excepthook
    threading.excepthook = caught.append
    try:
        bounded(lambda: kaleido.stop_sync_server(silence_warnings=True), seconds, "stop")
    finally:
        threading.excepthook = previous
    for args in caught:
        err = args.exc_value
        if isinstance(err, RuntimeError) and BROWSER_SHUTDOWN_TIMEOUT in str(err):
            warnings.warn(f"kaleido's browser shutdown timed out: {err}", RuntimeWarning,
                          stacklevel=2)
        else:
            raise err


@pytest.fixture
def session_browser_parts():
    """This file's session-browser functions, for tests that exercise them without importing it."""
    return SimpleNamespace(bounded=bounded, install=install_session_browser,
                           uninstall=uninstall_session_browser, first_figure=first_figure,
                           stop=stop_browser, failed=SessionBrowserFailed)


@pytest.fixture(scope="session")
def session_browser():
    """One kaleido browser for every export in the session instead of one per export.

    Each export otherwise opens and shuts down its own browser, and the shutdown fails on a
    loaded machine (see :func:`stop_browser`), which loses the figure. A kaleido without
    ``start_sync_server`` keeps a browser per export.
    """
    try:
        import kaleido
    except ImportError:
        yield
        return
    server = getattr(kaleido, "_global_server", None)  # private; see install_session_browser
    if not hasattr(kaleido, "start_sync_server") or server is None:
        yield
        return
    install_session_browser(server)
    kaleido.start_sync_server(silence_warnings=True)
    try:
        server.call_function.seconds = BROWSER_START_SECONDS
        first_figure(kaleido.calc_fig_sync)
        server.call_function.seconds = BROWSER_RENDER_SECONDS
        yield
    finally:
        try:
            stop_browser(kaleido)
        finally:
            uninstall_session_browser(server)


@pytest.fixture(autouse=True)
def _browser_exports_share_the_session_browser(request):
    marker = request.node.get_closest_marker("xdist_group")
    if marker is not None and marker.args and marker.args[0] == BROWSER_EXPORT_GROUP:
        request.getfixturevalue("session_browser")


def is_git_checkout(root: Path = ROOT) -> bool:
    """True in a clone or a linked worktree, where ``.git`` is a directory or a file."""
    return (root / ".git").exists()


@pytest.fixture
def git_checkout_probe():
    """:func:`is_git_checkout`, for a test that exercises it without importing this file."""
    return is_git_checkout


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"{MARK}: reads this repository's git data; skipped where there is no .git"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if is_git_checkout():
        return
    skip = pytest.mark.skip(reason=f"no .git under {ROOT}: a source export has no git data")
    for item in items:
        if item.get_closest_marker(MARK) is not None:
            item.add_marker(skip)
