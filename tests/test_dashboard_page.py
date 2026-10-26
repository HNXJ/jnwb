"""
tests/test_dashboard_page.py -- The dashboard template, its renderer and the data contract agree.

scripts/dashboard/app.js fills scripts/dashboard/index.html from data.json. These checks run
without a browser: the fixture validates against data.schema.json; every data-slot in the
template resolves in the fixture or is a derived slot the renderer computes; every element id
the renderer queries exists in the template; and every tab or card target names a section.
"""
import functools
import importlib
import json
import os
import re
import sys
import threading
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "scripts" / "dashboard"
TEMPLATE = DASHBOARD / "index.html"
SCHEMA = DASHBOARD / "data.schema.json"
RENDERER = DASHBOARD / "app.js"
FIXTURE = ROOT / "tests" / "fixtures" / "dashboard_data.json"

_ID_CALLS = (
    re.compile(r"""getElementById\(\s*['"]([A-Za-z0-9_-]+)['"]\s*\)"""),
    re.compile(r"""querySelector(?:All)?\(\s*['"]#([A-Za-z0-9_-]+)['"]\s*\)"""),
)


class _Template(HTMLParser):
    """Collects the attributes the renderer reads from the template."""

    def __init__(self):
        super().__init__()
        self.slots = []
        self.ids = []
        self.sections = []
        self.targets = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        for name in ("data-slot", "data-slot-href"):
            if name in attr:
                self.slots.append(attr[name] or "")
        if attr.get("id"):
            self.ids.append(attr["id"])
            if tag == "section":
                self.sections.append(attr["id"])
        for name in ("aria-controls", "data-target"):
            if name in attr:
                self.targets.append(attr[name] or "")


def _template():
    parser = _Template()
    parser.feed(TEMPLATE.read_text(encoding="utf-8"))
    return parser


def _lookup(data, path):
    node = data
    for key in path.split("."):
        if not isinstance(node, dict) or node.get(key) is None:
            return None
        node = node[key]
    return node


def _derived_names():
    """The slots the renderer computes itself: the keys of its DERIVED map."""
    source = RENDERER.read_text(encoding="utf-8")
    block = re.search(r"var DERIVED = \{(.*?)\};", source, re.S)
    assert block, "app.js has no DERIVED map"
    names = re.findall(r"'([a-z_.]+)'\s*:", block.group(1))
    assert names, "the DERIVED map names no slots"
    return set(names)


def test_fixture_validates_against_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is None:
        # Without jsonschema only the top-level required keys are checked.
        missing = [key for key in schema["required"] if key not in data]
        assert not missing, f"fixture lacks required keys: {missing}"
        return
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(data),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    assert not errors, [
        f"{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in errors
    ]


def test_every_template_slot_resolves_or_is_derived():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    slots = _template().slots
    assert slots, "template has no data-slot or data-slot-href attributes"
    derived = _derived_names()
    unresolved = sorted({
        slot for slot in slots
        if slot not in derived and _lookup(data, slot) is None
    })
    assert not unresolved, f"slots neither in the fixture nor derived by app.js: {unresolved}"


def test_every_element_id_the_renderer_queries_is_in_the_template():
    source = RENDERER.read_text(encoding="utf-8")
    queried = set()
    for pattern in _ID_CALLS:
        queried.update(pattern.findall(source))
    assert queried, "app.js queries no element id literal"
    missing = sorted(queried - set(_template().ids))
    assert not missing, f"app.js queries ids the template lacks: {missing}"


def test_tab_and_card_targets_name_a_section():
    template = _template()
    assert template.targets, "template has no aria-controls or data-target attributes"
    unknown = sorted(set(template.targets) - set(template.sections))
    assert not unknown, f"tab or card targets without a section: {unknown}"


class _Events(HTMLParser):
    """The template as events in document order: ("start", tag, attrs), ("end", tag, {}) and
    ("text", "", {"data": text})."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, dict(attrs)))

    def handle_endtag(self, tag):
        self.events.append(("end", tag, {}))

    def handle_data(self, data):
        self.events.append(("text", "", {"data": data}))


def _events():
    parser = _Events()
    parser.feed(TEMPLATE.read_text(encoding="utf-8"))
    return parser.events


def _openscope_section(events):
    """The indices of the OpenScope section's start and its closing tag."""
    begin = next(i for i, (kind, tag, attrs) in enumerate(events)
                 if kind == "start" and tag == "section" and attrs.get("id") == "openscope-glo")
    end = next(i for i in range(begin + 1, len(events)) if events[i][:2] == ("end", "section"))
    return begin, end


def test_the_openscope_tab_is_a_tab_button_for_its_section():
    events = _events()
    nav = next(i for i, (kind, tag, attrs) in enumerate(events)
               if kind == "start" and tag == "nav" and "tabs" in (attrs.get("class") or "").split())
    nav_end = next(i for i in range(nav + 1, len(events)) if events[i][:2] == ("end", "nav"))
    buttons = [i for i, (kind, tag, attrs) in enumerate(events)
               if kind == "start" and tag == "button" and attrs.get("aria-controls") == "openscope-glo"]
    assert len(buttons) == 1, f"expected one tab button for the section, found {len(buttons)}"
    assert nav < buttons[0] < nav_end, "the tab button sits outside nav.tabs"
    assert events[buttons[0]][2].get("role") == "tab"
    panels = [attrs for kind, tag, attrs in events
              if kind == "start" and tag == "section" and attrs.get("id") == "openscope-glo"]
    assert len(panels) == 1, f"expected one section with the id, found {len(panels)}"
    assert panels[0].get("role") == "tabpanel"
    assert "hidden" in panels[0], "the panel starts hidden, as the other panels do"


def test_the_openscope_section_holds_three_subsections_in_order():
    events = _events()
    begin, end = _openscope_section(events)
    markers, heading = [], None
    for kind, tag, attrs in events[begin:end]:
        if kind == "start" and tag == "h3":
            heading = ""
        elif kind == "text" and heading is not None:
            heading += attrs["data"]
        elif kind == "end" and tag == "h3":
            markers.append(heading.strip())
            heading = None
        elif kind == "start" and "showcase-group" in (attrs.get("class") or "").split():
            markers.append("group:" + attrs["id"])
    assert markers == [
        "Published findings", "group:showcase-published",
        "Exploratory results", "group:showcase-exploratory",
        "Verified findings", "group:showcase-verified",
    ]


def test_the_renderer_fills_the_groups_and_says_when_no_record_exists():
    source = RENDERER.read_text(encoding="utf-8")
    assert "No showcase records yet" in source, "the tab must say when no record exists"
    for name in ("showcase-status", "showcase-published", "showcase-exploratory", "showcase-verified"):
        assert f"'{name}'" in source, f"the renderer must fill {name}"
    assert "renderFigures(data);" in source and "renderShowcases(data);" in source
    assert source.index("renderFigures(data);") < source.index("renderShowcases(data);"), (
        "renderFigures resets the theme list, so the showcase figures must be added after it")
    assert source.count("figureImages.push(") >= 2, "showcase figures must join the theme swap"


def _fixture_showcase_entry():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["showcases"]["entries"][0]


def test_the_page_renders_every_replication_field_of_the_fixture():
    replications = _fixture_showcase_entry()["replications"]
    fields = sorted({key for row in replications for key in row})
    assert fields, "the fixture must hold replications"
    source = RENDERER.read_text(encoding="utf-8")
    missing = [key for key in fields if f"row.{key}" not in source]
    assert not missing, f"the renderer does not read these replication fields: {missing}"


def test_the_page_renders_the_origin_line():
    origin = _fixture_showcase_entry()["origin"]
    assert sorted(origin) == ["author", "issue", "kind"]
    source = RENDERER.read_text(encoding="utf-8")
    assert "'Origin: '" in source, "each card must label its origin line"
    for key in sorted(origin):
        assert f"origin.{key}" in source, f"the origin line must read origin.{key}"


def test_the_validations_panel_renders_every_card():
    cards = json.loads(FIXTURE.read_text(encoding="utf-8"))["validations"]
    assert cards, "the fixture must hold validation cards"
    shown = ("title", "path", "commit", "sha256", "fields", "html", "recorded_commit")
    carried = {key for card in cards for key in card} - {"id", "section"}
    assert carried <= set(shown), f"cards carry fields the panel does not show: {carried - set(shown)}"
    source = RENDERER.read_text(encoding="utf-8")
    assert "renderValidations(data);" in source, "render() must call renderValidations"
    assert "document.getElementById('validation-table')" in source, "the panel container"
    assert "lookup(data, 'validations')" in source, "the panel reads the validations section"
    assert "Array.isArray(cards) ? cards : null" in source, "the table gets every card as a row"
    for key in shown:
        assert f"card.{key}" in source or f"field('{key}')" in source, (
            f"the panel must read card.{key}")


# ---- validation index, pages and verdict chips --------------------------------------------

VERDICT_CLASSES = ("reproduced", "reproduced (conditional)", "mixed", "in progress",
                   "not started", "failed")
VERDICT_SLUGS = ("reproduced", "reproduced-conditional", "mixed", "in-progress", "not-started",
                 "failed")


def _section_bounds(events, name):
    """The indices of the named section's start and its closing tag."""
    begin = next(i for i, (kind, tag, attrs) in enumerate(events)
                 if kind == "start" and tag == "section" and attrs.get("id") == name)
    end = next(i for i in range(begin + 1, len(events)) if events[i][:2] == ("end", "section"))
    return begin, end


def test_the_validation_tab_holds_the_index_and_the_pages():
    events = _events()
    begin, end = _section_bounds(events, "validation")
    inside = {attrs.get("id") for kind, tag, attrs in events[begin:end] if kind == "start"}
    for name in ("validation-index", "validation-index-search", "validation-index-table",
                 "validation-pages"):
        assert name in inside, f"{name} must sit in the validation tab"


def _style():
    match = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8"), re.S)
    assert match, "the template has no style block"
    return match.group(1)


def test_every_verdict_chip_takes_its_colour_from_the_theme_tokens():
    style = _style()
    for slug in VERDICT_SLUGS:
        rule = re.search(rf"\.chip-{slug}(?![\w-])[^{{]*\{{([^}}]*)\}}", style)
        assert rule, f"no chip style for {slug}"
        assert "var(--" in rule.group(1), f"chip-{slug} takes a fixed colour, not a theme token"
    assert "prefers-color-scheme: dark" in style and 'data-theme="dark"' in style, (
        "the chips need the dark theme the tokens define")


def test_the_renderer_names_every_verdict_class_and_reads_the_deferred_rows():
    source = RENDERER.read_text(encoding="utf-8")
    for label in VERDICT_CLASSES:
        assert f"'{label}'" in source, f"the page does not name the verdict {label!r}"
    assert "lookup(data, 'deferred')" in source, "the index reads the deferred section"


def test_the_renderer_builds_the_index_and_the_pages_and_shows_each_label():
    source = RENDERER.read_text(encoding="utf-8")
    assert "renderValidationIndex(data);" in source and "renderValidationPages(data);" in source
    assert "row.label" in source, "the replication table must show the dashboard label"


# ---- every route, in Chromium, in light and dark ----------------------------------------

REQUIRE_BROWSER = "JNWB_REQUIRE_BROWSER"
#: The pinned Plotly CDN address. Its requests are set aside: a machine without network access
#: cannot load it, and the page then shows its "Chart unavailable" note without an error of its own.
PLOTLY_URL = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """The dashboard built into a temporary directory by the builder the workflow runs."""
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    out = tmp_path_factory.mktemp("browser") / "site"
    importlib.import_module("scripts.build_dashboard").write_dashboard(out)
    return out


@pytest.fixture(scope="module")
def base_url(site):
    """The built site served over HTTP: the page fetches data.json, which file:// does not allow."""
    handler = functools.partial(_QuietHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


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


def _routes(site):
    """Every tab, the first validation page and the first deferred row, each with the heading
    that must be visible on it. The names come from the built data and the template."""
    data = json.loads((site / "data.json").read_text(encoding="utf-8"))
    entry = data["showcases"]["entries"][0]["id"]
    deferred = data["deferred"][0]["id"]
    tabs = [attrs["aria-controls"] for kind, tag, attrs in _events()
            if kind == "start" and tag == "button" and attrs.get("role") == "tab"]
    assert tabs, "the template names no tab"
    routes = [(tab, f"#{tab} h2") for tab in tabs]
    routes.append((f"validation/{entry}", f'article.validation-page[data-page="{entry}"] h5'))
    routes.append((f"validation/{deferred}", f'article.validation-page[data-page="{deferred}"] h3'))
    return routes


def _collect(page, problems):
    """Records what the page reports: uncaught errors, console errors and failed requests, except
    the Plotly CDN address (see PLOTLY_URL)."""
    page.on("pageerror", lambda exc: problems.append(f"page error: {exc}"))

    def on_console(msg):
        location = msg.location.get("url", "")
        if msg.type == "error" and not location.startswith(PLOTLY_URL):
            problems.append(f"console error: {msg.text} ({location})")

    def on_failed(request):
        if not request.url.startswith(PLOTLY_URL):
            problems.append(f"request failed: {request.url}")

    page.on("console", on_console)
    page.on("requestfailed", on_failed)


def test_every_route_renders_in_light_and_dark_without_errors(browser, base_url, site):
    sync_api = pytest.importorskip("playwright.sync_api")
    routes = _routes(site)
    checked, problems = [], []
    for route, heading in routes:
        backgrounds = {}
        for scheme in ("light", "dark"):
            label = f"#{route} ({scheme})"
            found = []
            context = browser.new_context(color_scheme=scheme)
            try:
                page = context.new_page()
                _collect(page, found)
                try:
                    page.goto(f"{base_url}/index.html#{route}", wait_until="networkidle")
                    page.locator(heading).first.wait_for(state="visible", timeout=10000)
                except sync_api.Error as exc:
                    found.append(f"{heading!r} is not visible: {str(exc).splitlines()[0]}")
                backgrounds[scheme] = page.evaluate(
                    "getComputedStyle(document.body).backgroundColor")
            finally:
                context.close()
            problems.extend(f"{label}: {problem}" for problem in found)
            checked.append(label)
        if backgrounds["light"] == backgrounds["dark"]:
            problems.append(f"#{route}: the body background is {backgrounds['light']} in both "
                            "light and dark")
    assert len(checked) == 2 * len(routes), checked
    assert not problems, "\n".join(problems)
