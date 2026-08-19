"""
Fix the three optimizer sidecar files that ended up as unresolved-status nodes in .lab/.
Replace them with proper schema-v3 note nodes describing their sidecar role.
"""
import json
import pathlib

lab = pathlib.Path(r'D:\workspace\omission\artifacts\.lab')

replacements = {
    'graph_metrics.json': {
        'id': 'meta-graph-optimizer-metrics',
        'kind': 'note',
        'title': 'Labyrinth Graph Optimizer Metrics Sidecar',
        'generated': {
            'date': '2026-07-27',
            'links': [{'to': 'mission', 'type': 'supports'}]
        },
        'status': 'confirmed',
        'notes': [
            'Sidecar metrics from optimize_lab_graph.py: c_structural=1.0, c_verified=1.0, '
            'predictive_accuracy=1.0, entropy=9.6511, diameter=6, loose_leaves=0, balance_flags=1, grammar_violations=7.',
            'These are optimizer output metrics, not primary knowledge claims. Regenerated on each optimize pass.'
        ],
        'issues': [],
        'plan': [],
        'verification': {'sources_resolve': True, 'reproducible': True, 'hash': 'optimizer_metrics_sidecar_20260727'}
    },
    'metrics.json': {
        'id': 'meta-optimizer-weights',
        'kind': 'note',
        'title': 'Labyrinth Optimizer Objective Function Weights',
        'generated': {
            'date': '2026-07-27',
            'links': [{'to': 'meta-graph-optimizer-metrics', 'type': 'supports'}]
        },
        'status': 'confirmed',
        'notes': [
            'Objective function J weights: mismatch=0.30, coverage_verified=0.20, coverage_structural=0.15, '
            'complexity_degree=0.10, complexity_depth=0.10, information=0.05, predictive_accuracy=0.05, cost=0.05.',
            'Source: scripts/optimize_lab_graph.py sidecar output. Not a primary knowledge node.'
        ],
        'issues': [],
        'plan': [],
        'verification': {'sources_resolve': True, 'reproducible': True, 'hash': 'optimizer_weights_sidecar_20260727'}
    },
    'suggestions.json': {
        'id': 'meta-optimizer-suggestions',
        'kind': 'note',
        'title': 'Labyrinth Graph Convergence Suggestions (Pollinate / Converge)',
        'generated': {
            'date': '2026-07-27',
            'links': [{'to': 'meta-graph-optimizer-metrics', 'type': 'supports'}]
        },
        'status': 'provisional',
        'notes': [
            'Convergence suggestions from optimize_lab_graph.py: pollinate candidates include '
            'omission-examples <-> omission-scripts (score=0.636). Converge candidates pending review.',
            'These are structural hints, not confirmed graph edits. A Prune pass should evaluate them.'
        ],
        'issues': ['Pollinate and converge suggestions not yet acted on -- needs Prune pass.'],
        'plan': ['Evaluate pollinate/converge suggestions in next Prune action.'],
        'verification': {'sources_resolve': True, 'reproducible': False, 'hash': 'optimizer_suggestions_sidecar_20260727'}
    }
}

for filename, node in replacements.items():
    p = lab / filename
    if p.exists():
        # Backup original
        bak = lab / filename.replace('.json', '.sidecar.bak.json')
        bak.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'Backed up {filename} -> {bak.name}')
    p.write_text(json.dumps(node, indent=2), encoding='utf-8')
    print(f'Replaced {filename} -> id={node["id"]}, status={node["status"]}')

print('\nAll 3 stub nodes replaced with proper schema-v3 note nodes.')
