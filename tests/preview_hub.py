"""Open the real Hub with disposable sample data and safe demonstration actions.

Run from the repository root: python tests/preview_hub.py
No character assets, external packages or Windows integrations are required.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_pet.actions import Action, ActionRegistry
from desktop_pet.hub import Hub
from desktop_pet.storage import Store
from desktop_pet.ui import style


class PreviewApp:
    def __init__(self, root, directory):
        self.root = root
        self.store = Store(directory)
        self.pet_hidden = self.focused = self.live2d_mode = False
        self.plugins = SimpleNamespace(plugins={})
        self.registry = ActionRegistry()
        self.focus_running = self.focus_paused = False
        self.registry.add(Action('productivity.focus', 'productivity', self.focus_label, self.focus))
        self.registry.add(Action('productivity.stop', 'productivity', '结束计时', self.stop,
                                 enabled=lambda: self.focus_running))
        self.registry.add(Action('companion.greeting', 'companion', '和小汐打个招呼',
                                 lambda: self.notice('你好呀，一起把今天过得轻松一点。')))
        self.registry.add(Action('shortcuts.workspace', 'shortcuts', '打开我的工作空间',
                                 lambda: self.notice('这是预览，不会打开任何应用或网址。')))
        self.registry.add(Action('usage.today', 'usage', '查看今天的应用统计', self.show_usage_dashboard))
        self.registry.add(Action('settings.dnd', 'settings',
                                 lambda: '关闭免打扰' if self.store.get('dnd') else '开启免打扰', self.toggle_dnd))
        day = datetime.now().date().isoformat()
        for app, seconds in [('vscode', 3600), ('chrome', 1500), ('chatgpt', 900), ('steam', 300)]:
            self.store.add_usage(day, app, seconds)
        self.store.set('plugin.productivity.reminders', [
            {'title': '起来走走，喝一杯水', 'due': (datetime.now() + timedelta(minutes=15)).isoformat()}])
        self.store.set('plugin.productivity.todos', [
            {'title': '整理今天的灵感笔记'},
            {'title': '这是一条用来检查超长待办文本不会覆盖或超出卡片边界的示例内容'}])
        self.hub = Hub(self)
        self.hub.show()
        self.root.after(1000, self.tick)

    def favorite_ids(self):
        return ['companion.greeting', 'productivity.focus', 'shortcuts.workspace', 'usage.today']

    def edit_favorites(self):
        self.notice('预览显示四个示例常用操作。正式应用中可编辑你的收藏。')

    def focus_label(self):
        return '继续专注' if self.focus_paused else '暂停专注' if self.focus_running else '开始 25 分钟专注'

    def focus(self):
        if not self.focus_running:
            self.focus_running = True
            self.focus_paused = False
        else:
            self.focus_paused = not self.focus_paused
        self.store.set('plugin.productivity.timer', {
            'kind': '专注', 'minutes': 25, 'paused': self.focus_paused,
            'remaining': 1500, 'due': (datetime.now() + timedelta(minutes=25)).isoformat()})

    def stop(self):
        self.focus_running = self.focus_paused = False
        self.store.set('plugin.productivity.timer', None)

    def toggle_dnd(self):
        self.store.set('dnd', not self.store.get('dnd', False))

    def invoke_action(self, action_id):
        self.registry.invoke(action_id)
        self.hub.refresh()

    def toggle_pet_visibility(self):
        self.pet_hidden = not self.pet_hidden
        self.hub.refresh()

    def show_panel(self, category):
        self.hub.show()
        self.notice('这是独立界面预览。正式应用会在这里打开完整功能页面。')

    def show_usage_dashboard(self):
        self.hub.show()
        self.hub.select('usage')

    def notice(self, text):
        messagebox.showinfo('小汐 · 界面预览', text, parent=self.hub)

    def close_hub(self):
        self.close()

    def tick(self):
        if self.root.winfo_exists():
            self.hub.refresh()
            self.root.after(1000, self.tick)

    def close(self):
        self.root.destroy()


def main():
    with tempfile.TemporaryDirectory(prefix='xiaoxi-ui-preview-') as directory:
        root = tk.Tk()
        root.withdraw()
        style(root)
        app = PreviewApp(root, directory)
        try:
            root.mainloop()
        finally:
            app.store.close()


if __name__ == '__main__':
    main()
