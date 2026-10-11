"""Local configuration shared by workers. Never stores model credentials."""
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO = Path(__file__).resolve().parent.parent

# One layout contract is used by the generator, retrieval, launcher and upkeep.
# Legacy configs deliberately keep their original names. Adding localization is
# never an implicit migration of an existing personal vault.
LAYOUTS = {
    'zh': {
        'start': '00_开始', 'projects': '01_项目', 'sources': '02_资料',
        'notes': '03_我的笔记', 'files': '04_目录清单', 'topics': '05_主题',
        'templates': '06_模板', 'attachments': '07_附件',
        'home': '00_开始/首页.md', 'navigation': '00_开始/项目导航.md',
        'map': '00_开始/我的知识地图.md', 'guide': '00_开始/如何使用.md',
        'codex': '00_开始/与 Codex 一起工作.md',
        'profile': '03_我的笔记/我的近况.md', 'coverage': '00_开始/导入覆盖与缺口.md',
        'canvas': '知识全景.canvas', 'automation': '03_我的笔记/自动整理',
        'diary': '03_我的笔记/日记', 'knowledge_template': '06_模板/知识笔记.md',
        'decision_template': '06_模板/决策记录.md', 'reading_template': '06_模板/阅读笔记.md',
        'daily_template': '06_模板/每日记录.md',
    },
    'en': {
        'start': '00_Start', 'projects': '01_Projects', 'sources': '02_Sources',
        'notes': '03_My_Notes', 'files': '04_File_Lists', 'topics': '05_Topics',
        'templates': '06_Templates', 'attachments': '07_Attachments',
        'home': '00_Start/Home.md', 'navigation': '00_Start/Project Navigation.md',
        'map': '00_Start/My Knowledge Map.md', 'guide': '00_Start/Getting Started.md',
        'codex': '00_Start/Working with Codex.md',
        'profile': '03_My_Notes/My Current Focus.md', 'coverage': '00_Start/Coverage and Gaps.md',
        'canvas': 'Knowledge Overview.canvas', 'automation': '03_My_Notes/Automatic Reviews',
        'diary': '03_My_Notes/Daily', 'knowledge_template': '06_Templates/Knowledge Note.md',
        'decision_template': '06_Templates/Decision Record.md', 'reading_template': '06_Templates/Reading Note.md',
        'daily_template': '06_Templates/Daily Note.md',
    },
}
LEGACY_LAYOUT = {**LAYOUTS['zh'],
    'topics': '05_研究主题', 'map': '00_开始/我的研究地图.md',
    'codex': '00_开始/让 Codex 了解我的研究.md', 'profile': '03_我的笔记/我的研究近况.md',
    'canvas': '研究全景.canvas', 'knowledge_template': '06_模板/研究笔记.md',
    'decision_template': '06_模板/设计判断.md', 'reading_template': '06_模板/文献阅读.md',
}
LABELS = {
    'home': ('首页', 'Home'), 'navigation': ('项目导航', 'Project Navigation'),
    'map': ('我的知识地图', 'My Knowledge Map'), 'guide': ('如何使用', 'Getting Started'),
    'codex': ('与 Codex 一起工作', 'Working with Codex'),
    'profile': ('我的近况', 'My Current Focus'), 'coverage': ('导入覆盖与缺口', 'Coverage and Gaps'),
    'canvas': ('知识全景', 'Knowledge Overview'),
    'knowledge_template': ('知识笔记', 'Knowledge Note'), 'decision_template': ('决策记录', 'Decision Record'),
    'reading_template': ('阅读笔记', 'Reading Note'), 'daily_template': ('每日记录', 'Daily Note'),
}

def validate_vault_name(name):
    if (not isinstance(name, str) or not name or name != name.strip(' .')
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
        raise ValueError('vault_name must be a single valid folder name')
    return name

def default_categories(language):
    groups = [
        ('工作与项目', 'Work and Projects', ['work', 'project', 'client', '工作', '项目', '客户']),
        ('学习与阅读', 'Learning and Reading', ['learn', 'course', 'book', '学习', '课程', '阅读']),
        ('生活与计划', 'Life and Planning', ['life', 'travel', 'plan', '生活', '旅行', '计划']),
        ('研究与探索', 'Research and Exploration', ['research', 'experiment', 'paper', '研究', '实验', '论文']),
        ('个人记录', 'Personal Notes', ['journal', 'note', 'reflection', '日记', '笔记', '反思']),
    ]
    return {zh if language == 'zh' else en: keywords for zh, en, keywords in groups}

def resolve_timezone(name=None):
    """Persist an IANA name so future timestamps retain daylight-saving rules."""
    if name is None or name == '':
        try:
            from tzlocal import get_localzone_name
            name = get_localzone_name()
        except ImportError:
            raise ValueError('Install requirements.txt or provide --timezone with an IANA timezone') from None
        except (ValueError, OSError, RuntimeError):
            raise ValueError('Local timezone could not be detected; provide --timezone with an IANA timezone') from None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError('Use a valid IANA timezone, for example America/New_York or Europe/London') from None
    return name

def within(path, parent):
    return path == parent or parent in path.parents

class Settings:
    def __init__(self, filename=None):
        self.filename = Path(filename or os.environ.get('KNOWLEDGE_CONFIG') or os.environ.get('RESEARCH_CONFIG', REPO / 'settings.local.json')).resolve()
        values = json.loads(self.filename.read_text(encoding='utf-8-sig'))
        def absolute(key, default=None):
            value = values.get(key, default)
            if not value:
                raise ValueError(f'Missing configuration: {key}')
            p = Path(value).expanduser()
            return (self.filename.parent / p).resolve() if not p.is_absolute() else p.resolve()
        self.source = absolute('source')
        self.workspace = absolute('workspace')
        self.language = values.get('language', 'zh')
        if self.language not in LAYOUTS:
            raise ValueError('language must be zh or en')
        self.legacy_layout = 'language' not in values and 'vault_name' not in values
        default_name = '研究知识库' if self.legacy_layout else ('个人知识库' if self.language == 'zh' else 'Personal Knowledge')
        self.vault_name = validate_vault_name(values.get('vault_name', default_name))
        self.layout = dict(LEGACY_LAYOUT if self.legacy_layout else LAYOUTS[self.language])
        self.vault = self.workspace / self.vault_name
        self.data = self.workspace / 'data'
        # Legacy absent-key behavior is retained; new configs detect and persist
        # their system's IANA zone instead of inferring geography from language.
        self.timezone = resolve_timezone(values.get('timezone', 'Asia/Shanghai' if self.legacy_layout else None))
        self.obsidian = values.get('obsidian_exe', '')
        self.stable_project_ids = values.get('stable_project_ids', True)
        self.categories = values.get('categories', {} if self.legacy_layout else default_categories(self.language))
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

    def rel(self, key):
        return self.layout[key]

    def path(self, key):
        return self.vault / self.rel(key)

    def text(self, zh, en):
        return zh if self.language == 'zh' else en

    def label(self, key):
        return self.text(*LABELS[key])

    @property
    def product_name(self):
        return self.text('Obsidian 个人知识工作台', 'Obsidian Knowledge Workspace')

    def env(self):
        return {**os.environ, 'KNOWLEDGE_CONFIG': str(self.filename), 'RESEARCH_CONFIG': str(self.filename), 'PYTHONUTF8': '1'}
