"""An interactive figure switches its Plotly template when its page posts the dark scheme, in Chromium.

The figure's script listens for a `jnwb-scheme` message and calls Plotly.react with the template the
message names. The test loads one figure's HTML at the top of a page, posts the dark scheme from that
page and reads the template back from the plot. The figure asks for Plotly from the CDN, which a
machine without network access cannot reach, so the request is answered from the copy the installed
plotly package ships. Without Chromium the test skips, unless JNWB_REQUIRE_BROWSER is set, when it fails.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import plotly
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = REPO_ROOT / "scripts" / "figures"
FIGURE = "fig02_raster_psth.png"
CDN = "https://cdn.plot.ly/**"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
REQUIRE_BROWSER = "JNWB_REQUIRE_BROWSER"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, FIGURE_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


generator = _load("generate_figures")
interactive = _load("figure_interactive")


@pytest.fixture(scope="module")
def figure_html(tmp_path_factory):
    converted, _, _ = generator.convert_figure(FIGURE)
    path = tmp_path_factory.mktemp("figure") / "figure.html"
    path.write_text(interactive.to_html(converted), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    manager = sync_api.sync_playwright().start()
    try:
        chromium = manager.chromium.launch()
    except sync_api.Error as exc:
        manager.stop()
        reason = str(exc).strip().splitlines()[0]
        if os.environ.get(REQUIRE_BROWSER):
            pytest.fail(f"{REQUIRE_BROWSER} is set and Chromium cannot launch: {reason}")
        pytest.skip(f"Chromium cannot launch: {reason}")
    yield chromium
    chromium.close()
    manager.stop()


def test_the_dark_scheme_switches_the_plotly_template(browser, figure_html):
    assert PLOTLY_JS.exists(), f"plotly ships no {PLOTLY_JS}"
    light = interactive._template("light").layout.font.color
    dark = interactive._template("dark").layout.font.color
    assert light != dark, "the two templates share an ink colour, so the switch cannot show"
    read = f"document.getElementById({json.dumps(interactive.DIV_ID)}).layout.template.layout.font.color"
    page = browser.new_page()
    try:
        page.route(CDN, lambda route: route.fulfill(path=str(PLOTLY_JS), content_type="application/javascript"))
        page.goto(figure_html.as_uri())
        page.wait_for_function(f"typeof Plotly !== 'undefined' && {read} === {json.dumps(light)}")
        page.evaluate("window.postMessage({type: 'jnwb-scheme', scheme: 'dark'}, '*')")
        # Without the listener the template never changes and this wait times out, which fails the test.
        page.wait_for_function(f"{read} === {json.dumps(dark)}", timeout=5000)
        assert page.evaluate(read) == dark
    finally:
        page.close()
