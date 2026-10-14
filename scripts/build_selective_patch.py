#!/usr/bin/env python3
"""Generate version-specific, schema-grounded patches without model calls."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from diff_tool_schemas import parameter_changes

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def detect(before, after):
    """Compare connected servers only; failed discovery is never removal."""
    old = {s['name']: s for s in before['servers']}
    new = {s['name']: s for s in after['servers']}
    changes, unknown = [], []
    for server in sorted(set(old) | set(new)):
        a, b = old.get(server), new.get(server)
        if not a or not b or a['status'] != 'connected' or b['status'] != 'connected':
            unknown.append(server)
            continue
        aa = {t['name']: t for t in a['tools']}
        bb = {t['name']: t for t in b['tools']}
        for name in sorted(set(aa) | set(bb)):
            x, y = aa.get(name), bb.get(name)
            kinds = []
            if x is None:
                kinds = ['added']
            elif y is None:
                kinds = ['removed']
            else:
                for key, kind in [('description', 'description'), ('inputSchema', 'parameters'), ('outputSchema', 'output'), ('annotations', 'annotations')]:
                    if x.get(key) != y.get(key):
                        kinds.append(kind)
            if kinds:
                changes.append(dict(server=server, tool=name, kinds=kinds, before=x, after=y))
    return changes, unknown


def render(changes):
    sections = []
    for c in changes:
        lines = [f"### Tool {c['server']} / {c['tool']}"]
        target = c['after']
        if target is None:
            lines.append('This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.')
        else:
            lines.append('Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.')
            if 'added' in c['kinds']:
                lines.append('This tool is newly available. Purpose: ' + encode(target.get('description', '')[:240]))
            if 'description' in c['kinds']:
                before_lines = (c['before'] or {}).get('description', '').splitlines()
                after_lines = target.get('description', '').splitlines()
                additions = [line[2:] for line in difflib.ndiff(before_lines, after_lines) if line.startswith('+ ') and line[2:].strip()]
                lines.append('Updated description guidance: ' + encode(additions or after_lines))
            if 'parameters' in c['kinds']:
                delta = parameter_changes((c['before'] or {}).get('inputSchema', {}), target.get('inputSchema', {}))
                lines.append('Changed parameter contract (current values under after): ' + encode(delta))
                required = target.get('inputSchema', {}).get('required', [])
                if required:
                    lines.append('Current required fields: ' + encode(required))
            for key, kind in [('outputSchema', 'output'), ('annotations', 'annotations')]:
                if kind in c['kinds']:
                    lines.append('Current ' + key + ': ' + encode(target.get(key)))
        # The upstream agent formats the whole prompt with str.format.
        sections.append('\n'.join(lines).replace('{', '{{').replace('}', '}}'))
    return '\n\n'.join(sections)


def build(root, target, output, allow_incomplete=False):
    started = time.perf_counter()
    paths = [root / 'harness/original' / n for n in ('system_prompt.md', 'tool_usage_rules.md', 'manifest.json')]
    paths += [root / f'reports/tool-schemas/{v}.json' for v in dict.fromkeys(['early', target])]
    original = json.loads(paths[2].read_text())
    before = json.loads((root / 'reports/tool-schemas/early.json').read_text())
    after = json.loads((root / f'reports/tool-schemas/{target}.json').read_text())
    commit = original['benchmark_commit']
    if before['benchmark_commit'] != commit or after['benchmark_commit'] != commit:
        raise ValueError('Snapshot benchmark commits must match the original harness.')
    if before['version'] != 'early' or after['version'] != target:
        raise ValueError('Snapshot version does not match its requested version.')
    changes, unknown = detect(before, after)
    if unknown and not allow_incomplete:
        raise ValueError('Incomplete schema discovery; regenerate snapshots before a formal run. Unknown servers: ' + ', '.join(unknown))
    rules = paths[1].read_text()
    patch = render(changes)
    if patch:
        marker = '\n## Routing reference'
        if marker not in rules:
            raise ValueError('Original rules must have a Routing reference section.')
        rules = rules.replace(marker, '\n\n' + patch + '\n' + marker, 1)
    manifest = dict(schema_version=1, strategy='selective_patch', benchmark_commit=commit,
        generated_at=datetime.now(timezone.utc).isoformat(), from_version='early', target_version=target,
        formal_run_ready=not unknown, unknown_servers=unknown,
        adaptation_method=dict(name='schema_grounded_selective_patch', scope='changed tool contracts only', rename_policy='No inferred aliases; removals and additions remain separate.'),
        source_files=[dict(path=p.relative_to(root).as_posix(), sha256=digest(p)) for p in paths],
        adaptation_cost=dict(generation_mode='deterministic', api_prompt_tokens=0, api_completion_tokens=0, api_cost_usd=0,
            generation_seconds=time.perf_counter()-started, patch_utf8_bytes=len(patch.encode()),
            notes='Generation time excludes environment setup and runtime inference. Prompt tokens are not estimated.'),
        changed_tool_count=len(changes))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'system_prompt.md').write_bytes(paths[0].read_bytes())
    (output / 'tool_usage_rules.md').write_text(rules)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + '\n')
    (output / 'patch-audit.json').write_text(json.dumps(dict(changes=changes, unknown_servers=unknown), indent=2, ensure_ascii=True) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['early', 'middle', 'late'], required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-incomplete', action='store_true', help='Preview only: omit unknown servers and mark the manifest as not ready.')
    args = parser.parse_args()
    output = args.output or ROOT / 'harness/selective_patch' / args.target
    try:
        result = build(ROOT, args.target, output, args.allow_incomplete)
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(dict(output=str(output), changed_tool_count=result['changed_tool_count'], formal_run_ready=result['formal_run_ready'])))


if __name__ == '__main__':
    main()
