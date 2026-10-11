"""Check the exact Git index before publishing. No recursive private-data reads."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ROOTS = {'scripts', 'tests', 'docs', '.github'}
ALLOWED_FILES = {'README.md', 'LICENSE', 'AGENTS.md', '.gitignore', '.gitattributes',
                 'requirements.txt', 'settings.example.json', 'Start.cmd', 'Refresh.cmd',
                 'Open.cmd', 'Enable-Weekly.cmd'}

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
    for name in files:
        p = Path(name)
        if name not in ALLOWED_FILES and p.parts[0] not in ALLOWED_ROOTS:
            rejected.append(name + ': outside source whitelist')
            continue
        if any(part in {'__pycache__', 'data', '研究知识库', 'private', '.runtime'} for part in p.parts) or name.endswith('.local.json'):
            rejected.append(name + ': private/generated path')
            continue
        blob = subprocess.run(['git', 'show', ':' + name], cwd=ROOT, capture_output=True, check=True).stdout
        if len(blob) > 500_000:
            rejected.append(name + ': unexpectedly large file')
        text = blob.decode('utf-8', errors='replace')
        normalized = text.replace('\\\\', '\\').replace('\\', '/').casefold()
        if any(v.replace('\\', '/').casefold() in normalized for v in machine_values):
            rejected.append(name + ': machine-specific local value')
        for path in re.findall(r"(?i)\b[A-Z]:[\\/][^\s`\"'<>]+", text):
            clean_path = path.rstrip('.,;').replace(chr(92) * 2, chr(92))
            if clean_path not in {'C:' + chr(92) + 'Research', 'C:' + '/Research'}:
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
