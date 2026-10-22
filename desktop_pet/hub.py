"""Sidebar-style functional hub selected from the design previews.

The window is intentionally frameless and rounded to match the right-click
menu. The left rail switches between the "today" dashboard and the five
functional categories; the right pane holds the content.
"""
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from desktop_pet.actions import CATEGORIES
from desktop_pet import apps
from desktop_pet.ui import duration
from desktop_pet.menu import (
    ACCENT, CAPTION, CARD, DANGER, HOVER, ICON, INK, MUTED, SEP, UI_FONT,
    Card, UsageTable, icon_family, open_todos, rounded_rect, timer_state,
    today_seconds, usage_text,
)

WEEK = '一二三四五六日'
SOFT = '#F6F8FE'


def bordered_round(canvas, x1, y1, x2, y2, radius, fill, border=SEP):
    rounded_rect(canvas, x1, y1, x2, y2, radius, border)
    rounded_rect(canvas, x1 + 1, y1 + 1, x2 - 1, y2 - 1,
                 max(1, radius - 1), fill)


def category_icon(key):
    return {
        'companion': '\uEB51', 'productivity': '\uE916', 'shortcuts': '\uE945',
        'usage': '\uE9D2', 'settings': '\uE713',
    }.get(key, '\uE734')


class StatCard(tk.Canvas):
    def __init__(self, parent, width=116, height=66):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())

    def update(self, label, value, icon_code, ring=None):
        self.delete('all')
        rounded_rect(self, 0, 0, self.card_w, self.card_h, 10, SOFT)
        if ring is not None:
            self.create_oval(10, 17, 42, 49, outline='#E4EAF6', width=3)
            if ring > 0:
                self.create_arc(10, 17, 42, 49, start=90, extent=-359.9 * ring,
                                style='arc', outline=ACCENT, width=3)
            self.create_text(50, 16, text=label, anchor='w',
                             font=(UI_FONT, 7), fill=CAPTION)
            self.create_text(50, 32, text=value, anchor='w',
                             font=(UI_FONT, 11, 'bold'), fill=INK)
            return
        self.create_text(12, 17, text=label, anchor='w',
                         font=(UI_FONT, 7), fill=CAPTION)
        self.create_text(12, 33, text=value, anchor='w',
                         font=(UI_FONT, 11, 'bold'), fill=INK)
        self.create_text(self.card_w - 16, self.card_h / 2, text=icon_code,
                         font=(self.icon_font, 12), fill=ICON)


class NavItem(tk.Canvas):
    def __init__(self, parent, icon_code, label, command, width=132, height=36):
        super().__init__(parent, width=width, height=height, bg=SOFT,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())
        self.icon_code = icon_code
        self.label = label
        self.command = command
        self.selected = False
        self.hover = False
        self.configure(cursor='hand2')
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', lambda event: self.command())
        self.draw()

    def draw(self):
        self.delete('all')
        fill = '#E8EEFF' if self.selected else ('#FBFCFE' if self.hover else SOFT)
        rounded_rect(self, 0, 0, self.card_w, self.card_h, 8, fill)
        color = ACCENT if self.selected else (INK if self.hover else MUTED)
        self.create_text(14, self.card_h / 2, text=self.icon_code,
                         font=(self.icon_font, 12), fill=color, anchor='w')
        self.create_text(34, self.card_h / 2, text=self.label,
                         font=(UI_FONT, 9), fill=color, anchor='w')

    def set_selected(self, selected):
        self.selected = selected
        self.draw()

    def _enter(self, event=None):
        self.hover = True
        self.draw()

    def _leave(self, event=None):
        self.hover = False
        self.draw()


class Chip(tk.Canvas):
    def __init__(self, parent, icon_code, label, command, width=178, height=34,
                 enabled=True):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())
        self.icon_code = icon_code
        self.label = label
        self.command = command
        self.enabled = enabled
        self.hover = False
        if enabled:
            self.configure(cursor='hand2')
            self.bind('<Enter>', self._enter)
            self.bind('<Leave>', self._leave)
            self.bind('<Button-1>', self._click)
        self.draw()

    def draw(self):
        self.delete('all')
        bordered_round(self, 0, 0, self.card_w, self.card_h, 8,
                       HOVER if self.hover else '#F8FAFE')
        fg = INK if self.enabled else '#B7BFCD'
        self.create_text(12, self.card_h / 2, text=self.icon_code,
                         font=(self.icon_font, 10),
                         fill=ACCENT if self.enabled and self.hover else (ICON if self.enabled else '#C2C9D6'),
                         anchor='w')
        self.create_text(28, self.card_h / 2, text=self.label,
                         font=(UI_FONT, 9), fill=ACCENT if self.hover and self.enabled else fg,
                         anchor='w')

    def _enter(self, event=None):
        self.hover = True
        self.draw()

    def _leave(self, event=None):
        self.hover = False
        self.draw()

    def _click(self, event=None):
        if self.enabled:
            self.command()
        return 'break'


class ReminderCard(tk.Canvas):
    def __init__(self, parent, width=364, height=36):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())

    def update(self, text, right=''):
        self.delete('all')
        bordered_round(self, 0, 0, self.card_w, self.card_h, 8, '#F8FAFE')
        self.create_text(14, self.card_h / 2, text='\uE823',
                         font=(self.icon_font, 10), fill=ACCENT, anchor='w')
        self.create_text(30, self.card_h / 2, text=text,
                         font=(UI_FONT, 8), fill=INK, anchor='w')
        if right:
            self.create_text(self.card_w - 12, self.card_h / 2, text=right,
                             font=(UI_FONT, 7), fill=MUTED, anchor='e')


class SummaryCard(tk.Canvas):
    def __init__(self, parent, width=364, height=46):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())

    def update(self, text):
        self.delete('all')
        bordered_round(self, 0, 0, self.card_w, self.card_h, 9, '#F8FAFE')
        self.create_text(14, 15, text='\uE734', font=(self.icon_font, 10),
                         fill=ACCENT, anchor='w')
        self.create_text(30, 12, text='今日小结', font=(UI_FONT, 8, 'bold'),
                         fill=INK, anchor='w')
        self.create_text(30, 28, text=text, font=(UI_FONT, 7), fill=MUTED, anchor='w')


class ActionRow(tk.Frame):
    def __init__(self, parent, icon_code, label, command, width=364, height=34):
        super().__init__(parent, bg=CARD, width=width, height=height)
        self.pack_propagate(False)
        self.card_w, self.card_h = width, height
        self.command = command
        self.icon_font = icon_family(self.winfo_toplevel())
        self.icon = tk.Label(self, text=icon_code, font=(self.icon_font, 11),
                             bg=CARD, fg=ICON, width=2)
        self.icon.pack(side='left', padx=(8, 4))
        self.text = tk.Label(self, text=label, font=(UI_FONT, 9), bg=CARD,
                             fg=INK, anchor='w')
        self.text.pack(side='left', fill='x', expand=True)
        self.chevron = tk.Label(self, text='\uE76C', font=(self.icon_font, 8),
                                bg=CARD, fg='#A9B3C4')
        self.chevron.pack(side='right', padx=(0, 8))
        for widget in (self, self.icon, self.text, self.chevron):
            widget.configure(cursor='hand2')
            widget.bind('<Enter>', self._enter)
            widget.bind('<Leave>', self._leave)
            widget.bind('<Button-1>', self._click)

    def _enter(self, event=None):
        for widget in (self, self.icon, self.text, self.chevron):
            widget.configure(bg=HOVER)
        self.icon.configure(fg=ACCENT)
        self.chevron.configure(fg=ACCENT)

    def _leave(self, event=None):
        for widget in (self, self.icon, self.text, self.chevron):
            widget.configure(bg=CARD)
        self.icon.configure(fg=ICON)
        self.chevron.configure(fg='#A9B3C4')

    def _click(self, event=None):
        self.command()
        return 'break'


class UsageMini(tk.Canvas):
    """U2 compact card for the hub's Today section."""
    def __init__(self, parent, width=364, height=112, command=None):
        super().__init__(parent, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.card_w, self.card_h = width, height
        self.command = command
        self.bind('<Button-1>', lambda event: self.command() if self.command else None)

    def update(self, records, total):
        self.delete('all')
        if not records or total <= 0:
            self.create_text(0, 34, text='今天还没有应用记录', anchor='nw',
                             font=(UI_FONT, 8), fill=MUTED)
            return
        categories = apps.category_totals(records)
        ranked = sorted(categories, key=lambda key: categories[key], reverse=True)
        # Three headline categories plus an "other" bucket keep the compact
        # legend readable at 364 px.
        order = ranked[:3]
        rest = ranked[3:]
        if rest:
            categories['other'] = categories.get('other', 0) + sum(
                categories[key] for key in rest if key != 'other')
            if 'other' not in order:
                order = order + ['other']
        short = {'dev': '开发', 'browse': '浏览', 'ai': 'AI',
                 'fun': '娱乐', 'system': '系统', 'other': '其他'}
        left = 0
        width = self.card_w
        cursor = left
        for index, key in enumerate(order):
            value = categories[key]
            span = width * value / total
            color = apps.CATEGORIES[key][1]
            self.create_rectangle(cursor, 0, cursor + span, 8,
                                  fill=color, outline='')
            if index == 0:
                self.create_oval(cursor, 0, cursor + 8, 8, fill=color, outline='')
            if index == len(order) - 1:
                self.create_oval(cursor + span - 8, 0, cursor + span, 8,
                                 fill=color, outline='')
            cursor += span

        legend_width = width / max(1, len(order))
        for index, key in enumerate(order):
            x = index * legend_width
            color = apps.CATEGORIES[key][1]
            self.create_oval(x, 19, x + 6, 25, fill=color, outline='')
            self.create_text(x + 11, 16, text=short[key], anchor='nw',
                             font=(UI_FONT, 7), fill=MUTED)
            self.create_text(x + legend_width - 4, 16,
                             text=f'{categories[key] / total:.0%}', anchor='ne',
                             font=(UI_FONT, 7, 'bold'), fill=color)

        maximum = max((record.seconds for record in records), default=1)
        for index, record in enumerate(records[:3]):
            top = 34 + index * 26
            color = apps.CATEGORIES[record.category][1]
            self.create_oval(0, top + 5, 6, top + 11, fill=color, outline='')
            self.create_text(12, top, text=record.display, anchor='nw',
                             font=(UI_FONT, 8), fill=INK)
            self.create_text(width - 4, top, text=usage_text(record.seconds),
                             anchor='ne', font=(UI_FONT, 8, 'bold'), fill=INK)
            bar_width = max(3, (width - 120) * min(1, record.seconds / maximum))
            self.create_line(80, top + 18, width - 42, top + 18,
                             fill='#EEF2F8', width=5, capstyle='round')
            self.create_line(80, top + 18, 80 + bar_width, top + 18,
                             fill=color, width=5, capstyle='round')


class Hub(Card):
    WIDTH = 580
    HEIGHT = 600

    def __init__(self, app):
        super().__init__(app, self.WIDTH, inset=10, radius=14)
        self.attributes('-topmost', False)
        self.app = app
        self.current = 'today'
        self._drag = None
        self._last_data = 0.0
        self._favorite_signature = None
        self.avatar_image = None
        try:
            image = tk.PhotoImage(file=str(self._asset('menu-avatar.png')))
            self.avatar_image = image.subsample(2, 2) if image.width() > 44 else image
        except tk.TclError:
            self.avatar_image = None
        self._build()
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.finish(x, y)
        self.bind('<Escape>', lambda event: self.app.close_hub())
        self.refresh()

    def _asset(self, name):
        from pathlib import Path
        return Path(__file__).resolve().parent.parent / 'assets' / 'ui' / name

    # -- shell ---------------------------------------------------------
    def _build(self):
        self.rail = tk.Frame(self.body, bg=SOFT, width=156, height=580)
        self.rail.pack(side='left')
        self.rail.pack_propagate(False)
        self.right = tk.Frame(self.body, bg=CARD)
        self.right.pack(side='left', fill='both', expand=True)

        head = tk.Frame(self.rail, bg=SOFT)
        head.place(x=0, y=0, width=156, height=100)
        avatar = tk.Canvas(head, width=40, height=40, bg=SOFT,
                           highlightthickness=0)
        avatar.place(x=18, y=14)
        if self.avatar_image is not None:
            avatar.create_image(20, 20, image=self.avatar_image)
        else:
            avatar.create_oval(2, 2, 38, 38, fill='#EEF2FF', outline='#DCE4FA')
            avatar.create_text(20, 20, text='汐', fill=ACCENT,
                               font=(UI_FONT, 10, 'bold'))
        avatar.create_oval(1, 1, 39, 39, outline='#E1E7F5')
        name = tk.Label(head, text='小汐', font=(UI_FONT, 12, 'bold'),
                        bg=SOFT, fg=INK)
        name.place(x=18, y=60)
        self.rail_status = tk.Label(head, text='在这里陪你', font=(UI_FONT, 7),
                                    bg=SOFT, fg=MUTED)
        self.rail_status.place(x=18, y=79)
        for widget in (head, avatar, name, self.rail_status):
            self._bind_drag(widget)

        nav = [('today', '今天', '\uE80F')] + [
            (key, CATEGORIES[key][0], category_icon(key)) for key in CATEGORIES
        ]
        self.nav_items = {}
        for index, (key, label, code) in enumerate(nav):
            item = NavItem(self.rail, code, label,
                           lambda k=key: self.select(k), width=132, height=36)
            item.place(x=12, y=110 + index * 42)
            self.nav_items[key] = item

        bottom = tk.Frame(self.rail, bg=SOFT)
        bottom.place(x=8, y=530, width=140, height=42)
        self.hide_label = self._bottom_action(bottom, 0, '\uE7B3', '隐藏',
                                              self.app.toggle_pet_visibility)
        self._bottom_action(bottom, 46, '\uE713', '设置', self._open_settings)
        self._bottom_action(bottom, 92, '\uE7E8', '退出', self._exit, danger=True)

        self.topbar = tk.Frame(self.right, bg=CARD, height=30)
        self.topbar.pack(fill='x')
        self.topbar.pack_propagate(False)
        close = tk.Label(self.topbar, text='×', font=(UI_FONT, 14), bg=CARD,
                         fg=MUTED, cursor='hand2')
        close.place(relx=1.0, x=-16, y=4, anchor='ne')
        close.bind('<Button-1>', lambda event: self.app.close_hub())
        mini = tk.Label(self.topbar, text='—', font=(UI_FONT, 12), bg=CARD,
                        fg=MUTED, cursor='hand2')
        mini.place(relx=1.0, x=-42, y=6, anchor='ne')
        mini.bind('<Button-1>', lambda event: self.app.close_hub())
        self.topbar.bind('<ButtonPress-1>', self._start_drag)
        self.topbar.bind('<B1-Motion>', self._move_drag)
        self.topbar.bind('<ButtonRelease-1>', self._end_drag)

        self.content = tk.Frame(self.right, bg=CARD)
        self.content.place(x=20, y=36, width=364, height=534)
        self._show_today()

    def _bottom_action(self, parent, x, icon_code, label, command, danger=False):
        cell = tk.Frame(parent, bg=SOFT, width=44, height=42)
        cell.place(x=x, y=0)
        cell.pack_propagate(False)
        icon = tk.Label(cell, text=icon_code, font=(icon_family(self), 10),
                        bg=SOFT, fg=DANGER if danger else ICON)
        icon.place(x=0, y=1, width=44)
        text = tk.Label(cell, text=label, font=(UI_FONT, 7), bg=SOFT,
                        fg=DANGER if danger else MUTED)
        text.place(x=0, y=20, width=44)
        for widget in (cell, icon, text):
            widget.configure(cursor='hand2')

            def enter(event=None):
                for item in (cell, icon, text):
                    item.configure(bg=HOVER)
                icon.configure(fg=DANGER if danger else ACCENT)

            def leave(event=None):
                for item in (cell, icon, text):
                    item.configure(bg=SOFT)
                icon.configure(fg=DANGER if danger else ICON)

            def click(event=None):
                command()
                return 'break'

            widget.bind('<Enter>', enter)
            widget.bind('<Leave>', leave)
            widget.bind('<Button-1>', click)
        return text

    def _start_drag(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _move_drag(self, event):
        if self._drag:
            self.geometry(f'+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}')

    def _end_drag(self, event=None):
        self._drag = None

    def _bind_drag(self, widget):
        widget.bind('<ButtonPress-1>', self._start_drag)
        widget.bind('<B1-Motion>', self._move_drag)
        widget.bind('<ButtonRelease-1>', self._end_drag)

    # -- navigation ----------------------------------------------------
    def select(self, key):
        self.current = key
        for name, item in self.nav_items.items():
            item.set_selected(name == key)
        if key == 'today':
            self._show_today()
        else:
            self._show_category(key)
        self.refresh()

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.primary = None
        self.date_label = None
        self.stats = []
        self.fav_host = None
        self.reminder = None
        self.usage_mini = None
        self.todo_host = None
        self.summary = None

    def _show_today(self):
        self._clear_content()
        self.current = 'today'
        self._favorite_signature = None
        self._last_data = 0.0
        for name, item in self.nav_items.items():
            item.set_selected(name == 'today')
        c = self.content
        title = tk.Label(c, text='今天', font=(UI_FONT, 15, 'bold'), bg=CARD, fg=INK)
        title.place(x=0, y=0)
        self.date_label = tk.Label(c, text='', font=(UI_FONT, 7), bg=CARD, fg=MUTED)
        self.date_label.place(x=0, y=29)
        self.primary = tk.Button(c, text='开始 25 分钟专注', font=(UI_FONT, 8),
                                 bg=ACCENT, fg='white', activebackground='#4E61C0',
                                 activeforeground='white', relief='flat', bd=0,
                                 cursor='hand2', command=self._focus)
        self.primary.place(x=252, y=0, width=112, height=30)

        self.stats = []
        for index in range(3):
            card = StatCard(c)
            card.place(x=index * 124, y=46)
            self.stats.append(card)

        tk.Label(c, text='我的常用', font=(UI_FONT, 9, 'bold'), bg=CARD,
                 fg=INK).place(x=0, y=120)
        edit = tk.Label(c, text='编辑', font=(UI_FONT, 7), bg=CARD, fg=ACCENT,
                        cursor='hand2')
        edit.place(x=364, y=122, anchor='ne')
        edit.bind('<Button-1>', lambda event: self.app.edit_favorites())
        self.fav_host = tk.Frame(c, bg=CARD, width=364, height=80)
        self.fav_host.place(x=0, y=134)
        self.fav_host.pack_propagate(False)

        self.reminder = ReminderCard(c)
        self.reminder.place(x=0, y=216)

        tk.Label(c, text='今日应用', font=(UI_FONT, 9, 'bold'), bg=CARD,
                 fg=INK).place(x=0, y=258)
        view = tk.Label(c, text='查看全部', font=(UI_FONT, 7), bg=CARD,
                        fg=ACCENT, cursor='hand2')
        view.place(x=364, y=260, anchor='ne')
        view.bind('<Button-1>', lambda event: self._open_usage())
        self.usage_mini = UsageMini(c, command=self._open_usage)
        self.usage_mini.place(x=0, y=276)

        tk.Label(c, text='最近待办', font=(UI_FONT, 9, 'bold'), bg=CARD,
                 fg=INK).place(x=0, y=394)
        self.todo_host = tk.Frame(c, bg=CARD, width=364, height=56)
        self.todo_host.place(x=0, y=408)

        self.summary = SummaryCard(c)
        self.summary.place(x=0, y=464)
        tk.Label(c, text='点击左侧切换功能；最常用操作固定在右侧',
                 font=(UI_FONT, 7), bg=CARD, fg=CAPTION).place(x=0, y=512)

    def _show_category(self, key):
        self._clear_content()
        self.current = key
        c = self.content
        tk.Label(c, text=CATEGORIES[key][0], font=(UI_FONT, 15, 'bold'),
                 bg=CARD, fg=INK).place(x=0, y=0)
        tk.Label(c, text=CATEGORIES[key][1], font=(UI_FONT, 8), bg=CARD,
                 fg=MUTED, wraplength=240, justify='left').place(x=0, y=30)
        open_button = tk.Button(c, text='打开完整页面', font=(UI_FONT, 8),
                                bg='#EEF2FF', fg=ACCENT, activebackground='#DCE4FF',
                                relief='flat', bd=0, cursor='hand2',
                                command=lambda: self._open_panel(key))
        open_button.place(x=252, y=0, width=112, height=30)

        actions = self.app.registry.category(key)[:7]
        if not actions:
            tk.Label(c, text='此分类没有可用操作，可能对应插件已停用。',
                     font=(UI_FONT, 8), bg=CARD, fg=MUTED).place(x=0, y=74)
            return
        for index, action in enumerate(actions):
            row = ActionRow(c, category_icon(key), action.title,
                            lambda action_id=action.id: self._invoke(action_id))
            row.place(x=0, y=64 + index * 36)
            if not self.app.registry.available(action):
                for widget in (row, row.icon, row.text, row.chevron):
                    widget.configure(bg=CARD)
                row.text.configure(fg='#B7BFCD')

        self._category_context(key, 64 + len(actions) * 36 + 12)

        tk.Label(c, text='更多设置请点右上角「打开完整页面」。',
                 font=(UI_FONT, 7), bg=CARD, fg=CAPTION).place(x=0, y=510)

    def _category_context(self, key, start):
        c = self.content
        day = datetime.now().date().isoformat()
        if key == 'usage':
            try:
                records = self.app.store.usage_records(day)
            except Exception:
                records = []
            total = sum(record.seconds for record in records)
            tk.Label(c, text='今日应用', font=(UI_FONT, 9, 'bold'), bg=CARD,
                     fg=INK).place(x=0, y=start)
            host = tk.Frame(c, bg=CARD, width=364, height=68)
            host.place(x=0, y=start + 18)
            host.pack_propagate(False)
            UsageTable(host, self.app, width=364).pack()
            top = records[0].display if records else '暂无记录'
            tk.Label(c, text=f'今日共 {duration(total)} · {len(records)} 个应用 · 最常使用 {top}',
                     font=(UI_FONT, 8), bg=CARD, fg=MUTED).place(x=0, y=start + 92)
            return
        if key == 'productivity':
            reminder = ReminderCard(c)
            reminder.place(x=0, y=start)
            reminder.update(*self._reminder_pair())
            kind, value, fraction, paused = timer_state(self.app)
            cards = []
            for index in range(3):
                card = StatCard(c)
                card.place(x=index * 124, y=start + 46)
                cards.append(card)
            cards[0].update(kind + (' · 暂停' if paused else ''), value, '\uE916', ring=fraction)
            cards[1].update('今日', usage_text(today_seconds(self.app)), '\uE9D2')
            cards[2].update('待办', f'{open_todos(self.app)} 项', '\uE71D')
            return
        if key == 'shortcuts':
            try:
                items = self.app.store.get('plugin.shortcuts.items', [])
            except Exception:
                items = []
            tk.Label(c, text=f'已配置 {len(items)} 个入口', font=(UI_FONT, 9, 'bold'),
                     bg=CARD, fg=INK).place(x=0, y=start)
            names = ' · '.join(str(item.get('name', '')) for item in items[:3])
            tk.Label(c, text=names or '还没有添加入口；可在完整页面添加软件、文件夹或网址。',
                     font=(UI_FONT, 8), bg=CARD, fg=MUTED,
                     wraplength=350, justify='left').place(x=0, y=start + 22)
            return
        if key == 'companion':
            scale = int(round(getattr(self.app, 'live2d_scale', 0.8) * 100))
            prefs = self.app.store.get('pet.behavior', {})
            enabled = [title for name, title in
                       [('breathe', '呼吸'), ('blink', '眨眼'), ('wings', '翅膀'),
                        ('hair', '头发'), ('mouth', '张嘴')] if prefs.get(name, True)]
            tk.Label(c, text=f'Live2D V26 · 形象 {scale}%', font=(UI_FONT, 9, 'bold'),
                     bg=CARD, fg=INK).place(x=0, y=start)
            tk.Label(c, text='已开启：' + (' · '.join(enabled) if enabled else '无'),
                     font=(UI_FONT, 8), bg=CARD, fg=MUTED).place(x=0, y=start + 22)
            return
        if key == 'settings':
            try:
                plugins = len(self.app.plugins.plugins)
            except Exception:
                plugins = 0
            tk.Label(c, text=f'已加载 {plugins} 个插件', font=(UI_FONT, 9, 'bold'),
                     bg=CARD, fg=INK).place(x=0, y=start)
            tk.Label(c, text=f'数据目录：{self.app.store.directory}', font=(UI_FONT, 8),
                     bg=CARD, fg=MUTED, wraplength=350, justify='left').place(x=0, y=start + 22)

    def _reminder_pair(self):
        try:
            rows = [item for item in self.app.store.get('plugin.productivity.reminders', [])
                    if not item.get('done')]
        except Exception:
            rows = []
        if not rows:
            return '暂无提醒', '在专注页添加'
        try:
            item = min(rows, key=lambda row: row['due'])
            due = datetime.fromisoformat(item['due'])
            minutes = int((due - datetime.now()).total_seconds() // 60)
            right = f'还有 {minutes} 分钟' if minutes > 0 else '已到期'
            title = item.get('title', '')
            if len(title) > 14:
                title = title[:13] + '…'
            return f'下次提醒 {due.strftime("%H:%M")} · {title}', right
        except (KeyError, ValueError):
            return '暂无提醒', '在专注页添加'

    # -- data / refresh ------------------------------------------------
    def refresh(self):
        if not self.winfo_exists():
            return
        self.rail_status.config(text=self._status_line())
        if getattr(self, 'hide_label', None) is not None:
            self.hide_label.config(text='显示' if self.app.pet_hidden else '隐藏')
        if self.current == 'today' and self.date_label is not None:
            now = datetime.now()
            self.date_label.config(text=f'{now.month} 月 {now.day} 日 · 周{WEEK[now.weekday()]}')
            self._refresh_stats()
            self._refresh_primary()
            self._refresh_favorites()
            self._refresh_reminder()
            if time.monotonic() - self._last_data > 4:
                self._last_data = time.monotonic()
                self._refresh_data()

    def _status_line(self):
        try:
            if self.app.store.get('dnd', False):
                return '免打扰'
            if getattr(self.app, 'focused', False):
                return '专注模式'
        except Exception:
            pass
        return '在这里陪你'

    def _refresh_stats(self):
        kind, value, fraction, paused = timer_state(self.app)
        label = kind + (' · 暂停' if paused else '')
        if self.stats:
            self.stats[0].update(label, value, '\uE916', ring=fraction)
            self.stats[1].update('今日', usage_text(today_seconds(self.app)), '\uE9D2')
            self.stats[2].update('待办', f'{open_todos(self.app)} 项', '\uE71D')

    def _refresh_primary(self):
        if self.primary is None:
            return
        action = self.app.registry.items.get('productivity.focus')
        if action is None:
            self.primary.configure(state='disabled', text='专注插件未启用')
            return
        self.primary.configure(text=action.title,
                               state='normal' if self.app.registry.available(action) else 'disabled')

    def _refresh_favorites(self):
        if self.fav_host is None:
            return
        actions = []
        for key in self.app.favorite_ids()[:4]:
            action = self.app.registry.items.get(key)
            if action is not None:
                actions.append(action)
        signature = [(action.id, action.title, self.app.registry.available(action))
                     for action in actions]
        if signature == self._favorite_signature:
            return
        self._favorite_signature = signature
        for child in self.fav_host.winfo_children():
            child.destroy()
        if not actions:
            tk.Label(self.fav_host, text='还没有常用操作，点「编辑」添加。',
                     font=(UI_FONT, 8), bg=CARD, fg=MUTED).place(x=0, y=8)
            return
        for index, action in enumerate(actions):
            chip = Chip(self.fav_host, category_icon(action.category), action.title,
                        lambda key=action.id: self._invoke(key),
                        enabled=self.app.registry.available(action))
            chip.place(x=(index % 2) * 186, y=(index // 2) * 40)

    def _refresh_reminder(self):
        if self.reminder is None:
            return
        self.reminder.update(*self._reminder_pair())

    def _refresh_data(self):
        day = datetime.now().date().isoformat()
        try:
            records = self.app.store.usage_records(day)
        except Exception:
            records = []
        total = sum(record.seconds for record in records)
        if self.usage_mini is not None:
            self.usage_mini.update(records, total)
        if self.todo_host is not None:
            for child in self.todo_host.winfo_children():
                child.destroy()
            try:
                todos = [item for item in self.app.store.get('plugin.productivity.todos', [])
                         if not item.get('done')][:2]
            except Exception:
                todos = []
            if not todos:
                tk.Label(self.todo_host, text='暂无未完成待办', font=(UI_FONT, 8),
                         bg=CARD, fg=MUTED).place(x=0, y=4)
            for index, item in enumerate(todos):
                row = tk.Frame(self.todo_host, bg='#F8FAFE', height=26)
                row.place(x=0, y=index * 28, width=364, height=26)
                tk.Label(row, text='\uE739', font=(icon_family(self), 9),
                         bg='#F8FAFE', fg=MUTED).place(x=10, y=5)
                tk.Label(row, text=item.get('title', ''), font=(UI_FONT, 8),
                         bg='#F8FAFE', fg=INK).place(x=24, y=4)
                tk.Label(row, text='待完成', font=(UI_FONT, 7), bg='#F8FAFE',
                         fg=MUTED).place(x=352, y=6, anchor='ne')
        if self.summary is not None:
            try:
                minutes = self.app.store.event_sum(day, 'focus_planned_minutes')
            except Exception:
                minutes = 0
            try:
                done = sum(1 for item in self.app.store.get('plugin.productivity.todos', [])
                           if item.get('done') and str(item.get('completed', '')).startswith(day))
            except Exception:
                done = 0
            top = records[0].display if records else '暂无记录'
            self.summary.update(f'专注 {minutes:g} 分钟 · 待办完成 {done} 项 · 最常使用 {top}')

    # -- actions -------------------------------------------------------
    def _focus(self):
        try:
            self.app.invoke_action('productivity.focus')
        except Exception as exc:
            messagebox.showerror('专注', str(exc), parent=self)
        self.refresh()

    def _invoke(self, action_id):
        try:
            self.app.invoke_action(action_id)
        except Exception as exc:
            messagebox.showerror('操作未完成', str(exc), parent=self)
        self.refresh()

    def _open_usage(self):
        self.hide()
        self.app.show_usage_dashboard()

    def _open_panel(self, category):
        self.hide()
        if category == 'usage':
            self.app.show_usage_dashboard()
        else:
            self.app.show_panel(category)

    def _open_settings(self):
        self.hide()
        self.app.show_panel('settings')

    def _exit(self):
        if messagebox.askyesno('退出桌宠', '确定退出小汐吗？', parent=self):
            self.app.close()

    def show(self):
        self.deiconify()
        # Briefly raise above other apps, then return to normal stacking. The
        # hub is also reachable from the pet if it is covered later.
        self.attributes('-topmost', True)
        self.lift()
        self.after(160, self._drop_topmost)
        self.focus_force()
        self.refresh()

    def _drop_topmost(self):
        try:
            if self.winfo_exists():
                self.attributes('-topmost', False)
        except tk.TclError:
            pass

    def hide(self):
        self.withdraw()
