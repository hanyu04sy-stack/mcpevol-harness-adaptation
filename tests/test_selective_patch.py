import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_selective_patch import build, detect
from run_benchmark import load_harness, prepare_annotation_links, provider_model_id, resolve_run_output, select_task_harness_prompt, SHARED_COMPLETION_PROTOCOL
from experiment_config import ConfigError


def snapshot(tools, status='connected'):
    return dict(servers=[dict(name='server', status=status, tools=tools)])


class SelectivePatchTest(unittest.TestCase):
    def test_annotation_paths_work_from_agent_and_mcp_server_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            benchmark = project / 'external/MCPEvol-Bench'
            (benchmark / 'src').mkdir(parents=True)
            sample = benchmark / 'anotation_path/txt/log_yesterday.txt'
            sample.parent.mkdir(parents=True)
            sample.write_text('sample log')
            resolved = dict(project_root=project, benchmark_root=benchmark)
            links = prepare_annotation_links(resolved)
            self.assertEqual(len(links), 2)
            self.assertEqual((project / 'anotation_path/txt/log_yesterday.txt').read_text(), 'sample log')
            self.assertEqual((benchmark / 'src/anotation_path/txt/log_yesterday.txt').read_text(), 'sample log')
            for link in reversed(links):
                link.unlink()
            self.assertFalse((project / 'anotation_path').exists())

    def test_annotation_path_conflict_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            benchmark = project / 'external/MCPEvol-Bench'
            (benchmark / 'src').mkdir(parents=True)
            (benchmark / 'anotation_path').mkdir()
            conflict = project / 'anotation_path'
            conflict.mkdir()
            with self.assertRaises(ConfigError):
                prepare_annotation_links(dict(project_root=project, benchmark_root=benchmark))
            self.assertTrue(conflict.is_dir())
            self.assertFalse((benchmark / 'src/anotation_path').exists())

    def test_shared_completion_and_openrouter_alias(self):
        self.assertEqual(provider_model_id('gpt-4o-mini', 'https://openrouter.ai/api/v1'), 'openai/gpt-4o-mini')
        self.assertEqual(provider_model_id('gpt-4o-mini', None), 'gpt-4o-mini')
        self.assertEqual(provider_model_id('openai/gpt-4o-mini', 'https://openrouter.ai/api/v1'), 'openai/gpt-4o-mini')
        original = load_harness(ROOT / 'harness/original', json.loads((ROOT / 'harness/original/manifest.json').read_text())['benchmark_commit'])
        middle = load_harness(ROOT / 'harness/selective_patch/middle', json.loads((ROOT / 'harness/selective_patch/middle/manifest.json').read_text())['benchmark_commit'])
        self.assertIn(SHARED_COMPLETION_PROTOCOL, original['harness_prompt'])
        self.assertIn(SHARED_COMPLETION_PROTOCOL, middle['harness_prompt'])

    def test_task_scope_excludes_unrelated_tool_patches(self):
        directory = ROOT / 'harness/selective_patch/middle'
        commit = json.loads((directory / 'manifest.json').read_text())['benchmark_commit']
        loaded = load_harness(directory, commit)
        resolved = dict(harness_dir=directory, harness_prompt=loaded['harness_prompt'])
        prompt = select_task_harness_prompt(
            resolved,
            [{'name': 'validateMermaid'}, {'name': 'generate_flow_diagram'}],
            {'validateMermaid': '@rtuin/mcp-mermaid-validator', 'generate_flow_diagram': '@umengfe/mcp-server-chart'},
        )
        self.assertIn('### Tool @rtuin/mcp-mermaid-validator / validateMermaid', prompt)
        self.assertNotIn('### Tool coffee-mcp-agent', prompt)
        self.assertIn(SHARED_COMPLETION_PROTOCOL, prompt)
        self.assertLess(len(prompt), len(loaded['harness_prompt']) // 2)
        prompt.format(SET_TIME='now', FILE_EXISTS='files')

    def test_unknown_is_not_removal(self):
        changes, unknown = detect(snapshot([dict(name='x')]), snapshot([], 'failed'))
        self.assertEqual(changes, [])
        self.assertEqual(unknown, ['server'])

    def test_parameter_description_and_removal(self):
        a = [dict(name='x', description='old', inputSchema={'required': ['a']}), dict(name='gone')]
        b = [dict(name='x', description='new', inputSchema={'required': ['b']}), dict(name='added')]
        changes, unknown = detect(snapshot(a), snapshot(b))
        self.assertEqual(unknown, [])
        self.assertEqual({c['tool']: c['kinds'] for c in changes}, {'added': ['added'], 'gone': ['removed'], 'x': ['description', 'parameters']})

    def test_real_generation_injection_and_version_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'selective_patch'
            for version in ['early', 'middle']:
                out = base / version
                manifest = build(ROOT, version, out)
                self.assertEqual((out / 'system_prompt.md').read_bytes(), (ROOT / 'harness/original/system_prompt.md').read_bytes())
                loaded = load_harness(out, manifest['benchmark_commit'])
                prompt = loaded['harness_prompt'].format(SET_TIME='now', FILE_EXISTS='files')
                if version == 'early':
                    self.assertEqual(manifest['changed_tool_count'], 0)
                    self.assertEqual((out / 'tool_usage_rules.md').read_bytes(), (ROOT / 'harness/original/tool_usage_rules.md').read_bytes())
                else:
                    self.assertIn('Changed parameter contract', prompt)
                    self.assertIn('### Tool', prompt)
                resolved = dict(harness_dir=out, version=version, output_root=Path(temp) / 'results')
                self.assertIn('selective_patch', str(resolve_run_output(resolved, 1)))
                self.assertEqual(resolved['strategy'], 'selective_patch')
                resolved['version'] = 'late'
                with self.assertRaises(ConfigError):
                    resolve_run_output(resolved, 1)
            manifest = build(ROOT, 'late', base / 'late')
            self.assertTrue(manifest['formal_run_ready'])
            self.assertGreater(manifest['changed_tool_count'], 0)
            resolved = dict(harness_dir=base / 'late', version='late', output_root=base)
            self.assertIn('selective_patch/late', str(resolve_run_output(resolved, 1)))
            path = base / 'late' / 'manifest.json'
            data = json.loads(path.read_text())
            data['formal_run_ready'] = False
            path.write_text(json.dumps(data))
            with self.assertRaises(ConfigError):
                resolve_run_output(resolved, 1)


if __name__ == '__main__':
    unittest.main()
