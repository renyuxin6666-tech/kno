"""Check the exact Git index before publishing. No recursive private-data reads."""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ROOTS = {'scripts', 'tests', 'docs', '.github', 'skills'}
ALLOWED_FILES = {'README.md', 'README.en.md', 'plugin.json', '.agents/plugins/marketplace.json',
                 '.codex-plugin/plugin.json', 'LICENSE', 'AGENTS.md', '.gitignore', '.gitattributes',
                 'requirements.txt', 'settings.example.json', 'Start.cmd', 'Refresh.cmd',
                 'Open.cmd', 'Enable-Weekly.cmd'}
REVIEWED_IMAGES = {'docs/assets/workspace-redacted.png', 'docs/assets/map-redacted.png'}

def png_metadata(blob):
    """Check a reviewed PNG container; never treat raw pixels as UTF-8 text."""
    if not blob.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('not a PNG')
    offset = 8
    width = height = 0
    while offset + 12 <= len(blob):
        size = struct.unpack('>I', blob[offset:offset + 4])[0]
        kind = blob[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(blob):
            raise ValueError('truncated PNG chunk')
        if kind == b'IHDR':
            width, height = struct.unpack('>II', blob[offset + 8:offset + 16])
        if kind in {b'tEXt', b'zTXt', b'iTXt', b'eXIf'}:
            raise ValueError('unreviewed embedded text or EXIF metadata')
        offset = end
        if kind == b'IEND':
            if offset != len(blob) or not width or not height:
                raise ValueError('invalid PNG ending or dimensions')
            return {'width': width, 'height': height, 'embedded_text': False}
    raise ValueError('missing PNG ending')

def main():
    proc = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True)
    files = [s for s in proc.stdout.decode('utf-8').split('\0') if s]
    rejected = []
    manifest = []
    # These values are local only; the scanner never prints them or adds them to Git.
    machine_values = [os.environ.get('USERPROFILE', ''), os.environ.get('USERNAME', '')]
    local_config = ROOT / 'settings.local.json'
    if local_config.exists():
        values = json.loads(local_config.read_text(encoding='utf-8-sig'))
        machine_values += [values.get('source', ''), values.get('workspace', ''), values.get('obsidian_exe', '')]
    machine_values = [v for v in machine_values if len(v) >= 5]
    origin = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT,
                            capture_output=True).stdout.decode('utf-8', errors='replace').strip()
    public_origin = urlsplit(origin)
    public_repo = (public_origin.path.removesuffix('.git').strip('/')
                   if public_origin.hostname == 'github.com' and not public_origin.username else '')
    for name in files:
        p = Path(name)
        if name not in ALLOWED_FILES and p.parts[0] not in ALLOWED_ROOTS:
            rejected.append(name + ': outside source whitelist')
            continue
        if any(part in {'__pycache__', 'data', '研究知识库', '个人知识库', 'Personal Knowledge', 'private', '.runtime', '.knowledge-tools'} for part in p.parts) or name.endswith('.local.json'):
            rejected.append(name + ': private/generated path')
            continue
        blob = subprocess.run(['git', 'show', ':' + name], cwd=ROOT, capture_output=True, check=True).stdout
        if name in REVIEWED_IMAGES:
            try:
                dimensions = png_metadata(blob)
            except ValueError as exc:
                rejected.append(name + ': ' + str(exc))
                continue
            if len(blob) > 2_000_000:
                rejected.append(name + ': unexpectedly large screenshot')
            manifest.append({'file': name, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
                             'review': 'visually reviewed redacted screenshot', **dimensions})
            continue
        if p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.zip'}:
            rejected.append(name + ': unreviewed binary asset')
            continue
        if len(blob) > 500_000:
            rejected.append(name + ': unexpectedly large file')
        text = blob.decode('utf-8', errors='replace')
        normalized = text.replace('\\\\', '\\').replace('\\', '/').casefold()
        # The public origin's account/repository is intentionally visible in badges
        # and links. Its matching username substring is not a local filesystem leak.
        machine_scan = normalized
        if public_repo:
            owner = public_repo.split('/')[0]
            for host in ('github.com/', 'raw.githubusercontent.com/',
                         'img.shields.io/github/actions/workflow/status/'):
                machine_scan = machine_scan.replace((host + public_repo).casefold(), 'public-repository')
            machine_scan = machine_scan.replace(('github.com/' + owner).casefold(), 'public-project-owner')
            # Native Codex also accepts the public origin as an owner/repo selector.
            machine_scan = machine_scan.replace(public_repo.casefold(), 'public-repository-selector')
        if any(v.replace('\\', '/').casefold() in machine_scan for v in machine_values):
            rejected.append(name + ': machine-specific local value')
        for path in re.findall(r"(?i)\b[A-Z]:[\\/][^\s`\"'<>]+", text):
            clean_path = path.rstrip('.,;').replace(chr(92) * 2, chr(92))
            if clean_path not in {'C:' + chr(92) + 'Research', 'C:' + '/Research',
                                  'C:' + chr(92) + 'Knowledge', 'C:' + '/Knowledge'}:
                rejected.append(name + ': unexpected absolute Windows path')
        if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,})', text):
            rejected.append(name + ': possible token')
        if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text):
            rejected.append(name + ': unexpected email address')
        manifest.append({'file': name, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()})
    print(f'Publication audit: {len(files)} indexed source files, {len(rejected)} rejected')
    for failure in rejected:
        print(failure)
    if not rejected:
        print(json.dumps({'scope': 'exact Git index blobs, reviewed source whitelist', 'files': manifest}, indent=2))
    return 1 if rejected or not files else 0

if __name__ == '__main__':
    raise SystemExit(main())
