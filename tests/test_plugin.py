"""Offline checks of packaging, installed status, preservation and workspace reuse."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from install_codex_plugin import (PLUGIN, MARKETPLACE, bind_workspace, export_package,
                                  install, merge_marketplace, plugin_status, prepare_workspace,
                                  public_files)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Windows TEMP can use an 8.3 alias; compare the same canonical form as the installer.
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / 'source'
        self.home = self.base / 'codex-home'
        self.repo.mkdir()
        self.home.mkdir()
        self.write(self.repo / 'plugin.json', json.dumps({'name': PLUGIN, 'version': '0.2.0'}))
        self.write(self.repo / 'scripts' / 'pipeline.py', '# public engine\n')
        self.write(self.repo / 'skills' / 'setup-knowledge' / 'SKILL.md', '# public skill\n')
        self.write(self.repo / 'docs' / 'assets' / 'workspace-redacted.png', 'synthetic image')
        self.write(self.repo / 'settings.example.json', '{}\n')
        self.write(self.repo / 'settings.local.json', '{"private": true}')
        self.write(self.repo / '.runtime' / 'data' / 'catalog.jsonl', 'private source paths')
        self.write(self.repo / '研究知识库' / '个人笔记.md', 'private note')
        self.write(self.repo / 'private' / 'secret.py', 'private credential')
        self.write(self.repo / 'skills' / 'setup-knowledge' / 'settings.local.json', 'private config')

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def test_portable_manifest_and_onboarding_resolve_inside_package(self):
        manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['name'], PLUGIN)
        self.assertEqual(manifest['$schema'], 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json')
        onboarding = manifest['extensions']['com.openai']['onboardingSkill']
        self.assertTrue(onboarding.startswith('./'))
        self.assertIn(ROOT, (ROOT / onboarding).resolve().parents)
        self.assertTrue((ROOT / onboarding).is_file())
        compatibility = json.loads((ROOT / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(compatibility['name'], manifest['name'])
        self.assertEqual(compatibility['version'], manifest['version'])
        self.assertEqual(compatibility['interface'], manifest['extensions']['com.openai']['interface'])
        self.assertEqual(compatibility['extensions']['com.openai']['onboardingSkill'], onboarding)
        catalog = json.loads((ROOT / '.agents' / 'plugins' / 'marketplace.json').read_text(encoding='utf-8'))
        entry = next(item for item in catalog['plugins'] if item['name'] == PLUGIN)
        # Marketplace paths resolve from the repo root, not the catalog's directory.
        self.assertEqual((ROOT / entry['source']['path']).resolve(), ROOT)
        self.assertEqual(entry['policy']['installation'], 'AVAILABLE')

    def test_export_excludes_private_runtime_vault_and_nested_configs(self):
        target = self.base / 'package'
        count = export_package(self.repo, target)
        self.assertEqual(count, 5)
        self.assertTrue((target / 'docs' / 'assets' / 'workspace-redacted.png').is_file())
        names = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
        self.assertEqual(names, {'plugin.json', 'scripts/pipeline.py',
                         'skills/setup-knowledge/SKILL.md', 'docs/assets/workspace-redacted.png', 'settings.example.json'})
        self.assertEqual((self.repo / 'settings.local.json').read_text(), '{"private": true}')

    def test_untracked_scratch_documents_and_raw_images_are_not_exported(self):
        self.write(self.repo / 'docs' / 'private.md', 'private scratch material')
        self.write(self.repo / 'docs' / 'assets' / 'raw-private.png', 'unredacted private screenshot')
        self.write(self.repo / 'docs' / 'assets' / 'unknown-child' / 'raw.png', 'private nested screenshot')
        self.write(self.repo / 'README.private.md', 'private personal draft')
        self.write(self.repo / 'scripts' / 'scratch.py', 'private temporary script')
        target = self.base / 'restricted-package'
        # A concrete list must not scan children, including unknown junctions.
        with patch('install_codex_plugin.os.walk', side_effect=AssertionError('Unexpected traversal')):
            export_package(self.repo, target)
        self.assertFalse((target / 'docs' / 'private.md').exists())
        self.assertFalse((target / 'docs' / 'assets' / 'raw-private.png').exists())
        self.assertFalse((target / 'docs' / 'assets' / 'unknown-child').exists())
        self.assertFalse((target / 'README.private.md').exists())
        self.assertFalse((target / 'scripts' / 'scratch.py').exists())

    def test_marketplace_merge_preserves_other_plugins_and_metadata(self):
        path = self.base / 'marketplace.json'
        other = {'name': 'unrelated', 'source': {'source': 'local', 'path': './keep'},
                 'policy': {'installation': 'AVAILABLE'}, 'custom': {'value': 17}}
        original = {'name': 'already-named', 'interface': {'displayName': 'Keep This'},
                    'plugins': [other], 'custom': True}
        self.write(path, json.dumps(original))
        name, previous = merge_marketplace(path, './packages/new')
        updated = json.loads(path.read_text())
        self.assertEqual(name, 'already-named')
        self.assertEqual(updated['plugins'][0], other)
        self.assertEqual(updated['interface'], original['interface'])
        self.assertTrue(updated['custom'])
        self.assertEqual(json.loads(previous.read_text()), original)
        merge_marketplace(path, './packages/newer')
        self.assertEqual(len(json.loads(path.read_text())['plugins']), 2)
        with self.assertRaises(ValueError):
            merge_marketplace(path, './../outside')

    def test_native_install_confirms_installed_and_enabled_and_backs_up_config(self):
        original = b'model = "existing-model"\n[plugins."unrelated@personal"]\nenabled = true\n'
        (self.home / 'config.toml').write_bytes(original)
        calls = []
        def fake_cli(executable, args, home):
            calls.append(args)
            if args == ['plugin', 'list', '--json']:
                return json.dumps({'installed': [{'pluginId': PLUGIN + '@' + MARKETPLACE,
                                   'installed': True, 'enabled': True}]})
            return '{}'
        with patch('install_codex_plugin.run_cli', side_effect=fake_cli):
            result = install(self.repo, self.home, 'codex-native')
        self.assertEqual(result['status'], 'installed')
        self.assertTrue(result['installed'] and result['enabled'])
        self.assertEqual(Path(result['config_backup']).read_bytes(), original)
        self.assertEqual((self.home / 'config.toml').read_bytes(), original)
        self.assertIn(['plugin', 'add', PLUGIN + '@' + MARKETPLACE, '--json'], calls)
        self.assertFalse((Path(result['package']) / 'settings.local.json').exists())
        self.assertEqual(result['export_policy'], 'explicit_public_paths')
        self.assertNotIn('private_files_copied', result)

    def test_status_reuses_native_installed_selector_without_mutation(self):
        snapshot = {'installed': [{'pluginId': PLUGIN + '@' + MARKETPLACE,
                    'installed': True, 'enabled': True, 'version': '0.2.0'}]}
        with patch('install_codex_plugin.run_cli', return_value=json.dumps(snapshot)) as cli:
            result = plugin_status(self.repo, self.home, 'codex-native')
        self.assertTrue(result['installed'] and result['enabled'])
        self.assertEqual(result['package_origin'], 'local_source')
        cli.assert_called_once_with('codex-native', ['plugin', 'list', '--json'], self.home)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_cached_plugin_status_does_not_require_recursive_installation(self):
        package = self.home / 'plugins' / 'cache' / MARKETPLACE / PLUGIN / '0.2.0'
        with patch('install_codex_plugin.run_cli') as cli:
            result = plugin_status(package, self.home, None)
        self.assertEqual(result['package_origin'], 'cached_plugin')
        self.assertIsNone(result['installed'])
        self.assertIsNone(result['enabled'])
        cli.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_registration_only_host_does_not_claim_plugin_installation(self):
        calls = []
        def older_cli(executable, args, home):
            calls.append(args)
            if args == ['plugin', 'add', '--help']:
                raise RuntimeError('unsupported command')
            return '{}'
        with patch('install_codex_plugin.run_cli', side_effect=older_cli):
            result = install(self.repo, self.home, 'older-codex')
        self.assertEqual(result['status'], 'marketplace_registered')
        self.assertFalse(result['installed'] or result['enabled'])
        self.assertNotIn(['plugin', 'list', '--json'], calls)

    def test_dry_run_does_not_mutate_or_invoke_cli(self):
        with patch('install_codex_plugin.run_cli') as cli:
            result = install(self.repo, self.home, None, dry_run=True)
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(list(self.home.iterdir()), [])
        cli.assert_not_called()

    def test_reconnect_reuses_exact_config_without_reimport_or_rewrite(self):
        source = self.base / 'material'
        workspace = self.base / 'existing-workspace'
        source.mkdir()
        workspace.mkdir()
        config = self.repo / 'settings.local.json'
        values = {'source': str(source), 'workspace': str(workspace), 'vault_name': 'Accepted Vault',
                  'language': 'en', 'custom_setting': 'preserve'}
        self.write(config, json.dumps(values))
        original = config.read_bytes()
        result = prepare_workspace(self.repo, config=config)
        self.assertEqual(result['files_copied'], 0)
        self.assertEqual(Path(result['config']), config)
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(list(workspace.iterdir()), [])
        first = bind_workspace(config, self.home)
        second = bind_workspace(config, self.home)
        registry = json.loads(Path(second['registry']).read_text())
        self.assertEqual(len(registry['workspaces']), 1)
        self.assertEqual(first['vault_name'], 'Accepted Vault')
        self.assertEqual(config.read_bytes(), original)

    def test_prepare_runtime_stays_outside_plugin_cache_and_preserves_local_config(self):
        workspace = self.base / 'stable'
        first = prepare_workspace(self.repo, workspace)
        tool = Path(first['tool_root'])
        self.assertIn(workspace, tool.parents)
        self.assertNotIn(self.repo, tool.parents)
        self.write(tool / 'settings.local.json', 'private stable config')
        self.write(tool / 'unrelated-note.md', 'accepted content')
        self.write(self.repo / 'scripts' / 'pipeline.py', '# improved public engine\n')
        prepare_workspace(self.repo, workspace)
        self.assertEqual((tool / 'settings.local.json').read_text(), 'private stable config')
        self.assertEqual((tool / 'unrelated-note.md').read_text(), 'accepted content')
        self.assertEqual((tool / 'scripts' / 'pipeline.py').read_text(), '# improved public engine\n')

    def test_package_link_cannot_read_or_overwrite_outside_material(self):
        external = self.base / 'external.py'
        self.write(external, 'must stay untouched')
        link = self.repo / 'scripts' / 'pipeline.py'
        link.unlink()
        try:
            link.symlink_to(external)
        except OSError:
            self.skipTest('Creating symlinks is unavailable on this host')
        with self.assertRaises(ValueError):
            public_files(self.repo)
        link.unlink()
        self.write(link, '# public engine\n')
        target = self.base / 'target'
        (target / 'scripts').mkdir(parents=True)
        (target / 'scripts' / 'pipeline.py').symlink_to(external)
        with self.assertRaises(ValueError):
            export_package(self.repo, target)
        self.assertEqual(external.read_text(), 'must stay untouched')


if __name__ == '__main__':
    unittest.main()
