"""Five categories, a compact home, and alternate entrances to shared actions."""
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from desktop_pet.actions import Action, CATEGORIES
from desktop_pet.ui import safe, duration
from desktop_pet.menu import ContextMenu

class Navigation:
    def init_navigation(self):
        self.hub = None
        self.qt_hub_host = None
        self.qt_hub_failed = False
        self.qt_hub_editing = False
        self.usage_dashboard = None
        self.click_job = None
        self.pet_hidden = False
        self.registry.add(Action('settings.dnd', 'settings',
            lambda: '关闭免打扰' if self.store.get('dnd', False) else '开启免打扰', self.toggle_dnd))
        self.registry.add(Action('settings.history', 'settings', '通知记录', self.show_history))

    def invoke_action(self, action_id):
        self.close_context_popup()
        safe(self.root, lambda: self.registry.invoke(action_id))
        self.refresh_navigation()

    def close_context_popup(self, event=None):
        popup = getattr(self, 'context_popup', None)
        self.context_popup = None
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        return 'break'

    def toggle_context_popup(self, x, y):
        popup = getattr(self, 'context_popup', None)
        if popup is not None and popup.winfo_exists():
            self.close_context_popup()
            return
        self.context_popup = ContextMenu(self, x, y)

    def favorite_ids(self):
        return self.store.get('navigation.favorites',
            ['companion.greeting', 'productivity.focus', 'shortcuts.mute', 'usage.today'])[:4]

    def pet_click(self):
        if getattr(self, 'context_popup', None) is not None:
            self.close_context_popup()
            return
        if self.click_job:
            self.root.after_cancel(self.click_job)
            self.click_job = None
            self.invoke_action(self.store.get('navigation.double_click', 'companion.greeting'))
        else:
            self.click_job = self.root.after(320, self.single_pet_click)

    def single_pet_click(self):
        self.click_job = None
        self.show_hub()

    def cancel_pet_click(self):
        if self.click_job:
            self.root.after_cancel(self.click_job)
            self.click_job = None

    def status_summary(self):
        timer = self.store.get('plugin.productivity.timer')
        if timer:
            if timer.get('paused'):
                return timer['kind'] + '已暂停 · ' + duration(timer['remaining'])
            return timer['kind'] + '还剩 ' + duration(max(0, (datetime.fromisoformat(timer['due'])-datetime.now()).total_seconds()))
        return '今日应用使用 ' + duration(self.store.usage_total(datetime.now().date().isoformat()))

    def show_hub(self):
        self.leave()
        # A separate Qt process is optional. Never remove the working Tk path.
        if not getattr(self, 'smoke', True) and not getattr(self, 'qt_hub_failed', False):
            from desktop_pet.qt_hub_host import QtHubHost
            host = getattr(self, 'qt_hub_host', None)
            if host is None:
                host = QtHubHost(self, self.qt_hub_failure)
                if host.start():
                    self.qt_hub_host = host
                else:
                    self.qt_hub_failed = True
                    host = None
            if host is not None and not host.closed:
                if self.hub is not None and self.hub.winfo_exists():
                    self.hub.hide()
                host.show()
                return
        self.show_legacy_hub()

    def qt_hub_failure(self, reason, was_visible):
        self.qt_hub_failed = True
        self.qt_hub_host = None
        self.qt_hub_editing = False
        if was_visible:
            self.show_legacy_hub()
            self.notify('小屋兼容模式', '新版界面暂时不可用，已恢复原小屋；计时、提醒和数据仍然保留。', character_event=False)

    def show_legacy_hub(self):
        self.leave()
        from desktop_pet.hub import Hub
        if self.hub is None or not self.hub.winfo_exists():
            self.hub = Hub(self)
        self.hub.show()

    def refresh_navigation(self):
        host = getattr(self, 'qt_hub_host', None)
        if host is not None and not host.closed:
            host.refresh()
        if self.hub is not None and self.hub.winfo_exists():
            self.hub.refresh()

    def show_usage_dashboard(self):
        self.leave()
        host = getattr(self, 'qt_hub_host', None)
        if host is not None and not host.closed:
            host.show('usage')
            return
        if self.hub is not None and self.hub.winfo_exists():
            self.hub.hide()
        from desktop_pet.usage_dashboard import UsageDashboard
        if self.usage_dashboard is None or not self.usage_dashboard.winfo_exists():
            self.usage_dashboard = UsageDashboard(self)
        self.usage_dashboard.show()

    def edit_favorites(self):
        win = tk.Toplevel(self.root); win.title('编辑常用操作'); win.geometry('480x420')
        ttk.Label(win,text='选择最多四项；前三项也显示在右键菜单顶部。',padding=12).pack()
        box = tk.Listbox(win, selectmode='multiple', exportselection=False, font=('Microsoft YaHei UI',11))
        box.pack(fill='both', expand=True, padx=12)
        actions = [a for category in CATEGORIES for a in self.registry.category(category)]
        for i, action in enumerate(actions):
            box.insert('end', CATEGORIES[action.category][0]+' · '+action.title)
            if action.id in self.favorite_ids(): box.selection_set(i)
        def save():
            ids = [actions[i].id for i in box.curselection()]
            if len(ids)>4:
                messagebox.showinfo('常用操作','最多选择四项。',parent=win); return
            self.store.set('navigation.favorites', ids); self.refresh_navigation(); win.destroy()
        ttk.Button(win,text='保存',command=save).pack(pady=12)

    def set_pet_hidden(self, hidden, show_hub=False):
        self.pet_hidden = bool(hidden)
        self.leave()
        if self.live2d:
            self.live2d.state(visible=not self.pet_hidden)
        elif not self.live2d_mode:
            if self.pet_hidden:
                self.pet.withdraw()
            else:
                self.pet.deiconify()
        if show_hub:
            # Keep a visible recovery entrance even when the global hotkey is occupied.
            self.show_hub()

    def toggle_pet_visibility(self):
        self.set_pet_hidden(not self.pet_hidden, show_hub=True)

    def close_hub(self):
        host = getattr(self, 'qt_hub_host', None)
        if host is not None and not host.closed:
            host.hide()
        if self.pet_hidden and not (self.hotkey and self.hotkey.registered):
            self.set_pet_hidden(False)
        if self.hub is not None and self.hub.winfo_exists():
            self.hub.hide()

    def create_category_menu(self):
        menu = tk.Menu(self.root, tearoff=False, font=('Microsoft YaHei UI',10))
        for key in self.favorite_ids()[:3]:
            action = self.registry.items.get(key)
            if action:
                menu.add_command(label='★ '+action.title, state='normal' if self.registry.available(action) else 'disabled',
                                 command=lambda k=key:self.invoke_action(k))
        menu.add_separator()
        for category, (title, _) in CATEGORIES.items():
            child = tk.Menu(menu, tearoff=False)
            for action in self.registry.category(category)[:6]:
                child.add_command(label=action.title, state='normal' if self.registry.available(action) else 'disabled',
                                  command=lambda key=action.id:self.invoke_action(key))
            child.add_separator()
            child.add_command(label='管理'+title+'…', command=lambda k=category:self.show_panel(k))
            menu.add_cascade(label=title, menu=child)
        menu.add_separator()
        menu.add_command(label='功能小屋', command=self.show_hub)
        menu.add_command(label='显示宠物' if self.pet_hidden else '隐藏宠物', command=self.toggle_pet_visibility)
        menu.add_command(label='退出桌宠', command=self.close)
        return menu
