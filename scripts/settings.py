"""Local configuration shared by workers. Never stores model credentials."""
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def within(path, parent):
    return path == parent or parent in path.parents

class Settings:
    def __init__(self, filename=None):
        self.filename = Path(filename or os.environ.get('RESEARCH_CONFIG', REPO / 'settings.local.json')).resolve()
        values = json.loads(self.filename.read_text(encoding='utf-8-sig'))
        def absolute(key, default=None):
            value = values.get(key, default)
            if not value:
                raise ValueError(f'Missing configuration: {key}')
            p = Path(value).expanduser()
            return (self.filename.parent / p).resolve() if not p.is_absolute() else p.resolve()
        self.source = absolute('source')
        self.workspace = absolute('workspace')
        self.vault = self.workspace / '研究知识库'
        self.data = self.workspace / 'data'
        self.timezone = values.get('timezone', 'Asia/Shanghai')
        self.obsidian = values.get('obsidian_exe', '')
        self.stable_project_ids = values.get('stable_project_ids', True)
        self.categories = values.get('categories', {})
        for label, keywords in self.categories.items():
            if re.search(r'[<>:"/\\|?*\[\]#^]', label) or not label.strip(' .') or not isinstance(keywords, list):
                raise ValueError('Category names must be valid note filenames; keywords must be lists')
        if not self.source.is_dir():
            raise ValueError('Source directory does not exist')
        if within(self.source, self.workspace):
            raise ValueError('Source must be separate from output; output cannot contain source')
        self.excluded = [self.workspace] + [Path(p).resolve() for p in values.get('exclude_paths', [])]
        if REPO != self.source and within(REPO, self.source):
            self.excluded.append(REPO)
        for p in [self.workspace, *self.workspace.parents]:
            if p.exists() and (p.is_symlink() or getattr(p.stat(), 'st_file_attributes', 0) & 0x400):
                raise ValueError('Output cannot be a link or reparse point')

    def is_excluded(self, path):
        return any(within(path, root) for root in self.excluded)

    def env(self):
        return {**os.environ, 'RESEARCH_CONFIG': str(self.filename), 'PYTHONUTF8': '1'}
