"""Compact Fluent-style right-click menu for the desktop companion.

Design references: Windows 11 context menus (grouping, 32 px rhythm, Segoe
Fluent icons), Raycast (status header), and a compact dashboard instead of a
long stack of buttons. The menu stays dependency-free: plain Tk widgets plus
a small Canvas for the stats table, focus ring and usage bars.
"""
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path

from desktop_pet.actions import CATEGORIES

BASE = Path(__file__).resolve().parent.parent
UI_FONT = 'Microsoft YaHei UI'
CARD = '#FCFDFF'
BORDER = '#DFE5F1'
INK = '#273149'
MUTED = '#8B95A7'
CAPTION = '#98A3B5'
ACCENT = '#6175DA'
ICON = '#7D89A3'
HOVER = '#F0F4FF'
SEP = '#EDF1F8'
DANGER = '#C0566A'
DANGER_HOVER = '#FDF1F3'
PAUSE = '#C9963F'
KEY = '#FE00FE'

WIDTH = 230
INSET = 8
RADIUS = 11
SUB_WIDTH = 232

CATEGORY_ICONS = {
    'companion': '\uEB51',      # heart
    'productivity': '\uE916',   # stopwatch
    'shortcuts': '\uE945',      # lightning
    'usage': '\uE9D2',          # chart
    'settings': '\uE713',       # gear
}
SHORT_LABELS = {
    'companion': '动作',
    'productivity': '专注',
    'shortcuts': '快捷',
    'usage': '统计',
    'settings': '设置',
}


def icon_family(root):
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    if 'Segoe Fluent Icons' in families:
        return 'Segoe Fluent Icons'
    if 'Segoe MDL2 Assets' in families:
        return 'Segoe MDL2 Assets'
    return 'Segoe UI Symbol'


def rounded_rect(canvas, x1, y1, x2, y2, radius, fill, tags=()):
    d = radius * 2
    canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90, fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=fill, tags=tags)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline=fill, tags=tags)


def clock_text(seconds):
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return f'{seconds // 3600}:{(seconds % 3600) // 60:02d}'
    return f'{seconds // 60}:{seconds % 60:02d}'


def usage_text(seconds):
    minutes = max(0, int(seconds)) // 60
    if minutes >= 60:
        return f'{minutes // 60}h{minutes % 60:02d}m'
    return f'{minutes}m'


def timer_state(app):
    try:
        timer = app.store.get('plugin.productivity.timer')
    except Exception:
        timer = None
    if not timer:
        return '专注', '未开始', 0.0, False
    kind = timer.get('kind', '专注')
    if timer.get('paused'):
        remaining = timer.get('remaining', 0)
    else:
        try:
            remaining = max(0, (datetime.fromisoformat(timer['due']) - datetime.now()).total_seconds())
        except (KeyError, ValueError):
            remaining = 0
    total = max(1, (timer.get('minutes') or 25) * 60)
    return kind, clock_text(remaining), min(1.0, remaining / total), bool(timer.get('paused'))


def today_seconds(app):
    try:
        return app.store.usage_total(datetime.now().date().isoformat())
    except Exception:
        return 0


def open_todos(app):
    try:
        return sum(1 for item in app.store.get('plugin.productivity.todos', []) if not item.get('done'))
    except Exception:
        return 0


class Card(tk.Toplevel):
    def __init__(self, app, width, inset=INSET, radius=RADIUS):
        super().__init__(app.root)
        self.app = app
        self.card_width = width
        self.inset = inset
        self.radius = radius
        self.icon_font = icon_family(app.root)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=KEY)
        try:
            self.attributes('-transparentcolor', KEY)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=CARD)

    def finish(self, x, y, focus=True):
        self.body.update_idletasks()
        width = self.card_width
        height = max(56, self.body.winfo_reqheight() + 2 * self.inset)
        self.canvas.configure(width=width, height=height)
        rounded_rect(self.canvas, 0, 0, width, height, self.radius + 1, BORDER)
        rounded_rect(self.canvas, 1, 1, width - 1, height - 1, self.radius, CARD)
        self.canvas.create_window(self.inset, self.inset, window=self.body, anchor='nw',
                                  width=width - 2 * self.inset, height=height - 2 * self.inset)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(8, min(int(x), screen_w - width - 8))
        y = int(y)
        if y + height > screen_h - 8:
            y = max(8, y - height)
        else:
            y = max(8, y)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self._set_alpha(0.0)
        self.after(8, lambda: self._set_alpha(0.98))
        self.after(24, lambda: self._set_alpha(1.0))
        if focus:
            self.focus_force()
        return height

    def _set_alpha(self, value):
        try:
            if self.winfo_exists():
                self.attributes('-alpha', value)
        except tk.TclError:
            pass


class Row(tk.Frame):
    def __init__(self, parent, menu, icon, label, hint='', chevron=False,
                 command=None, category=None, enabled=True, danger=False,
                 height=28, font_size=9, in_submenu=False):
        super().__init__(parent, bg=CARD, height=height)
        self.pack_propagate(False)
        self.menu = menu
        self.category = category
        self.command = command
        self.enabled = enabled
        self.danger = danger
        self.in_submenu = in_submenu
        self._base_icon = DANGER if danger else ICON
        self._base_text = DANGER if danger else INK
        self._hover_bg = DANGER_HOVER if danger else HOVER
        self._parts = [self]
        self.icon = None
        if icon:
            self.icon = tk.Label(self, text=icon, font=(menu.icon_font, 11),
                                 bg=CARD, fg=self._base_icon, width=2, anchor='center')
            self.icon.pack(side='left', padx=(6, 2))
            self._parts.append(self.icon)
        else:
            spacer = tk.Frame(self, bg=CARD, width=24, height=1)
            spacer.pack(side='left')
            self._parts.append(spacer)
        self.text = tk.Label(self, text=label, font=(UI_FONT, font_size), bg=CARD,
                             fg=self._base_text, anchor='w')
        self.hint = None
        if hint:
            self.hint = tk.Label(self, text=hint, font=(UI_FONT, 7), bg=CARD, fg=MUTED)
            self.hint.pack(side='right', padx=(2, 6))
            self._parts.append(self.hint)
        self.chevron = None
        if chevron:
            self.chevron = tk.Label(self, text='\uE76C', font=(menu.icon_font, 8),
                                    bg=CARD, fg='#A9B3C4')
            self.chevron.pack(side='right', padx=(0, 6))
            self._parts.append(self.chevron)
        self.text.pack(side='left', fill='x', expand=True)
        cursor = 'hand2' if enabled else 'arrow'
        for widget in self._parts + [self.text]:
            widget.configure(cursor=cursor)
            if enabled:
                widget.bind('<Enter>', self._enter)
                widget.bind('<Leave>', self._leave)
                widget.bind('<Button-1>', self._click)
        if not enabled:
            self.text.configure(fg='#B7BFCD')
            if self.icon:
                self.icon.configure(fg='#C2C9D6')

    def _enter(self, event=None):
        self.set_hover(True)
        if self.category:
            self.menu.schedule_submenu(self)
        elif not self.in_submenu:
            self.menu.close_submenu()

    def _leave(self, event=None):
        self.set_hover(False)

    def _click(self, event=None):
        if not self.enabled:
            return
        if self.category:
            self.menu.open_submenu(self)
        elif self.command:
            self.menu.close()
            self.command()
        return 'break'

    def set_hover(self, on):
        if not self.enabled:
            return
        bg = self._hover_bg if on else CARD
        fg = (DANGER if self.danger else ACCENT) if on else self._base_text
        icon_fg = (DANGER if self.danger else ACCENT) if on else self._base_icon
        for widget in self._parts + [self.text]:
            widget.configure(bg=bg)
        self.text.configure(fg=fg)
        if self.icon:
            self.icon.configure(fg=icon_fg)
        if self.chevron:
            self.chevron.configure(fg=ACCENT if on else '#A9B3C4')


class Tile(tk.Canvas):
    """Compact icon tile used for the six launcher entries."""

    def __init__(self, parent, menu, icon, label, category=None, command=None,
                 width=64, height=50, icon_size=16, label_size=8):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.menu = menu
        self.category = category
        self.command = command
        rounded_rect(self, 1, 1, width - 1, height - 1, 8, CARD, tags=('bg',))
        self.icon_item = self.create_text(width / 2, height / 2 - 4, text=icon,
                                          font=(menu.icon_font, icon_size), fill=ICON)
        self.text_item = self.create_text(width / 2, height - 10, text=label,
                                          font=(UI_FONT, label_size), fill=MUTED)
        self.configure(cursor='hand2')
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)

    def _enter(self, event=None):
        self.set_hover(True)
        if self.category:
            self.menu.schedule_submenu(self)

    def _leave(self, event=None):
        self.set_hover(False)

    def _click(self, event=None):
        if self.category:
            self.menu.open_submenu(self)
        elif self.command:
            self.menu.close()
            self.command()
        return 'break'

    def set_hover(self, on):
        self.itemconfigure('bg', fill=HOVER if on else CARD)
        self.itemconfigure(self.icon_item, fill=ACCENT if on else ICON)
        self.itemconfigure(self.text_item, fill=ACCENT if on else MUTED)


class UsageTable(tk.Canvas):
    """Top-three canonical applications with soft category bars."""

    def __init__(self, parent, app, width=216):
        try:
            rows = app.store.usage_records(datetime.now().date().isoformat())[:3]
        except Exception:
            rows = []
        height = 8 + 20 * len(rows) if rows else 30
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.draw(rows, width, height)

    def draw(self, rows, width, height):
        if not rows:
            self.create_text(width // 2, height // 2, text='今天还没有应用记录',
                             font=(UI_FONT, 7), fill=MUTED)
            return
        maximum = max((record.seconds for record in rows), default=1) or 1
        for index, record in enumerate(rows):
            y = 4 + index * 20
            color = record.color
            self.create_oval(8, y + 3, 16, y + 11, fill=color, outline='')
            label = record.display if len(record.display) <= 16 else record.display[:15] + '…'
            self.create_text(20, y, text=label, anchor='nw',
                             font=(UI_FONT, 7), fill=INK)
            self.create_text(width - 8, y, text=usage_text(record.seconds),
                             anchor='ne', font=(UI_FONT, 7), fill=MUTED)
            self.create_line(8, y + 15, width - 8, y + 15,
                             fill='#EDF1F8', width=3, capstyle='round')
            bar = (width - 16) * record.seconds / maximum
            self.create_line(8, y + 15, 8 + max(3, bar), y + 15,
                             fill=color, width=3, capstyle='round')


class Submenu(Card):
    def __init__(self, menu, category):
        super().__init__(menu.app, SUB_WIDTH, inset=8, radius=10)
        self.menu = menu
        self.category = category
        self._build()

    def _build(self):
        head = tk.Frame(self.body, bg=CARD)
        head.pack(fill='x', pady=(2, 2))
        tk.Label(head, text=CATEGORY_ICONS.get(self.category, '\uE734'),
                 font=(self.icon_font, 12), bg=CARD, fg=ACCENT).pack(
            side='left', padx=(10, 5))
        tk.Label(head, text=CATEGORIES[self.category][0], font=(UI_FONT, 9, 'bold'),
                 bg=CARD, fg=INK).pack(side='left')

        if self.category == 'usage':
            UsageTable(self.body, self.menu.app, width=200).pack(fill='x', padx=8, pady=(0, 2))
        elif self.category == 'productivity':
            self._reminder_line()

        actions = self.menu.app.registry.category(self.category)[:6]
        if not actions:
            tk.Label(self.body, text='此分类没有可用操作', font=(UI_FONT, 9),
                     fg=MUTED, bg=CARD, anchor='w').pack(fill='x', padx=12, pady=4)
        for action in actions:
            Row(self.body, self.menu, None, action.title,
                command=lambda key=action.id: self.menu.app.invoke_action(key),
                enabled=self.menu.app.registry.available(action),
                height=28, font_size=9, in_submenu=True).pack(fill='x', padx=4)
        tk.Frame(self.body, bg=SEP, height=1).pack(fill='x', padx=10, pady=4)
        Row(self.body, self.menu, '\uE8A5', '打开完整页面…',
            command=lambda: self.menu.open_panel(self.category),
            height=28, font_size=9, in_submenu=True).pack(fill='x', padx=4, pady=(0, 2))

    def _reminder_line(self):
        try:
            reminders = [item for item in self.menu.app.store.get('plugin.productivity.reminders', [])
                         if not item.get('done')]
        except Exception:
            reminders = []
        if not reminders:
            return
        try:
            upcoming = min(reminders, key=lambda item: item['due'])
            due = datetime.fromisoformat(upcoming['due']).strftime('%H:%M')
        except (KeyError, ValueError):
            return
        title = upcoming.get('title', '')
        if len(title) > 12:
            title = title[:11] + '…'
        tk.Label(self.body, text=f'下次提醒 {due} · {title}', font=(UI_FONT, 7),
                 fg=MUTED, bg=CARD, anchor='w').pack(fill='x', padx=10, pady=(0, 2))

    def finish(self, x, y, focus=False):
        return super().finish(x, y, focus=False)


class ContextMenu(Card):
    def __init__(self, app, x, y):
        super().__init__(app, WIDTH)
        self.flyout = None
        self.submenu_job = None
        self.active_anchor = None
        self.category_rows = {}
        self.avatar_image = None
        try:
            image = tk.PhotoImage(file=str(BASE / 'assets/ui/menu-avatar-72.png'))
            self.avatar_image = image.subsample(2, 2) if image.width() > 48 else image
        except tk.TclError:
            self.avatar_image = None
        self._build()
        self.finish(x + 6, y + 6)
        self.bind('<Escape>', lambda event: self.close())
        self.bind('<Button-3>', lambda event: self.close())
        self.bind('<FocusOut>', lambda event: self.after(120, self._check_focus))

    def _build(self):
        header = tk.Frame(self.body, bg=CARD)
        header.pack(fill='x')
        avatar = tk.Canvas(header, width=36, height=36, bg=CARD, highlightthickness=0)
        avatar.pack(side='left', padx=(8, 6), pady=2)
        if self.avatar_image is not None:
            avatar.create_image(18, 18, image=self.avatar_image)
        else:
            avatar.create_oval(2, 2, 34, 34, fill='#EEF2FF', outline='#DCE4FA')
            avatar.create_text(18, 18, text='汐', fill=ACCENT, font=(UI_FONT, 9, 'bold'))
        avatar.create_oval(1, 1, 35, 35, outline='#E1E7F5')
        info = tk.Frame(header, bg=CARD)
        info.pack(side='left', fill='y', pady=3)
        tk.Label(info, text='小汐', font=(UI_FONT, 10, 'bold'), fg=INK,
                 bg=CARD, anchor='w').pack(anchor='w')
        tk.Label(info, text=self._status_line(), font=(UI_FONT, 7), fg=MUTED,
                 bg=CARD, anchor='w').pack(anchor='w')

        line = tk.Frame(self.body, bg=CARD, height=20)
        line.pack(fill='x', padx=10)
        line.pack_propagate(False)
        kind, value, _, paused = timer_state(self.app)
        left = f'{kind} {value}' + (' ·暂停' if paused else '')
        tk.Label(line, text=left, font=(UI_FONT, 8, 'bold'), fg=ACCENT,
                 bg=CARD).pack(side='left')
        right = f'今日 {usage_text(today_seconds(self.app))} · 待办 {open_todos(self.app)}'
        tk.Label(line, text=right, font=(UI_FONT, 7), fg=MUTED,
                 bg=CARD).pack(side='right')

        grid = tk.Frame(self.body, bg=CARD, height=108)
        grid.pack(fill='x', padx=2, pady=(2, 0))
        grid.pack_propagate(False)
        entries = [(CATEGORY_ICONS.get(key, '\uE734'),
                    SHORT_LABELS.get(key, '功能'), key) for key in CATEGORIES]
        entries.append(('\uE80F', '小屋', None))
        cell_w, cell_h, gap_x, gap_y = 64, 50, 5, 4
        inner = self.card_width - 2 * self.inset
        start_x = (inner - (3 * cell_w + 2 * gap_x)) / 2
        for index, (icon, label, category) in enumerate(entries):
            column, row_index = index % 3, index // 3
            tile = Tile(grid, self, icon, label, category,
                        command=self.app.show_hub if category is None else None,
                        width=cell_w, height=cell_h)
            tile.place(x=start_x + column * (cell_w + gap_x),
                       y=row_index * (cell_h + gap_y),
                       width=cell_w, height=cell_h)
            if category:
                self.category_rows[category] = tile

        tk.Frame(self.body, bg=SEP, height=1).pack(fill='x', padx=8, pady=3)
        bottom = tk.Frame(self.body, bg=CARD, height=24)
        bottom.pack(fill='x')
        bottom.pack_propagate(False)
        self._mini(bottom, '\uE7B3', '显示' if self.app.pet_hidden else '隐藏',
                   self.app.toggle_pet_visibility, side='left')
        self._mini(bottom, '\uE7E8', '退出', self.app.close, side='right', danger=True)

    def _status_line(self):
        try:
            if self.app.store.get('dnd', False):
                return '免打扰'
            if getattr(self.app, 'focused', False):
                return '专注模式'
        except Exception:
            pass
        return '在这里陪你'

    def _mini(self, parent, icon, label, callback, side='left', danger=False):
        cell = tk.Frame(parent, bg=CARD)
        cell.pack(side=side, padx=8)
        base = DANGER if danger else INK
        hover = DANGER_HOVER if danger else HOVER
        icon_label = tk.Label(cell, text=icon, font=(self.icon_font, 9), bg=CARD,
                              fg=DANGER if danger else ICON)
        icon_label.pack(side='left', padx=(0, 2))
        text_label = tk.Label(cell, text=label, font=(UI_FONT, 7), bg=CARD, fg=base)
        text_label.pack(side='left')
        widgets = [cell, icon_label, text_label]
        for widget in widgets:
            widget.configure(cursor='hand2')

        def enter(event=None):
            self.close_submenu()
            for item in widgets:
                item.configure(bg=hover)
            text_label.configure(fg=DANGER if danger else ACCENT)
            icon_label.configure(fg=DANGER if danger else ACCENT)

        def leave(event=None):
            for item in widgets:
                item.configure(bg=CARD)
            text_label.configure(fg=base)
            icon_label.configure(fg=DANGER if danger else ICON)

        def click(event=None):
            self.close()
            callback()
            return 'break'

        for widget in widgets:
            widget.bind('<Enter>', enter)
            widget.bind('<Leave>', leave)
            widget.bind('<Button-1>', click)

    def schedule_submenu(self, anchor):
        self._cancel_submenu_job()
        if self.flyout is not None and self.active_anchor is anchor:
            return
        if self.flyout is not None:
            self.close_submenu()
        self.submenu_job = self.after(80, lambda: self.open_submenu(anchor))

    def open_submenu(self, anchor):
        self._cancel_submenu_job()
        if self.flyout is not None and self.active_anchor is anchor:
            return
        self.close_submenu()
        self.active_anchor = anchor
        submenu = Submenu(self, anchor.category)
        self.flyout = submenu
        x = self.winfo_rootx() + self.winfo_width() - 6
        y = anchor.winfo_rooty() - (2 if isinstance(anchor, Tile) else 6)
        if x + submenu.card_width > self.winfo_screenwidth() - 8:
            x = self.winfo_rootx() - submenu.card_width + 6
        submenu.finish(x, y, focus=False)

    def close_submenu(self):
        self._cancel_submenu_job()
        flyout, self.flyout = self.flyout, None
        self.active_anchor = None
        if flyout is not None:
            try:
                flyout.destroy()
            except tk.TclError:
                pass

    def _cancel_submenu_job(self):
        if self.submenu_job is not None:
            try:
                self.after_cancel(self.submenu_job)
            except tk.TclError:
                pass
            self.submenu_job = None

    def open_panel(self, category):
        self.close()
        self.app.show_panel(category)

    def _check_focus(self):
        if not self.winfo_exists():
            return
        try:
            focus = self.focus_get()
        except Exception:
            focus = None
        widget = focus
        while widget is not None:
            if widget is self or (self.flyout is not None and widget is self.flyout):
                return
            widget = getattr(widget, 'master', None)
        self.close()

    def close(self):
        if getattr(self.app, 'context_popup', None) is self:
            self.app.context_popup = None
        self.destroy()

    def destroy(self):
        self._cancel_submenu_job()
        flyout, self.flyout = self.flyout, None
        if flyout is not None:
            try:
                flyout.destroy()
            except tk.TclError:
                pass
        super().destroy()
