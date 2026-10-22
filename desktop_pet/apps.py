"""Application identity, friendly names and usage categories.

The tracker only ever stores a canonical app id and seconds. Window titles are
used transiently to disambiguate hosts such as java.exe; they are never stored.
"""
import ctypes
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

IS_WINDOWS = os.name == 'nt'

CATEGORIES = {
    'dev': ('开发与工作', '#67C7A5', '#E9F9F2'),
    'browse': ('浏览与资讯', '#7FA9F8', '#EAF2FF'),
    'ai': ('AI 与沟通', '#9B8AFB', '#F0EDFF'),
    'fun': ('娱乐与游戏', '#F2A97E', '#FFF0E8'),
    'system': ('系统与工具', '#9AA6B8', '#F1F4F8'),
    'other': ('其他 / 待识别', '#B7C0CE', '#F4F6FA'),
}
CATEGORY_ORDER = ['dev', 'browse', 'ai', 'fun', 'system', 'other']
CATEGORY_LABELS = {key: value[0] for key, value in CATEGORIES.items()}
LABEL_TO_CATEGORY = {value[0]: key for key, value in CATEGORIES.items()}
LABEL_TO_CATEGORY.update({
    '开发': 'dev', '工作': 'dev', '学习': 'dev',
    '浏览': 'browse', '浏览器': 'browse',
    'AI': 'ai', 'ai': 'ai', '沟通': 'ai',
    '娱乐': 'fun', '游戏': 'fun',
    '系统': 'system', '工具': 'system',
    '其他': 'other', '未分类': 'other',
})


@dataclass(frozen=True)
class AppEntry:
    id: str
    display: str
    category: str
    aliases: tuple = ()
    hidden: bool = False
    self_process: bool = False
    source: str = 'catalog'

    @property
    def label(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[0]

    @property
    def color(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[1]

    @property
    def background(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[2]


@dataclass
class UsageRecord:
    id: str
    display: str
    category: str
    seconds: float
    variants: int = 1
    hidden: bool = False
    self_process: bool = False

    @property
    def label(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[0]

    @property
    def color(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[1]

    @property
    def background(self):
        return CATEGORIES.get(self.category, CATEGORIES['other'])[2]


ENTRIES = {}
ALIASES = {}


def _add(app_id, display, category, aliases=(), hidden=False):
    entry = AppEntry(app_id, display, category, tuple(aliases), hidden)
    ENTRIES[app_id] = entry
    ALIASES[display.lower()] = entry
    for alias in aliases:
        ALIASES[alias.lower()] = entry
        stem = Path(alias).stem.lower()
        if stem:
            ALIASES.setdefault(stem, entry)
    return entry


# ---------------------------------------------------------------- catalog
_add('chrome', 'Google Chrome', 'browse',
     ('chrome.exe', 'chrome_proxy.exe', 'googlechrome.exe'))
_add('edge', 'Microsoft Edge', 'browse', ('msedge.exe',))
_add('firefox', 'Firefox', 'browse', ('firefox.exe',))
_add('vscode', 'Visual Studio Code', 'dev',
     ('code.exe', 'code - insiders.exe', 'vscodium.exe'))
_add('trae', 'Trae CN', 'dev', ('trae cn.exe', 'trae.exe'))
_add('trae-installer', 'Trae CN 安装程序', 'other',
     ('trae_cn-setup-x64.tmp', 'trae_cn-setup-x64.exe', 'trae cn setup.exe'),
     hidden=True)
_add('terminal', 'Windows Terminal', 'dev', ('windowsterminal.exe', 'wt.exe'))
_add('python', 'Python', 'dev', ('python.exe', 'pythonw.exe'))
_add('java', 'Java 应用', 'dev', ('java.exe', 'javaw.exe'))
_add('intellij', 'IntelliJ IDEA', 'dev', ('idea64.exe', 'idea.exe'))
_add('pycharm', 'PyCharm', 'dev', ('pycharm64.exe', 'pycharm.exe'))
_add('webstorm', 'WebStorm', 'dev', ('webstorm64.exe', 'webstorm.exe'))
_add('clion', 'CLion', 'dev', ('clion64.exe', 'clion.exe'))
_add('goland', 'GoLand', 'dev', ('goland64.exe', 'goland.exe'))
_add('eclipse', 'Eclipse', 'dev', ('eclipse.exe',))
_add('notion', 'Notion', 'dev', ('notion.exe',))
_add('obsidian', 'Obsidian', 'dev', ('obsidian.exe',))
_add('chatgpt', 'ChatGPT', 'ai', ('chatgpt.exe',))
_add('claude', 'Claude', 'ai', ('claude.exe',))
_add('wechat', '微信', 'ai', ('wechat.exe', 'weixin.exe'))
_add('qq', 'QQ', 'ai', ('qq.exe',))
_add('discord', 'Discord', 'ai', ('discord.exe',))
_add('slack', 'Slack', 'ai', ('slack.exe',))
_add('hades2', 'Hades II', 'fun', ('hades2.exe', 'hades ii.exe'))
_add('steam', 'Steam', 'fun',
     ('steam.exe', 'steamwebhelper.exe', 'gameoverlayui.exe'))
_add('minecraft', 'Minecraft', 'fun', ('minecraft.exe',))
_add('vlc', 'VLC', 'fun', ('vlc.exe',))
_add('potplayer', 'PotPlayer', 'fun', ('potplayermini64.exe', 'potplayer.exe'))
_add('explorer', '文件资源管理器', 'system', ('explorer.exe',))
_add('windows-shell', 'Windows 系统组件', 'system',
     ('pickerhost.exe', 'shellexperiencehost.exe',
      'startmenuexperiencehost.exe', 'searchhost.exe'), hidden=True)
_add('windows-app', 'Windows 应用', 'system')
_add('windows-settings', '设置', 'system')
_add('windows-photos', '照片', 'other')
_add('windows-calculator', '计算器', 'system')
_add('windows-store', 'Microsoft Store', 'system')
_add('self', '小汐（本应用）', 'system', hidden=True)

SELF_ENTRY = replace(ENTRIES['self'], self_process=True)
ENTRIES['self'] = SELF_ENTRY

# Transient title patterns. They only choose a canonical id; titles are never
# persisted. Keep these specific to hosts that cannot be told apart by exe.
JAVA_TITLE_RULES = [
    (r'minecraft', 'minecraft'),
    (r'intellij\s*idea', 'intellij'),
    (r'pycharm', 'pycharm'),
    (r'webstorm', 'webstorm'),
    (r'clion', 'clion'),
    (r'goland', 'goland'),
    (r'eclipse', 'eclipse'),
]
UWP_TITLE_RULES = [
    (r'^设置$|^settings$', 'windows-settings'),
    (r'^照片$|^photos$', 'windows-photos'),
    (r'^计算器$|^calculator$', 'windows-calculator'),
    (r'microsoft store|^商店$', 'windows-store'),
]
HOST_TITLE_RULES = [
    (r'\btrae\b', 'trae'),
    (r'chatgpt', 'chatgpt'),
    (r'visual studio code', 'vscode'),
    (r'windows terminal', 'terminal'),
    (r'google chrome', 'chrome'),
    (r'microsoft edge', 'edge'),
    (r'hades\s*(ii|2)', 'hades2'),
]

METADATA_CACHE = {}
GENERIC_PRODUCTS = {
    '', 'microsoft® windows® operating system', 'microsoft windows',
    'windows', 'microsoft® windows® operating system',
    'microsoft windows operating system',
}


def _slug(value):
    value = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return value or 'app'


def _version_strings(path):
    key = os.path.normcase(str(path))
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = METADATA_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    if not IS_WINDOWS:
        return {}
    result = {}
    try:
        version = ctypes.WinDLL('version', use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p,
                                                    ctypes.POINTER(ctypes.c_ulong)]
        version.GetFileVersionInfoSizeW.restype = ctypes.c_ulong
        version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong,
                                                ctypes.c_ulong, ctypes.c_void_p]
        version.GetFileVersionInfoW.restype = ctypes.c_bool
        version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                           ctypes.POINTER(ctypes.c_void_p),
                                           ctypes.POINTER(ctypes.c_uint)]
        version.VerQueryValueW.restype = ctypes.c_bool
        size = version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            METADATA_CACHE[key] = (mtime, result)
            return result
        data = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(path), 0, size, data):
            METADATA_CACHE[key] = (mtime, result)
            return result
        value = ctypes.c_void_p()
        length = ctypes.c_uint()
        translations = []
        if version.VerQueryValueW(data, r'\VarFileInfo\Translation',
                                  ctypes.byref(value), ctypes.byref(length)):
            raw = ctypes.string_at(value.value, length.value)
            for index in range(0, len(raw) - 3, 4):
                lang, code_page = struct_unpack(raw[index:index + 4])
                translations.append(f'{lang:04x}{code_page:04x}')
        if not translations:
            translations = ['040904b0', '080404b0']
        for block in translations:
            for name in ('ProductName', 'FileDescription', 'CompanyName'):
                query = f'\\StringFileInfo\\{block}\\{name}'
                if version.VerQueryValueW(data, query, ctypes.byref(value),
                                          ctypes.byref(length)):
                    text = ctypes.wstring_at(value.value, length.value).strip('\x00').strip()
                    if text:
                        result[name] = text
            if result:
                break
    except Exception:
        result = {}
    METADATA_CACHE[key] = (mtime, result)
    return result


def struct_unpack(raw):
    import struct
    return struct.unpack('<HH', raw)


def metadata(path):
    if not path:
        return {}
    return _version_strings(path)


def clean_name(raw):
    name = Path(str(raw)).name
    if name.lower().endswith('.exe'):
        name = name[:-4]
    if name.lower().endswith('.tmp'):
        name = name[:-4]
    name = name.replace('_', ' ').replace('-', ' ').strip()
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    return name or '未知应用'


def _title_entry(title, rules):
    if not title:
        return None
    for pattern, app_id in rules:
        if re.search(pattern, title, re.I):
            return ENTRIES.get(app_id)
    return None


def _category_for_publisher(publisher):
    publisher = (publisher or '').lower()
    if 'google' in publisher:
        return 'browse'
    if 'valve' in publisher:
        return 'fun'
    if 'jetbrains' in publisher:
        return 'dev'
    if 'microsoft' in publisher:
        return 'system'
    return 'other'


def _entry_from_metadata(path, name):
    meta = metadata(path)
    product = (meta.get('ProductName') or '').strip()
    description = (meta.get('FileDescription') or '').strip()
    company = (meta.get('CompanyName') or '').strip()
    for candidate in (product, description):
        if candidate.lower() in ALIASES:
            return ALIASES[candidate.lower()]
    for candidate in (product, description):
        if candidate and candidate.lower() not in GENERIC_PRODUCTS:
            display = candidate
            slug = _slug(candidate)
            if slug == 'app':
                slug = _slug(Path(name).stem)
            app_id = 'app:' + slug
            category = _category_for_publisher(company)
            entry = AppEntry(app_id, display, category,
                             source='metadata')
            ENTRIES.setdefault(app_id, entry)
            ALIASES.setdefault(display.lower(), entry)
            return entry
    display = clean_name(name)
    app_id = 'raw:' + name.lower()
    entry = AppEntry(app_id, display, 'other', source='raw')
    ENTRIES.setdefault(app_id, entry)
    return entry


def _apply_override(entry, overrides):
    if not overrides:
        return entry
    keys = (entry.id, entry.display, entry.display.lower(),
            Path(entry.display).stem.lower())
    for key in keys:
        if key in overrides:
            value = overrides[key]
            category = LABEL_TO_CATEGORY.get(value, value)
            if category not in CATEGORIES:
                category = 'other'
            if category != entry.category:
                return replace(entry, category=category)
            return entry
    return entry


def resolve_key(raw, overrides=None):
    """Resolve a stored key (new canonical id or old exe/display name)."""
    if raw is None:
        return _apply_override(SELF_ENTRY, overrides)
    key = str(raw).strip()
    if key in ENTRIES:
        return _apply_override(ENTRIES[key], overrides)
    name = Path(key).name
    lower = name.lower()
    if lower in ALIASES:
        return _apply_override(ALIASES[lower], overrides)
    if key.lower() in ALIASES:
        return _apply_override(ALIASES[key.lower()], overrides)
    if lower.endswith('.exe') or lower.endswith('.tmp'):
        lower_stem = Path(lower).stem
        if lower_stem in ALIASES:
            return _apply_override(ALIASES[lower_stem], overrides)
    display = clean_name(name)
    app_id = 'raw:' + lower
    entry = ENTRIES.get(app_id)
    if entry is None:
        entry = AppEntry(app_id, display, 'other', source='raw')
        ENTRIES[app_id] = entry
        ALIASES.setdefault(display.lower(), entry)
    return _apply_override(entry, overrides)


def resolve_info(info, overrides=None, self_pids=(), self_paths=()):
    """Resolve a ProcessInfo to an AppEntry.

    ``info`` is duck-typed: pid, path, name, title. Titles are used only for
    ambiguous hosts and are discarded immediately.
    """
    name = (getattr(info, 'name', '') or '').lower()
    path = getattr(info, 'path', '') or ''
    pid = getattr(info, 'pid', None)
    title = getattr(info, 'title', '') or ''
    if pid and pid in self_pids:
        return SELF_ENTRY
    if path:
        norm = os.path.normcase(os.path.abspath(path))
        if any(norm == os.path.normcase(os.path.abspath(p)) for p in self_paths):
            return SELF_ENTRY
    if name in ALIASES:
        entry = ALIASES[name]
        if name in ('java.exe', 'javaw.exe'):
            titled = _title_entry(title, JAVA_TITLE_RULES)
            if titled is not None:
                entry = titled
        elif name == 'applicationframehost.exe':
            titled = _title_entry(title, UWP_TITLE_RULES)
            entry = titled or ENTRIES['windows-app']
        elif name == 'msedgewebview2.exe':
            titled = _title_entry(title, HOST_TITLE_RULES)
            if titled is not None:
                entry = titled
        return _apply_override(entry, overrides)
    if name in ('java.exe', 'javaw.exe'):
        return _apply_override(_title_entry(title, JAVA_TITLE_RULES) or ENTRIES['java'],
                               overrides)
    if name == 'applicationframehost.exe':
        return _apply_override(_title_entry(title, UWP_TITLE_RULES) or ENTRIES['windows-app'],
                               overrides)
    if name == 'msedgewebview2.exe':
        return _apply_override(_title_entry(title, HOST_TITLE_RULES) or
                               _entry_from_metadata(path, name), overrides)
    return _apply_override(_entry_from_metadata(path, name), overrides)


def record_for(raw, seconds, overrides=None, variants=1):
    entry = resolve_key(raw, overrides)
    return UsageRecord(entry.id, entry.display, entry.category, seconds,
                       variants=variants, hidden=entry.hidden,
                       self_process=entry.self_process)


def visible_records(records):
    return [record for record in records if not record.hidden]


def category_totals(records):
    totals = {}
    for record in records:
        if record.hidden:
            continue
        totals[record.category] = totals.get(record.category, 0) + record.seconds
    return totals
