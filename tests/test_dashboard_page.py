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
