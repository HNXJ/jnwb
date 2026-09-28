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
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARK = "requires_git_checkout"

#: Tests in this xdist group export through kaleido, which renders in a headless browser.
BROWSER_EXPORT_GROUP = "browser_export"
BROWSER_SHUTDOWN_TIMEOUT = "Couldn't close or kill browser subprocess"
#: How long the session browser may take to render its first figure before the suite fails.
BROWSER_START_SECONDS = 300


def stop_browser(kaleido) -> None:
    """Stops kaleido's session browser; a shutdown that only timed out warns instead of failing.

    The browser closes in kaleido's own thread, so its error reaches ``threading.excepthook``
    rather than this caller. choreographer allows the browser 3 s to exit and 6 s after a kill;
    a loaded Windows machine can take longer, and the process exits afterwards anyway.
    """
    caught = []
    previous = threading.excepthook
    threading.excepthook = caught.append
    try:
        kaleido.stop_sync_server(silence_warnings=True)
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
def browser_stopper():
    """:func:`stop_browser`, for a test that exercises it without importing this file."""
    return stop_browser


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
    if not hasattr(kaleido, "start_sync_server"):
        yield
        return
    kaleido.start_sync_server(silence_warnings=True)
    answer = {}

    def first_figure():
        try:
            answer["bytes"] = kaleido.calc_fig_sync(
                {"data": [{"type": "scatter", "x": [0, 1], "y": [0, 1]}], "layout": {}},
                opts={"format": "svg", "width": 100, "height": 100},
            )
        except BaseException as err:  # noqa: BLE001 -- re-raised below on this thread
            answer["error"] = err

    ask = threading.Thread(target=first_figure, daemon=True)
    ask.start()
    ask.join(BROWSER_START_SECONDS)
    if ask.is_alive():
        # The server thread is stuck; stopping it would block on the same thread.
        raise RuntimeError(f"kaleido's browser rendered nothing in {BROWSER_START_SECONDS} s")
    try:
        if "error" in answer:
            raise answer["error"]
        assert answer["bytes"], "kaleido's browser returned an empty figure"
        yield
    finally:
        stop_browser(kaleido)


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
