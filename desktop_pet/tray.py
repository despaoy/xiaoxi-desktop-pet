"""Native Windows tray icon, independent from the Live2D renderer."""
import queue

import pystray
from PIL import Image

from desktop_pet import platform_win


class Tray:
    def __init__(self, app):
        self.app = app
        self.actions = queue.Queue()
        image = Image.open(app.resource('assets/ui/app-icon.png')).convert('RGBA')
        self.icon = pystray.Icon(
            'XiaoXi', image, '小汐桌宠',
            pystray.Menu(
                pystray.MenuItem(
                    lambda item: '显示角色' if app.pet_hidden else '隐藏角色（后台运行）',
                    lambda icon, item: self.actions.put('toggle')),
                pystray.MenuItem(
                    '打开功能小屋',
                    lambda icon, item: self.actions.put('hub'), default=True),
                pystray.MenuItem(
                    '开机自启',
                    lambda icon, item: self.actions.put('startup'),
                    checked=lambda item: platform_win.startup_enabled()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    '退出小汐',
                    lambda icon, item: self.actions.put('exit')),
            ),
        )
        self.icon.run_detached()

    def poll(self):
        if not self.app.root.winfo_exists():
            return
        try:
            while True:
                self.app.handle_tray(self.actions.get_nowait())
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.icon.title = ('小汐桌宠 · 后台运行' if self.app.pet_hidden
                               else '小汐桌宠')
            self.icon.update_menu()
        except Exception:
            pass
        try:
            self.app.root.after(250, self.poll)
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass

    def notify(self, message, title='小汐桌宠'):
        try:
            self.icon.notify(message, title)
        except Exception:
            pass
