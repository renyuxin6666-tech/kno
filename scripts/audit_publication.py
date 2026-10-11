"""Check the exact Git index before publishing. No recursive private-data reads."""
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
        if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,})', text):
            rejected.append(name + ': possible token')
    print(f'Publication audit: {len(files)} indexed source files, {len(rejected)} rejected')
    for failure in rejected:
        print(failure)
    return 1 if rejected or not files else 0

if __name__ == '__main__':
    raise SystemExit(main())
