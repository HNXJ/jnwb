"""
tests/test_dashboard_page.py -- The dashboard template, its renderer and the data contract agree.

scripts/dashboard/app.js fills scripts/dashboard/index.html from data.json. These checks run
without a browser: the fixture validates against data.schema.json; every data-slot in the
template resolves in the fixture or is a derived slot the renderer computes; every element id
the renderer queries exists in the template; and every tab or card target names a section.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

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
