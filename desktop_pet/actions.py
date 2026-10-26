"""Shared actions: menus, favorites and buttons resolve the same live state."""
from dataclasses import dataclass
import logging

CATEGORIES = {
    'companion': ('动作与互动', '打招呼、眨眼、舒展与台词'),
    'productivity': ('提醒与专注', '番茄钟、提醒与今日待办'),
    'shortcuts': ('快捷操作', '软件、文件夹、网址与场景'),
    'usage': ('使用统计', '今日排行、分类与历史趋势'),
    'settings': ('宠物与设置', '行为偏好、通知与插件管理'),
}

@dataclass
class Action:
    id: str
    category: str
    label: object
    callback: object
    owner: str = ''
    enabled: object = lambda: True

    @property
    def title(self):
        return self.label() if callable(self.label) else self.label

class ActionRegistry:
    def __init__(self, owner_available=lambda owner: True):
        self.items = {}
        self.owner_available = owner_available
        self.on_invoked = None

    def add(self, action):
        if action.category not in CATEGORIES:
            raise ValueError('未知功能分类：' + action.category)
        if action.id in self.items:
            raise ValueError('操作 ID 重复：' + action.id)
        self.items[action.id] = action
        return action.id

    def available(self, action):
        return (not action.owner or self.owner_available(action.owner)) and action.enabled()

    def invoke(self, action_id):
        action = self.items.get(action_id)
        if not action or not self.available(action):
            raise ValueError('此操作当前不可用，请检查插件状态。')
        result = action.callback()
        self.note_invoked(action_id)
        return result

    def note_invoked(self, action_id):
        """Report success once; ancillary usage failures must not repeat actions."""
        if self.on_invoked is not None:
            try:
                self.on_invoked(action_id)
            except Exception:
                logging.exception("Could not persist adaptive shortcut usage")

    def category(self, category):
        return [a for a in self.items.values() if a.category == category
                and (not a.owner or self.owner_available(a.owner))]

    def remove_prefix(self, prefix):
        for key in list(self.items):
            if key.startswith(prefix):
                del self.items[key]
