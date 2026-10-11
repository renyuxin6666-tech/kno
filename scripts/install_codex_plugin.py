"""Install this source-only plugin through Codex's native CLI and bind local workspaces.

Exports use concrete public paths; review their content before publication.
Local settings and generated vaults are excluded. The installer never edits
TOML directly or restarts the user's application.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = 'obsidian-knowledge-workspace'
MARKETPLACE = 'obsidian-knowledge'
PUBLIC_PATHS = frozenset({
    'plugin.json', '.codex-plugin/plugin.json', 'LICENSE', 'requirements.txt',
    'settings.example.json', 'AGENTS.md', '.gitattributes', 'README.md', 'README.en.md',
    'Start.cmd', 'Refresh.cmd', 'Open.cmd', 'Enable-Weekly.cmd',
    'scripts/settings.py', 'scripts/inventory_research.py', 'scripts/extract_document.py',
    'scripts/build_vault.py', 'scripts/pipeline.py', 'scripts/bootstrap.ps1',
    'scripts/schedule.ps1', 'scripts/audit_publication.py', 'scripts/install_codex_plugin.py',
    'skills/setup-knowledge/SKILL.md', 'skills/setup-knowledge/agents/openai.yaml',
    'skills/knowledge-retrieval/SKILL.md', 'skills/knowledge-retrieval/agents/openai.yaml',
    'skills/maintain-knowledge/SKILL.md', 'skills/maintain-knowledge/agents/openai.yaml',
    'docs/automation.md', 'docs/automation.en.md', 'docs/codex-plugin.md',
    'docs/privacy.md', 'docs/privacy.en.md', 'docs/release-notes.md',
    'docs/assets/README.md', 'docs/assets/hero.svg', 'docs/assets/weekly-flow.svg',
    'docs/assets/workspace-redacted.png', 'docs/assets/map-redacted.png',
})


def timestamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def assert_plain_path(path):
    """Do not overwrite a file through a symlink or Windows junction."""
    path = Path(os.path.abspath(path))
    # Check ancestors first, before inspecting a child through a junction.
    for candidate in (*reversed(path.parents), path):
        if candidate.is_symlink() or (candidate.exists() and
                getattr(candidate.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Managed output cannot contain links or reparse points')


def backup(path, directory=None):
    if not path.exists():
        return None
    parent = Path(directory) if directory else path.parent
    assert_plain_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / (path.name + '.before-knowledge-' + timestamp())
    shutil.copy2(path, target)
    return target


def write_json(path, value):
    assert_plain_path(path)
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8-sig') == content:
        return None
    previous = backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(content, encoding='utf-8', newline='\n')
    temporary.replace(path)
    return previous


def public_files(repo):
    """Exact public paths only; never traverse directories or inspect scratch files."""
    assert_plain_path(repo)
    repo = Path(repo).resolve()
    assert_plain_path(repo / 'plugin.json')
    manifest = read_json(repo / 'plugin.json')
    if manifest.get('name') != PLUGIN:
        raise ValueError('This installer only manages its own plugin package')
    paths = []
    for name in sorted(PUBLIC_PATHS):
        candidate = repo / name
        assert_plain_path(candidate)
        if candidate.is_file():
            paths.append(candidate)
    return paths


def package_digest(repo, files):
    digest = hashlib.sha256()
    for p in files:
        digest.update(p.relative_to(repo).as_posix().encode())
        digest.update(b'\0')
        digest.update(p.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def export_package(repo, destination):
    """Copy only public code; preserve private settings and unrelated existing files."""
    assert_plain_path(destination)
    repo, destination = Path(repo).resolve(), Path(destination).resolve()
    if destination == repo:
        raise ValueError('Package export needs a separate destination')
    if (destination / 'plugin.json').exists():
        if read_json(destination / 'plugin.json').get('name') != PLUGIN:
            raise ValueError('Destination belongs to a different plugin')
    files = public_files(repo)
    for source in files:
        target = destination / source.relative_to(repo)
        assert_plain_path(target)
        if target.exists() and target.read_bytes() == source.read_bytes():
            continue
        if target.exists():
            backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return len(files)


def merge_marketplace(path, relative_source):
    if not relative_source.startswith('./') or '..' in Path(relative_source).parts:
        raise ValueError('Marketplace source must be a contained ./-prefixed path')
    value = read_json(path) if path.exists() else {
        'name': MARKETPLACE,
        'interface': {'displayName': 'Obsidian Knowledge Workspace'},
        'plugins': []}
    if not isinstance(value.get('plugins'), list) or not value.get('name'):
        raise ValueError('Existing marketplace has an invalid shape; left unchanged')
    owned = {
        'name': PLUGIN,
        'source': {'source': 'local', 'path': relative_source},
        'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
        'category': 'Productivity'}
    indices = [i for i, item in enumerate(value['plugins']) if item.get('name') == PLUGIN]
    if len(indices) > 1:
        raise ValueError('Duplicate owned plugin entries need review; left unchanged')
    if indices:
        previous = value['plugins'][indices[0]]
        # Keep custom metadata on our entry, and never alter the other entries.
        value['plugins'][indices[0]] = {**previous, **owned}
    else:
        value['plugins'].append(owned)
    previous = write_json(path, value)
    return value['name'], previous


def codex_home(explicit=None):
    return Path(explicit or os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser().resolve()


def native_codex(explicit=None):
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    # Prefer the native npm payload on Windows, avoiding a shell wrapper.
    if os.name == 'nt':
        wrapper = shutil.which('codex.cmd')
        if wrapper:
            npm = Path(wrapper).parent / 'node_modules' / '@openai'
            candidates = list((npm / 'codex').glob('vendor/*/codex/codex.exe'))
            candidates += list((npm / 'codex').glob('vendor/*/bin/codex.exe'))
            candidates += list((npm / 'codex' / 'node_modules' / '@openai').glob(
                'codex-*/vendor/*/bin/codex.exe'))
            candidates += list((Path(wrapper).parent / 'node_modules' / '@openai').glob(
                'codex-*/vendor/*/codex/codex.exe'))
            candidates += list(npm.glob('codex-*/vendor/*/bin/codex.exe'))
            if candidates:
                return str(candidates[0])
    return shutil.which('codex')


def run_cli(executable, args, home):
    result = subprocess.run([executable, *args], capture_output=True, text=True,
                            encoding='utf-8', env={**os.environ, 'CODEX_HOME': str(home)},
                            timeout=120)
    if result.returncode:
        raise RuntimeError('Codex command failed: ' + (result.stderr or result.stdout)[-1500:].strip())
    return result.stdout


def plugin_status(repo, home, executable):
    """Read native installation state without installing, upgrading or writing."""
    repo, home = Path(repo).resolve(), Path(home).resolve()
    cached = home / 'plugins' / 'cache'
    origin = 'cached_plugin' if cached in repo.parents else 'local_source'
    catalog = home / 'plugins' / 'local' / MARKETPLACE / '.agents' / 'plugins' / 'marketplace.json'
    marketplace = read_json(catalog).get('name', MARKETPLACE) if catalog.exists() else MARKETPLACE
    selector = PLUGIN + '@' + marketplace
    base = {'selector': selector, 'package_origin': origin, 'cli_available': bool(executable)}
    if not executable:
        return {**base, 'status': 'installation_unknown', 'installed': None, 'enabled': None}
    try:
        snapshot = json.loads(run_cli(executable, ['plugin', 'list', '--json'], home))
    except (RuntimeError, ValueError) as error:
        return {**base, 'status': 'installation_unknown', 'installed': None, 'enabled': None,
                'error': str(error)}
    entry = next((item for item in snapshot.get('installed', [])
                  if item.get('pluginId') == selector), None)
    installed = bool(entry and entry.get('installed'))
    enabled = bool(entry and entry.get('enabled'))
    return {**base, 'status': 'installed' if installed and enabled else 'not_enabled',
            'installed': installed, 'enabled': enabled,
            'version': entry.get('version') if entry else None}


def install(repo, home, executable, dry_run=False):
    repo, home = Path(repo).resolve(), Path(home).resolve()
    manifest = read_json(repo / 'plugin.json')
    files = public_files(repo)
    digest = package_digest(repo, files)
    root = home / 'plugins' / 'local' / MARKETPLACE
    relative = './packages/' + manifest['version'] + '-' + digest[:12]
    package = root / relative[2:]
    catalog = root / '.agents' / 'plugins' / 'marketplace.json'
    plan = {'plugin': PLUGIN, 'marketplace_root': str(root), 'package': str(package),
            'source_files': len(files), 'package_sha256': digest,
            'export_policy': 'explicit_public_paths',
            'package_files': [p.relative_to(repo).as_posix() for p in files],
            'dry_run': dry_run}
    if dry_run:
        return {**plan, 'status': 'planned', 'installed': False, 'enabled': False}
    if not executable:
        raise RuntimeError('Codex CLI was not found. Install Codex CLI or use the repo marketplace in the desktop app.')
    # Check support before changing local catalogs or configuration.
    run_cli(executable, ['plugin', 'marketplace', 'add', '--help'], home)
    try:
        run_cli(executable, ['plugin', 'add', '--help'], home)
        can_install = True
    except RuntimeError:
        can_install = False
    export_package(repo, package)
    marketplace, _ = merge_marketplace(catalog, relative)
    config_backup = backup(home / 'config.toml', root / 'backups')
    run_cli(executable, ['plugin', 'marketplace', 'add', str(root), '--json'], home)
    if not can_install:
        return {**plan, 'status': 'marketplace_registered', 'installed': False, 'enabled': False,
                'marketplace': marketplace, 'config_backup': str(config_backup) if config_backup else None,
                'next': 'Refresh or restart the desktop app, install this plugin from the local marketplace, then run setup.'}
    selector = PLUGIN + '@' + marketplace
    run_cli(executable, ['plugin', 'add', selector, '--json'], home)
    snapshot = json.loads(run_cli(executable, ['plugin', 'list', '--json'], home))
    entry = next((item for item in snapshot.get('installed', [])
                  if item.get('pluginId') == selector), None)
    verified = bool(entry and entry.get('installed') and entry.get('enabled'))
    return {**plan, 'status': 'installed' if verified else 'installation_unconfirmed',
            'installed': bool(entry and entry.get('installed')), 'enabled': bool(entry and entry.get('enabled')),
            'marketplace': marketplace, 'selector': selector,
            'config_backup': str(config_backup) if config_backup else None,
            'next': 'Open a new Codex conversation or refresh the app and run $setup-knowledge. Existing chats may not discover new skills until refreshed.'}


def absolute_setting(config, values, key):
    path = Path(values[key]).expanduser()
    return path.resolve() if path.is_absolute() else (config.parent / path).resolve()


def bind_workspace(config, home):
    config = Path(config).resolve()
    values = read_json(config)
    workspace = absolute_setting(config, values, 'workspace')
    source = absolute_setting(config, values, 'source')
    if not source.is_dir() or not workspace.is_dir():
        raise ValueError('Bind an existing source and prepared workspace')
    if not (config.parent / 'scripts' / 'pipeline.py').is_file():
        raise ValueError('The configuration must belong to a complete pipeline installation')
    registry = Path(home) / PLUGIN / 'workspaces.json'
    value = read_json(registry) if registry.exists() else {'workspaces': []}
    if not isinstance(value.get('workspaces'), list):
        raise ValueError('Invalid workspace registry; left unchanged')
    entry = {'workspace': str(workspace), 'config': str(config), 'tool_root': str(config.parent),
             'language': values.get('language', 'zh'),
             'vault_name': values.get('vault_name', '研究知识库')}
    matches = [i for i, item in enumerate(value['workspaces']) if item.get('workspace') == str(workspace)]
    if matches:
        value['workspaces'][matches[0]] = entry
    else:
        value['workspaces'].append(entry)
    write_json(registry, value)
    return {'status': 'workspace_bound', **entry, 'registry': str(registry)}


def prepare_workspace(repo, workspace=None, config=None):
    if config:
        config = Path(config).resolve()
        values = read_json(config)
        if not (config.parent / 'scripts' / 'pipeline.py').is_file():
            raise ValueError('Existing config must belong to a pipeline installation')
        return {'status': 'existing_workspace_reused',
                'workspace': str(absolute_setting(config, values, 'workspace')),
                'tool_root': str(config.parent), 'config': str(config), 'files_copied': 0}
    if not workspace:
        raise ValueError('Choose a workspace folder for the generated knowledge base')
    workspace = Path(workspace).expanduser().resolve()
    tool = workspace / '.knowledge-tools' / PLUGIN
    count = export_package(repo, tool)
    return {'status': 'runtime_prepared', 'workspace': str(workspace), 'tool_root': str(tool),
            'config': str(tool / 'settings.local.json'), 'files_copied': count,
            'next': 'Run this stable tool root\'s bootstrap.ps1 on Windows, then bind its config. Source files have not been imported yet.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('install', help='Install through the native Codex plugin CLI')
    p.add_argument('--repo-root', default=str(REPO))
    p.add_argument('--codex-home')
    p.add_argument('--codex')
    p.add_argument('--dry-run', action='store_true')
    p = commands.add_parser('status', help='Read native plugin installation state without changes')
    p.add_argument('--repo-root', default=str(REPO))
    p.add_argument('--codex-home')
    p.add_argument('--codex')
    p = commands.add_parser('prepare-workspace', help='Prepare stable tools or reuse an explicitly linked config')
    p.add_argument('--repo-root', default=str(REPO))
    p.add_argument('--workspace')
    p.add_argument('--config')
    p = commands.add_parser('bind-workspace', help='Remember an explicitly linked local workspace')
    p.add_argument('--config', required=True)
    p.add_argument('--codex-home')
    p = commands.add_parser('workspaces', help='List only the local workspaces linked to this plugin')
    p.add_argument('--codex-home')
    args = parser.parse_args()
    if args.command == 'install':
        result = install(args.repo_root, codex_home(args.codex_home), native_codex(args.codex), args.dry_run)
    elif args.command == 'status':
        result = plugin_status(args.repo_root, codex_home(args.codex_home), native_codex(args.codex))
    elif args.command == 'prepare-workspace':
        result = prepare_workspace(args.repo_root, args.workspace, args.config)
    elif args.command == 'bind-workspace':
        result = bind_workspace(args.config, codex_home(args.codex_home))
    else:
        registry = codex_home(args.codex_home) / PLUGIN / 'workspaces.json'
        result = read_json(registry) if registry.exists() else {'workspaces': []}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, KeyError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
