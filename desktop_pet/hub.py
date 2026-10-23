"""Compact, keyboard-friendly home for the desktop companion.

The content uses layout managers and a scrollable viewport so text, actions and
status cards remain reachable on smaller screens and at larger display scales.
"""
import math
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import messagebox, ttk

from desktop_pet.actions import CATEGORIES
from desktop_pet import apps
from desktop_pet.ui import SOFT, draw_icon, fit_text, text_button
from desktop_pet.menu import (
    ACCENT, CAPTION, CARD, DANGER, HOVER, ICON, INK, MUTED, SEP, UI_FONT,
    Card, icon_family, open_todos, rounded_rect, timer_state, today_seconds,
    usage_text,
)

WEEK = '一二三四五六日'
DISABLED = '#8C96A8'


def bordered_round(canvas, x1, y1, x2, y2, radius, fill, border=SEP):
    rounded_rect(canvas, x1, y1, x2, y2, radius, border)
    rounded_rect(canvas, x1 + 1, y1 + 1, x2 - 1, y2 - 1,
                 max(1, radius - 1), fill)


def category_icon(key):
    return {
        'companion': '\uEB51', 'productivity': '\uE916', 'shortcuts': '\uE945',
        'usage': '\uE9D2', 'settings': '\uE713',
    }.get(key, '\uE734')


def compact_categories(records, limit=3):
    """Keep the largest named categories and one non-duplicated other bucket."""
    totals = apps.category_totals(records)
    named = sorted(((key, value) for key, value in totals.items()
                    if key != 'other' and value > 0), key=lambda item: -item[1])
    visible = named[:max(0, limit)]
    other = totals.get('other', 0) + sum(value for _, value in named[max(0, limit):])
    if other > 0:
        visible.append(('other', other))
    return visible


def reminder_pair(rows, now=None):
    """Return the nearest valid reminder without losing it to a corrupt row."""
    now = now or datetime.now()
    upcoming = []
    for row in rows if isinstance(rows, (list, tuple)) else []:
        if not isinstance(row, dict) or row.get('done'):
            continue
        try:
            due = datetime.fromisoformat(row['due'])
            seconds = (due - now).total_seconds()
        except (KeyError, TypeError, ValueError):
            continue
        upcoming.append((seconds, due, row))
    if not upcoming:
        return '暂无提醒', '在专注页添加'
    seconds, due, row = min(upcoming, key=lambda item: item[0])
    right = ('已到期' if seconds <= 0 else '即将到期' if seconds < 60
             else f'还有 {math.ceil(seconds / 60)} 分钟')
    return f'{due:%H:%M} · {row.get("title") or "未命名提醒"}', right


class Surface(tk.Canvas):
    """A size-aware canvas; text measurements use the actual Tk font."""
    def __init__(self, parent, width=420, height=48, background=CARD):
        super().__init__(parent, width=width, height=height, bg=background,
                         highlightthickness=0, bd=0)
        self.card_w, self.card_h = width, height
        self.icon_font = icon_family(self.winfo_toplevel())
        self._fonts = {}
        self.bind('<Configure>', self._resize)

    def _resize(self, event):
        if (event.width, event.height) != (self.card_w, self.card_h):
            self.card_w, self.card_h = event.width, event.height
            self.draw()

    def font(self, size=9, weight='normal'):
        key = (size, weight)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(self, family=UI_FONT, size=size, weight=weight)
        return self._fonts[key]

    def line(self, x, y, text, width, size=9, weight='normal', fill=INK, anchor='w'):
        font = self.font(size, weight)
        return self.create_text(x, y, text=fit_text(text, font.measure, width),
                                font=font, fill=fill, anchor=anchor)

    def symbol(self, x, y, code, size=12, fill=ICON, anchor='w'):
        names = {'\uEB51': 'heart', '\uE916': 'clock', '\uE945': 'bolt',
                 '\uE9D2': 'chart', '\uE713': 'settings', '\uE734': 'spark',
                 '\uE80F': 'home', '\uE823': 'bell', '\uE71D': 'check',
                 '\uE76C': 'chevron', '\uE739': 'circle'}
        pixels = max(14, size * 1.4)
        draw_icon(self, x, y - pixels / 2, names.get(code, 'spark'), pixels, fill)

    def draw(self):
        pass


class Chip(Surface):
    def __init__(self, parent, icon_code, label, command, width=202, height=40,
                 enabled=True):
        self.icon_code, self.label, self.command = icon_code, label, command
        self.enabled, self.hover, self.focused = enabled, False, False
        super().__init__(parent, width, height)
        self.configure(takefocus=enabled, cursor='hand2' if enabled else 'arrow')
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<FocusIn>', self._focus_in)
        self.bind('<FocusOut>', self._focus_out)
        self.bind('<Button-1>', self._click)
        self.bind('<Return>', self._click)
        self.bind('<space>', self._click)
        self.draw()

    def set_content(self, label, enabled=True):
        if (self.label, self.enabled) != (label, enabled):
            self.label, self.enabled = label, enabled
            self.configure(takefocus=enabled, cursor='hand2' if enabled else 'arrow')
            self.draw()

    def draw(self):
        self.delete('all')
        active = self.enabled and (self.hover or self.focused)
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 9,
                       HOVER if active else SOFT,
                       ACCENT if self.focused and self.enabled else SEP)
        self.symbol(13, self.card_h / 2, self.icon_code, 11,
                    ACCENT if self.enabled else DISABLED)
        self.line(34, self.card_h / 2, self.label, self.card_w - 46,
                  fill=INK if self.enabled else DISABLED)

    def _enter(self, event=None):
        self.hover = True
        self.draw()

    def _leave(self, event=None):
        self.hover = False
        self.draw()

    def _focus_in(self, event=None):
        self.focused = True
        self.draw()

    def _focus_out(self, event=None):
        self.focused = False
        self.draw()

    def _click(self, event=None):
        if self.enabled:
            self.focus_set()
            self.command()
        return 'break'


class NavItem(Chip):
    def __init__(self, parent, icon_code, label, command, width=140, height=42):
        self.selected = False
        super().__init__(parent, icon_code, label, command, width, height)
        self.configure(bg=SOFT)

    def draw(self):
        self.delete('all')
        fill = '#E0EBDD' if self.selected else (CARD if self.hover else SOFT)
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 9, fill,
                       ACCENT if self.focused else fill)
        if self.selected:
            self.create_line(3, 13, 3, self.card_h - 13, fill=ACCENT, width=3)
        color = ACCENT if self.selected else INK if self.hover else MUTED
        self.symbol(14, self.card_h / 2, self.icon_code, 12, color)
        self.line(36, self.card_h / 2, self.label, self.card_w - 44,
                  weight='bold' if self.selected else 'normal', fill=color)

    def set_selected(self, selected):
        self.selected = selected
        self.draw()


class ActionRow(Chip):
    def __init__(self, parent, icon_code, label, command, width=420, height=44,
                 enabled=True):
        super().__init__(parent, icon_code, label, command, width, height, enabled)

    def draw(self):
        # Reserve the right edge for navigation, even with long action names.
        self.delete('all')
        active = self.enabled and (self.hover or self.focused)
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 9,
                       HOVER if active else SOFT,
                       ACCENT if self.focused and self.enabled else SEP)
        self.symbol(14, self.card_h / 2, self.icon_code, 11,
                    ACCENT if self.enabled else DISABLED)
        self.line(36, self.card_h / 2, self.label, self.card_w - 68,
                  fill=INK if self.enabled else DISABLED)
        self.symbol(self.card_w - 18, self.card_h / 2, '\uE76C', 10,
                    ICON if self.enabled else DISABLED)


class StatCard(Surface):
    def __init__(self, parent, width=132, height=76):
        self.data = ('', '', '', None)
        super().__init__(parent, width, height)

    def update(self, label, value, icon_code, ring=None):
        self.data = (label, value, icon_code, ring)
        self.draw()

    def draw(self):
        self.delete('all')
        label, value, icon_code, ring = self.data
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 11, SOFT)
        self.line(13, 20, label, self.card_w - 28, size=9, fill=MUTED)
        if ring is not None:
            self.create_oval(13, 37, 36, 60, outline='#DAE4D9', width=3)
            if ring > 0:
                self.create_arc(13, 37, 36, 60, start=90, extent=-359.9 * ring,
                                style='arc', outline=ACCENT, width=3)
            self.line(46, 49, value, self.card_w - 56, 13, 'bold')
        else:
            self.line(13, 49, value, self.card_w - 39, 15, 'bold')
            self.symbol(self.card_w - 25, 49, icon_code, 12, ACCENT)


class ReminderCard(Chip):
    def __init__(self, parent, width=420, height=58, command=None):
        self.detail = ''
        super().__init__(parent, '\uE823', '', command or (lambda: None), width, height)

    def update(self, text, right=''):
        self.label, self.detail = text, right
        self.draw()

    def draw(self):
        self.delete('all')
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 10,
                       HOVER if self.hover else '#EFF4E9',
                       ACCENT if self.focused else '#DFE8D5')
        self.symbol(14, self.card_h / 2, '\uE823', 12, ACCENT)
        self.line(37, 17, '下一次提醒', self.card_w - 150, 8, fill=MUTED)
        self.line(self.card_w - 14, 17, self.detail, 110, 8, fill=ACCENT, anchor='e')
        self.line(37, 39, self.label, self.card_w - 52, 9)


class SummaryCard(Surface):
    def __init__(self, parent, width=420, height=60):
        self.text = ''
        super().__init__(parent, width, height)

    def update(self, text):
        self.text = text
        self.draw()

    def draw(self):
        self.delete('all')
        bordered_round(self, 1, 1, self.card_w - 1, self.card_h - 1, 10, SOFT)
        self.symbol(14, 19, '\uE734', 11, ACCENT)
        self.line(36, 19, '每一点进展，都值得被看见', self.card_w - 50, 9, 'bold')
        self.line(14, 42, self.text, self.card_w - 28, 8, fill=MUTED)


class UsageMini(Chip):
    def __init__(self, parent, width=420, height=134, command=None):
        self.records, self.total = [], 0
        super().__init__(parent, '\uE9D2', '查看应用统计', command or (lambda: None), width, height)

    def update(self, records, total):
        self.records, self.total = records, total
        self.draw()

    def draw(self):
        self.delete('all')
        w = self.card_w
        bordered_round(self, 1, 1, w - 1, self.card_h - 1, 10, SOFT,
                       ACCENT if self.focused else SEP)
        if not self.records or self.total <= 0:
            self.symbol(18, 36, '\uE9D2', 17, ACCENT)
            self.line(48, 36, '今天还没有使用记录', w - 62, 10, 'bold')
            self.line(18, 70, '使用应用后，这里会显示你的时间分布。', w - 36, 9, fill=MUTED)
            self.line(18, 98, '仅在本机统计，空闲与锁屏时暂停。', w - 36, 8, fill=MUTED)
            return
        order = compact_categories(self.records)
        cursor = 14
        for key, seconds in order:
            span = (w - 28) * seconds / self.total
            self.create_rectangle(cursor, 13, cursor + span, 19,
                                  fill=apps.CATEGORIES[key][1], outline='')
            cursor += span
        short = {'dev': '开发', 'browse': '浏览', 'ai': 'AI', 'fun': '娱乐',
                 'system': '系统', 'other': '其他'}
        cell = (w - 28) / max(1, len(order))
        for index, (key, seconds) in enumerate(order):
            self.line(14 + index * cell, 33, f'{short[key]} {seconds / self.total:.0%}',
                      cell - 6, 8, fill=MUTED)
        maximum = max(record.seconds for record in self.records) or 1
        for index, record in enumerate(self.records[:3]):
            y = 55 + index * 26
            color = apps.CATEGORIES[record.category][1]
            self.create_oval(14, y - 3, 20, y + 3, fill=color, outline='')
            value = usage_text(record.seconds)
            value_width = self.font(9, 'bold').measure(value)
            self.line(27, y, record.display, w - 59 - value_width, 9)
            self.line(w - 14, y, value, value_width + 1, 9, 'bold', anchor='e')
            self.create_line(27, y + 11, w - 14, y + 11, fill='#DEE7DB', width=3)
            self.create_line(27, y + 11, 27 + (w - 41) * record.seconds / maximum,
                             y + 11, fill=color, width=3)


class Hub(Card):
    WIDTH = 680
    HEIGHT = 700

    def __init__(self, app):
        width = min(self.WIDTH, app.root.winfo_screenwidth() - 16)
        super().__init__(app, width, inset=10, radius=14)
        self.attributes('-topmost', False)
        self.title('小汐 · 功能小屋')
        self.current = 'today'
        self._drag = None
        self._last_data = 0.0
        self._favorite_signature = None
        self._todo_signature = None
        self._category_ids = ()
        self._category_rows = {}
        self.avatar_image = None
        self.body_height = min(self.HEIGHT - 20, self.winfo_screenheight() - 48)
        self.rail_width = 164 if width >= 620 else 148
        self.content_width = max(160, width - 20 - self.rail_width - 44)
        try:
            image = tk.PhotoImage(file=str(self._asset('menu-avatar.png')))
            ratio = max(1, math.ceil(max(image.width(), image.height()) / 48))
            self.avatar_image = image.subsample(ratio, ratio)
        except tk.TclError:
            pass
        self._build()
        self.finish((self.winfo_screenwidth() - width) // 2,
                    (self.winfo_screenheight() - self.body_height - 20) // 2)
        self.bind('<Escape>', lambda event: self.app.close_hub())
        self.bind('<MouseWheel>', self._wheel)
        self.bind('<Button-4>', self._wheel)
        self.bind('<Button-5>', self._wheel)
        self.bind('<Prior>', lambda event: self._scroll_page(-1))
        self.bind('<Next>', lambda event: self._scroll_page(1))
        self.bind('<FocusIn>', self._reveal_focus, add='+')
        self.refresh()

    def _asset(self, name):
        from pathlib import Path
        return Path(__file__).resolve().parent.parent / 'assets' / 'ui' / name

    def _build(self):
        self.rail = tk.Frame(self.body, bg=SOFT, width=self.rail_width, height=self.body_height)
        self.rail.pack(side='left', fill='y')
        self.rail.pack_propagate(False)
        self.right = tk.Frame(self.body, bg=CARD)
        self.right.pack(side='left', fill='both', expand=True)

        head = tk.Frame(self.rail, bg=SOFT, height=116)
        head.pack(fill='x', padx=16, pady=(18, 0))
        head.pack_propagate(False)
        avatar = tk.Canvas(head, width=48, height=48, bg=SOFT, highlightthickness=0)
        avatar.pack(anchor='w')
        if self.avatar_image is not None:
            avatar.create_image(24, 24, image=self.avatar_image)
        else:
            avatar.create_oval(1, 1, 47, 47, fill='#E1EBDD', outline='')
            avatar.create_text(24, 24, text='汐', fill=ACCENT, font=(UI_FONT, 16, 'bold'))
        name = tk.Label(head, text='小汐', font=(UI_FONT, 14, 'bold'), bg=SOFT, fg=INK)
        name.pack(anchor='w', pady=(6, 0))
        self.rail_status = tk.Label(head, text='在这里陪你', font=(UI_FONT, 9), bg=SOFT, fg=MUTED)
        self.rail_status.pack(anchor='w')
        for widget in (head, avatar, name, self.rail_status):
            self._bind_drag(widget)

        self.nav_items = {}
        nav = [('today', '今天', '\uE80F')] + [
            (key, CATEGORIES[key][0], category_icon(key)) for key in CATEGORIES]
        for key, label, code in nav:
            item = NavItem(self.rail, code, label, lambda k=key: self.select(k),
                           width=self.rail_width - 20)
            item.pack(fill='x', padx=10, pady=3)
            item.bind('<Up>', lambda event, k=key: self._nav_move(k, -1))
            item.bind('<Down>', lambda event, k=key: self._nav_move(k, 1))
            self.nav_items[key] = item

        bottom = tk.Frame(self.rail, bg=SOFT)
        bottom.pack(side='bottom', fill='x', padx=12, pady=14)
        tk.Label(bottom, text='轻一点的陪伴', font=(UI_FONT, 9), bg=SOFT,
                 fg=MUTED).pack(anchor='w', pady=(0, 8))
        self.hide_label = text_button(bottom, '隐藏角色', self.app.toggle_pet_visibility, quiet=True)
        self.hide_label.pack(fill='x')
        actions = tk.Frame(bottom, bg=SOFT)
        actions.pack(fill='x', pady=(2, 0))
        text_button(actions, '设置', self._open_settings, quiet=True).pack(side='left', expand=True)
        exit_button = text_button(actions, '退出', self._exit, quiet=True)
        exit_button.configure(fg=DANGER)
        exit_button.pack(side='right', expand=True)

        self.topbar = tk.Frame(self.right, bg=CARD, height=38)
        self.topbar.pack(fill='x')
        self.topbar.pack_propagate(False)
        self._bind_drag(self.topbar)
        title = tk.Label(self.topbar, text='功能小屋', font=(UI_FONT, 8), bg=CARD,
                         fg=CAPTION)
        title.pack(side='left', padx=20)
        self._bind_drag(title)
        text_button(self.topbar, '关闭 ×', self.app.close_hub, quiet=True).pack(side='right', padx=(0, 10))

        host = tk.Frame(self.right, bg=CARD)
        host.pack(fill='both', expand=True, padx=(18, 6), pady=(0, 8))
        self.viewport = tk.Canvas(host, bg=CARD, highlightthickness=0, bd=0,
                                  width=self.content_width)
        self.scrollbar = ttk.Scrollbar(host, orient='vertical', command=self.viewport.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.viewport.pack(side='left', fill='both', expand=True, padx=(0, 4))
        self.viewport.configure(yscrollcommand=self.scrollbar.set)
        self.content = tk.Frame(self.viewport, bg=CARD)
        self.content_window = self.viewport.create_window(0, 0, window=self.content, anchor='nw', width=self.content_width)
        self.content.bind('<Configure>', lambda event: self.viewport.configure(scrollregion=self.viewport.bbox('all')))
        self.viewport.bind('<Configure>', self._resize_content)
        self._show_today()

    def _resize_content(self, event):
        self.content_width = event.width
        self.viewport.itemconfigure(self.content_window, width=event.width)
        if self.date_label is not None:
            self.date_label.configure(wraplength=max(100, event.width - 4))
        if self.context_label is not None:
            self.context_label.configure(wraplength=max(100, event.width - 36))

    def _inside_content(self, widget):
        while widget is not None:
            if widget in (self.content, self.viewport):
                return True
            widget = getattr(widget, 'master', None)
        return False

    def _wheel(self, event):
        if self._inside_content(event.widget):
            if getattr(event, 'num', None) in (4, 5):
                units = -3 if event.num == 4 else 3
            else:
                delta = getattr(event, 'delta', 0)
                if not delta:
                    return
                units = -max(1, abs(int(delta / 120))) if delta > 0 else max(1, abs(int(delta / 120)))
            self.viewport.yview_scroll(units, 'units')
            return 'break'

    def _scroll_page(self, direction):
        self.viewport.yview_scroll(direction, 'pages')
        return 'break'

    def _reveal_focus(self, event):
        if not self._inside_content(event.widget) or event.widget is self.viewport:
            return
        widget = event.widget
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + widget.winfo_height()
        current = self.viewport.canvasy(0)
        height = self.viewport.winfo_height()
        total = max(1, self.content.winfo_height())
        if top < current:
            self.viewport.yview_moveto(max(0, top - 8) / total)
        elif bottom > current + height:
            self.viewport.yview_moveto((bottom - height + 8) / total)

    def _nav_move(self, key, offset):
        keys = list(self.nav_items)
        item = self.nav_items[keys[(keys.index(key) + offset) % len(keys)]]
        item.focus_set()
        item._click()
        return 'break'

    def _start_drag(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _move_drag(self, event):
        if self._drag:
            x = max(0, min(event.x_root - self._drag[0], self.winfo_screenwidth() - self.winfo_width()))
            y = max(0, min(event.y_root - self._drag[1], self.winfo_screenheight() - self.winfo_height()))
            self.geometry(f'+{x}+{y}')

    def _end_drag(self, event=None):
        self._drag = None

    def _bind_drag(self, widget):
        widget.bind('<ButtonPress-1>', self._start_drag)
        widget.bind('<B1-Motion>', self._move_drag)
        widget.bind('<ButtonRelease-1>', self._end_drag)

    def select(self, key):
        if key != 'today' and key not in CATEGORIES:
            return
        if key != self.current:
            self._show_today() if key == 'today' else self._show_category(key)
            self.viewport.yview_moveto(0)
        for name, item in self.nav_items.items():
            item.set_selected(name == key)
        self.refresh()

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.primary = self.date_label = self.fav_host = None
        self.reminder = self.usage_mini = self.todo_host = self.summary = None
        self.context_label = None
        self.stats = []
        self._category_rows = {}
        self._category_ids = ()
        self._favorite_signature = self._todo_signature = None
        self._last_data = 0.0

    def _header(self, title, subtitle, action=None):
        head = tk.Frame(self.content, bg=CARD)
        head.pack(fill='x', pady=(4, 12))
        title_row = tk.Frame(head, bg=CARD)
        title_row.pack(fill='x')
        if action:
            self.primary = text_button(title_row, action[0], action[1], primary=True)
            self.primary.pack(side='right', padx=(8, 0))
        tk.Label(title_row, text=title, font=(UI_FONT, 19, 'bold'), bg=CARD, fg=INK, anchor='w',
                 wraplength=self.content_width).pack(side='left')
        self.date_label = tk.Label(head, text=subtitle, font=(UI_FONT, 9), bg=CARD,
                                   fg=MUTED, justify='left', anchor='w', wraplength=self.content_width)
        self.date_label.pack(anchor='w', pady=(3, 0))

    def _section(self, title, link=None, command=None):
        row = tk.Frame(self.content, bg=CARD)
        row.pack(fill='x', pady=(10, 4))
        tk.Label(row, text=title, font=(UI_FONT, 10, 'bold'), bg=CARD, fg=INK).pack(side='left')
        if link:
            text_button(row, link, command, quiet=True).pack(side='right')

    def _make_stats(self, parent):
        host = tk.Frame(parent, bg=CARD)
        host.pack(fill='x')
        cards = []
        for index in range(3):
            host.columnconfigure(index, weight=1, uniform='stats')
            card = StatCard(host, width=max(100, (self.content_width - 16) // 3))
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 4, 0 if index == 2 else 4))
            cards.append(card)
        return cards

    def _show_today(self):
        self._clear_content()
        self.current = 'today'
        self._header('今天', '', ('开始 25 分钟专注', self._focus))
        self.stats = self._make_stats(self.content)
        self._section('我的常用', '编辑常用', self.app.edit_favorites)
        self.fav_host = tk.Frame(self.content, bg=CARD)
        self.fav_host.pack(fill='x')
        for index in (0, 1):
            self.fav_host.columnconfigure(index, weight=1, uniform='favorites')
        self.reminder = ReminderCard(self.content, command=lambda: self._open_panel('productivity'))
        self.reminder.pack(fill='x', pady=(12, 0))
        self._section('时间花在哪里', '查看全部 ›', self._open_usage)
        self.usage_mini = UsageMini(self.content, command=self._open_usage)
        self.usage_mini.pack(fill='x')
        self._section('最近待办', '管理待办 ›', lambda: self._open_panel('productivity'))
        self.todo_host = tk.Frame(self.content, bg=CARD)
        self.todo_host.pack(fill='x')
        self.summary = SummaryCard(self.content)
        self.summary.pack(fill='x', pady=(14, 10))
        tk.Label(self.content, text='数据只留在本机  ·  Tab 切换操作，Esc 收起小屋',
                 font=(UI_FONT, 8), bg=CARD, fg=CAPTION).pack(anchor='w', pady=(0, 8))
        for name, item in self.nav_items.items():
            item.set_selected(name == 'today')

    def _show_category(self, key):
        self._clear_content()
        self.current = key
        self._header(CATEGORIES[key][0], CATEGORIES[key][1])
        text_button(self.content, '打开完整页面 ↗', lambda: self._open_panel(key)).pack(anchor='w', pady=(0, 14))
        self.action_host = tk.Frame(self.content, bg=CARD)
        self.action_host.pack(fill='x')
        self.context_host = tk.Frame(self.content, bg=CARD)
        self.context_host.pack(fill='x', pady=(18, 8))
        if key == 'productivity':
            self.reminder = ReminderCard(self.context_host, command=lambda: self._open_panel(key))
            self.reminder.pack(fill='x', pady=(0, 10))
            self.stats = self._make_stats(self.context_host)
        elif key == 'usage':
            self.usage_mini = UsageMini(self.context_host, command=self._open_usage)
            self.usage_mini.pack(fill='x')
        else:
            self.context_label = tk.Label(self.context_host, bg=SOFT, fg=MUTED,
                font=(UI_FONT, 9), justify='left', anchor='w', padx=14, pady=14,
                wraplength=max(100, self.content_width - 36))
            self.context_label.pack(fill='x')
        tk.Label(self.content, text='完整页面中可管理更多设置与内容。', bg=CARD,
                 fg=CAPTION, font=(UI_FONT, 8)).pack(anchor='w', pady=8)
        self._refresh_category()

    def _refresh_category(self):
        actions = self.app.registry.category(self.current)
        ids = tuple(action.id for action in actions)
        if ids != self._category_ids or not self.action_host.winfo_children():
            self._category_ids = ids
            for child in self.action_host.winfo_children():
                child.destroy()
            self._category_rows = {}
            if not actions:
                tk.Label(self.action_host, text='暂时没有可用操作\n可在设置中检查对应插件。',
                         font=(UI_FONT, 10), bg=SOFT, fg=MUTED, justify='left',
                         padx=16, pady=20).pack(fill='x')
            for action in actions:
                row = ActionRow(self.action_host, category_icon(self.current), action.title,
                                lambda key=action.id: self._invoke(key),
                                enabled=self.app.registry.available(action))
                row.pack(fill='x', pady=(0, 6))
                self._category_rows[action.id] = row
        for action in actions:
            self._category_rows[action.id].set_content(action.title, self.app.registry.available(action))
        self._refresh_stats()
        self._refresh_reminder()
        if self.context_label is not None:
            if self.current == 'shortcuts':
                items = self.app.store.get('plugin.shortcuts.items', [])
                names = '、'.join(str(item.get('name', '')) for item in items[:3])
                text = f'已配置 {len(items)} 个快捷入口\n' + (names or '添加软件、文件夹或网址，让常用操作近一点。')
            elif self.current == 'companion':
                prefs = self.app.store.get('pet.behavior', {})
                enabled = [title for name, title in [('breathe', '呼吸'), ('blink', '眨眼'),
                           ('wings', '翅膀'), ('hair', '头发'), ('mouth', '张嘴')]
                           if prefs.get(name, True)]
                mode = ('Live2D · 形象 ' + str(round(getattr(self.app, 'live2d_scale', .8) * 100)) + '%'
                        if getattr(self.app, 'live2d_mode', False) else '图片形象模式')
                text = mode + '\n已开启：' + (' · '.join(enabled) if enabled else '无自动行为')
            else:
                text = f'已加载 {len(self.app.plugins.plugins)} 个插件\n数据目录：{self.app.store.directory}'
            self.context_label.configure(text=text)

    def _reminder_pair(self):
        return reminder_pair(self.app.store.get('plugin.productivity.reminders', []))

    def refresh(self):
        if not self.winfo_exists():
            return
        self.rail_status.configure(text=self._status_line())
        self.hide_label.configure(text='显示角色' if self.app.pet_hidden else '隐藏角色')
        if self.current == 'today':
            now = datetime.now()
            self.date_label.configure(text=f'{now.month} 月 {now.day} 日 · 星期{WEEK[now.weekday()]}')
            self._refresh_stats()
            self._refresh_primary()
            self._refresh_favorites()
            self._refresh_reminder()
        else:
            self._refresh_category()
        if time.monotonic() - self._last_data > 4:
            self._last_data = time.monotonic()
            self._refresh_data()

    def _status_line(self):
        if self.app.store.get('dnd', False):
            return '免打扰 · 安静陪伴'
        if getattr(self.app, 'focused', False):
            return '专注模式 · 一起加油'
        return '在这里陪你'

    def _refresh_stats(self):
        if self.stats:
            kind, value, fraction, paused = timer_state(self.app)
            self.stats[0].update(kind + (' · 暂停' if paused else ''), value, '\uE916', ring=fraction)
            self.stats[1].update('今日使用', usage_text(today_seconds(self.app)), '\uE9D2')
            self.stats[2].update('待完成', f'{open_todos(self.app)} 项', '\uE71D')

    def _refresh_primary(self):
        action = self.app.registry.items.get('productivity.focus')
        self.primary.configure(text=action.title if action else '专注插件未启用',
                               state='normal' if action and self.app.registry.available(action) else 'disabled')

    def _refresh_favorites(self):
        actions = [self.app.registry.items[key] for key in self.app.favorite_ids()[:4]
                   if key in self.app.registry.items]
        signature = [(action.id, action.title, self.app.registry.available(action)) for action in actions]
        if signature == self._favorite_signature:
            return
        # Preserve keyboard focus when only an action's title/state changes.
        if (self._favorite_signature is not None and
                [row[0] for row in signature] == [row[0] for row in self._favorite_signature]):
            for child, action in zip(self.fav_host.winfo_children(), actions):
                child.set_content(action.title, self.app.registry.available(action))
        else:
            for child in self.fav_host.winfo_children():
                child.destroy()
            if not actions:
                text_button(self.fav_host, '+ 添加常用操作', self.app.edit_favorites).grid(row=0, column=0, columnspan=2, sticky='ew')
            for index, action in enumerate(actions):
                chip = Chip(self.fav_host, category_icon(action.category), action.title,
                            lambda key=action.id: self._invoke(key),
                            height=38,
                            enabled=self.app.registry.available(action))
                chip.grid(row=index // 2, column=index % 2, sticky='ew',
                          padx=(0, 4) if index % 2 == 0 else (4, 0), pady=(0, 6))
        self._favorite_signature = signature

    def _refresh_reminder(self):
        if self.reminder is not None:
            self.reminder.update(*self._reminder_pair())

    def _refresh_data(self):
        day = datetime.now().date().isoformat()
        try:
            records = self.app.store.usage_records(day)
        except Exception:
            records = []
        if self.usage_mini is not None:
            self.usage_mini.update(records, sum(record.seconds for record in records))
        todos = self.app.store.get('plugin.productivity.todos', [])
        if self.todo_host is not None:
            pending = [item for item in todos if not item.get('done')][:2]
            signature = [str(item.get('title', '')) for item in pending]
            if signature != self._todo_signature:
                self._todo_signature = signature
                for child in self.todo_host.winfo_children():
                    child.destroy()
                if not pending:
                    text_button(self.todo_host, '还没有待办，添加一件小事',
                                lambda: self._open_panel('productivity')).pack(fill='x')
                for item in pending:
                    Chip(self.todo_host, '\uE739', item.get('title', ''),
                         lambda: self._open_panel('productivity'), height=36).pack(fill='x', pady=(0, 4))
        if self.summary is not None:
            minutes = self.app.store.event_sum(day, 'focus_planned_minutes')
            done = sum(1 for item in todos if item.get('done') and str(item.get('completed', '')).startswith(day))
            self.summary.update(f'今日小结  ·  计划专注 {minutes:g} 分钟  ·  完成待办 {done} 项')

    def _focus(self):
        self._invoke('productivity.focus')

    def _invoke(self, action_id):
        try:
            self.app.invoke_action(action_id)
        except Exception as exc:
            messagebox.showerror('操作未完成', str(exc), parent=self)
        if self.winfo_exists():
            self._last_data = 0
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
        self._open_panel('settings')

    def _exit(self):
        if messagebox.askyesno('退出桌宠', '确定退出小汐吗？\n退出后，专注计时和提醒将停止。', parent=self):
            self.app.close()

    def show(self):
        self.deiconify()
        self.attributes('-topmost', True)
        self.lift()
        self.after(160, self._drop_topmost)
        self.focus_force()
        self.nav_items[self.current].focus_set()
        self._last_data = 0
        self.refresh()

    def _drop_topmost(self):
        try:
            if self.winfo_exists():
                self.attributes('-topmost', False)
        except tk.TclError:
            pass

    def hide(self):
        self._drag = None
        self.withdraw()
