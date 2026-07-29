"""
Audit Labyrinth grammar violations and fix them in place.
Valid kinds, statuses, and link types per schema-v3.
"""
import json
import pathlib

lab = pathlib.Path(r'D:\workspace\omission\artifacts\.lab')

VALID_KINDS = {'hypothesis', 'evidence', 'goal', 'plan', 'reflection', 'question', 'note', 'decision', 'checkpoint'}
VALID_STATUSES = {'unconfirmed', 'provisional', 'confirmed', 'contested', 'superseded'}
VALID_LINK_TYPES = {'supports', 'contradicts', 'derives_from', 'questions', 'refines', 'supersedes'}

violations = []
fixed = []

for p in sorted(lab.glob('*.json')):
    if 'bak' in p.name:
        continue
    try:
        n = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        violations.append(f'{p.name}: JSON parse error: {e}')
        continue

    changed = False
    kind = n.get('kind', '')
    status = n.get('status', '')

    if kind not in VALID_KINDS:
        violations.append(f'{p.name}: invalid kind={repr(kind)}')
        # Auto-fix common patterns
        if kind == '?' or kind == '':
            n['kind'] = 'note'
            changed = True
            fixed.append(f'{p.name}: kind {repr(kind)} -> note')

    if status not in VALID_STATUSES:
        violations.append(f'{p.name}: invalid status={repr(status)}')
        if status == '?' or status == '':
            n['status'] = 'confirmed'
            changed = True
            fixed.append(f'{p.name}: status {repr(status)} -> confirmed')

    # Fix raw string links
    links = n.get('generated', {}).get('links', [])
    new_links = []
    for link in links:
        if isinstance(link, str):
            violations.append(f'{p.name}: raw string link={repr(link[:40])}')
            new_links.append({'to': link, 'type': 'supports'})
            changed = True
            fixed.append(f'{p.name}: raw link {repr(link[:30])} -> dict')
        elif isinstance(link, dict):
            ltype = link.get('type', '')
            if ltype not in VALID_LINK_TYPES:
                violations.append(f'{p.name}: invalid link type={repr(ltype)} -> {link.get("to", "?")}')
                link['type'] = 'supports'
                changed = True
                fixed.append(f'{p.name}: link type {repr(ltype)} -> supports')
            new_links.append(link)
        else:
            new_links.append(link)

    if new_links != links and 'generated' in n:
        n['generated']['links'] = new_links
        changed = True

    if changed:
        p.write_text(json.dumps(n, indent=2), encoding='utf-8')

print(f'Grammar violations detected: {len(violations)}')
for v in violations:
    print(f'  VIOLATION: {v}')
print(f'\nFixes applied: {len(fixed)}')
for f in fixed:
    print(f'  FIX: {f}')
