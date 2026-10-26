"""Compact icon-and-text menu with stable adaptive shortcuts and complete flyouts.

Plain Tk, local usage only. The home remains the single full-feature dashboard.
"""
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path

from desktop_pet.actions import CATEGORIES
from desktop_pet.ui import UI_FONT, draw_icon, fit_text, CARD, BORDER, HOVER, ACCENT, INK, MUTED

# Backward-compatible exports used by the unchanged legacy dashboard.
ICON, SEP = "#718276", "#E8EDE3"
from desktop_pet.action_usage import recommended_actions

# Menu-only palette: do not change existing windows or saved appearance settings.
MENU_CARD, MENU_BORDER, MENU_HOVER = "#FFFCF8", "#DDD1EE", "#F0E8FA"
MENU_ACCENT, MENU_INK, MENU_MUTED = "#8866B1", "#4D3E61", "#85758F"

BASE = Path(__file__).resolve().parent.parent
CAPTION = '#68776C'
MENU_ICON = '#9275B5'
MENU_SEP = '#E8DFF0'
DANGER = '#C0566A'
DANGER_HOVER = '#FDF1F3'
PAUSE = '#C9963F'
KEY = '#FE00FE'

WIDTH = 230
INSET = 8
RADIUS = 11
SUB_WIDTH = 232

CATEGORY_ICONS = {
    'companion': 'heart', 'productivity': 'bell', 'shortcuts': 'bolt',
    'usage': 'chart', 'settings': 'settings',
}


def menu_metrics(root):
    """Fit actual font metrics, including Windows display scaling, not glyph counts."""
    font = tkfont.Font(root, family=UI_FONT, size=9)
    line = font.metrics('linespace')
    width = max(WIDTH, max(font.measure(title) for title, _ in CATEGORIES.values()) + 76)
    return min(width, max(120, root.winfo_screenwidth() - 16)), max(30, line + 12)


def clamp_position(x, y, width, height, screen_w, screen_h):
    return (max(0, min(int(x), max(0, screen_w - width - 8))),
            max(0, min(int(y), max(0, screen_h - height - 8))))


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
    def __init__(self, app, width, inset=INSET, radius=RADIUS, background=CARD, border=BORDER):
        super().__init__(app.root)
        self.app = app
        self.card_width = width
        self.inset = inset
        self.radius = radius
        self.background, self.border = background, border
        self.animation_jobs = []
        self._card_destroyed = False
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
        self.body = tk.Frame(self.canvas, bg=self.background)

    def finish(self, x, y, focus=True):
        self.body.update_idletasks()
        width = self.card_width
        height = max(56, self.body.winfo_reqheight() + 2 * self.inset)
        self.canvas.configure(width=width, height=height)
        rounded_rect(self.canvas, 0, 0, width, height, self.radius + 1, self.border)
        rounded_rect(self.canvas, 1, 1, width - 1, height - 1, self.radius, self.background)
        self.canvas.create_window(self.inset, self.inset, window=self.body, anchor='nw',
                                  width=width - 2 * self.inset, height=height - 2 * self.inset)
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = clamp_position(x, y, width, height, screen_w, screen_h)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self._set_alpha(0.0)
        self.animation_jobs.extend((
            self.after(8, lambda: self._set_alpha(0.98)),
            self.after(24, lambda: self._set_alpha(1.0))))
        if focus:
            self.focus_force()
        return height

    def destroy(self):
        if self._card_destroyed:
            return
        self._card_destroyed = True
        for job in self.animation_jobs:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self.animation_jobs.clear()
        super().destroy()

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
        super().__init__(parent, bg=MENU_CARD, height=height, takefocus=enabled, highlightthickness=0)
        self.pack_propagate(False)
        self.menu = menu
        self.category = category
        self.command = command
        self.enabled = enabled
        self.danger = danger
        self.in_submenu = in_submenu
        self._base_icon = DANGER if danger else MENU_ICON
        self._base_text = DANGER if danger else MENU_INK
        self._hover_bg = DANGER_HOVER if danger else MENU_HOVER
        self._parts = [self]
        self.icon = None
        self.icon_name = icon
        if icon:
            self.icon = tk.Canvas(self, width=22, height=22, bg=MENU_CARD, highlightthickness=0)
            draw_icon(self.icon, 2, 2, icon, size=18, color=self._base_icon)
            self.icon.pack(side='left', padx=(6, 2))
            self._parts.append(self.icon)
        else:
            spacer = tk.Frame(self, bg=MENU_CARD, width=24, height=1)
            spacer.pack(side='left')
            self._parts.append(spacer)
        self.text = tk.Label(self, text=label, font=(UI_FONT, font_size), bg=MENU_CARD,
                             fg=self._base_text, anchor='w')
        self.hint = None
        if hint:
            self.hint = tk.Label(self, text=hint, font=(UI_FONT, 7), bg=MENU_CARD, fg=MENU_MUTED)
            self.hint.pack(side='right', padx=(2, 6))
            self._parts.append(self.hint)
        self.chevron = None
        if chevron:
            self.chevron = tk.Label(self, text='›', font=(UI_FONT, 12),
                                    bg=MENU_CARD, fg='#A9B3C4')
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
        self.bind('<Return>', self._click)
        self.bind('<space>', self._click)
        self.bind('<FocusIn>', self._enter)
        self.bind('<FocusOut>', self._leave)
        if category:
            self.bind('<Right>', self._click)
        if not enabled:
            self.text.configure(fg='#B7BFCD')
            if self.icon:
                self.icon.itemconfigure('all', fill='#C2C9D6')

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
            if getattr(event, 'keysym', '') in ('Right', 'Return', 'space'):
                rows = self.menu.flyout.action_rows
                first = next((row for row in rows if row.enabled), None)
                if first is not None:
                    first.focus_set()
        elif self.command:
            self.menu.close()
            self.command()
        return 'break'

    def set_hover(self, on):
        if not self.enabled:
            return
        bg = self._hover_bg if on else MENU_CARD
        fg = (DANGER if self.danger else MENU_ACCENT) if on else self._base_text
        icon_fg = (DANGER if self.danger else MENU_ACCENT) if on else self._base_icon
        for widget in self._parts + [self.text]:
            widget.configure(bg=bg)
        self.text.configure(fg=fg)
        if self.icon:
            self.icon.delete('all')
            draw_icon(self.icon, 2, 2, self.icon_name, size=18, color=icon_fg)
        if self.chevron:
            self.chevron.configure(fg=MENU_ACCENT if on else '#A9B3C4')


class QuickButton(tk.Canvas):
    """Stable recommendation slot. Full live label is retained as a hover tooltip."""
    def __init__(self, parent, menu, action):
        self.menu, self.action = menu, action
        self.title = str(action.title)
        self.hover = False
        self.tip = None
        self.tip_job = None
        self.font = tkfont.Font(parent, family=UI_FONT, size=8)
        height = max(40, self.font.metrics('linespace') + 24)
        super().__init__(parent, bg=MENU_CARD, width=62, height=height,
                         highlightthickness=0, takefocus=True, cursor='hand2')
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<FocusIn>', self._enter)
        self.bind('<FocusOut>', self._leave)
        self.bind('<Button-1>', self._activate)
        self.bind('<Return>', self._activate)
        self.bind('<space>', self._activate)

    def _draw(self, event=None):
        self.delete('all')
        w, h = max(1, self.winfo_width()), self.winfo_height()
        rounded_rect(self, 1, 1, w - 1, h - 1, 6, MENU_HOVER if self.hover else '#F6F0FB')
        draw_icon(self, w / 2 - 7, 4, CATEGORY_ICONS.get(self.action.category, 'heart'), size=14, color=MENU_ACCENT)
        self.create_text(w / 2, h - 11, text=fit_text(self.title, self.font.measure, w - 8),
                         font=self.font, fill=MENU_INK)

    def _enter(self, event=None):
        self.hover = True
        self.menu.close_submenu()
        self._draw()
        self._cancel_tip()
        self.tip_job = self.after(450, self._show_tip)

    def _show_tip(self):
        self.tip_job = None
        if not self.winfo_exists():
            return
        self.tip = tk.Toplevel(self)
        self.tip.overrideredirect(True)
        self.tip.attributes('-topmost', True)
        tk.Label(self.tip, text=self.title, bg=MENU_CARD, fg=MENU_INK, font=(UI_FONT, 9),
                 relief='solid', borderwidth=1, padx=6, pady=3).pack()
        self.tip.update_idletasks()
        x, y = clamp_position(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height(),
                              self.tip.winfo_reqwidth(), self.tip.winfo_reqheight(),
                              self.winfo_screenwidth(), self.winfo_screenheight())
        self.tip.geometry(f'+{x}+{y}')

    def _cancel_tip(self):
        if self.tip_job is not None:
            self.after_cancel(self.tip_job)
            self.tip_job = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

    def _leave(self, event=None):
        self.hover = False
        self._cancel_tip()
        self._draw()

    def _activate(self, event=None):
        # Registry rechecks eligibility at click time. Slots never reorder while open.
        self.menu.app.invoke_action(self.action.id)
        return 'break'

    def destroy(self):
        self._cancel_tip()
        super().destroy()


class Submenu(Card):
    def __init__(self, menu, category):
        font = tkfont.Font(menu.app.root, family=UI_FONT, size=9)
        titles = [str(a.title) for a in menu.app.registry.category(category)]
        width = max(SUB_WIDTH, min(360, max((font.measure(t) for t in titles), default=0) + 48))
        super().__init__(menu.app, min(width, menu.winfo_screenwidth() - 16), inset=8, radius=10, background=MENU_CARD, border=MENU_BORDER)
        self.menu = menu
        self.category = category
        self._build()

    def _build(self):
        tk.Label(self.body, text=CATEGORIES[self.category][0], font=(UI_FONT, 9, 'bold'),
                 bg=MENU_CARD, fg=MENU_INK, anchor='w').pack(fill='x', padx=8, pady=(4, 6))
        if self.category == 'productivity':
            self._reminder_line()
        actions = self.menu.app.registry.category(self.category)
        # No six-item truncation: removing the full-page link must not orphan actions.
        viewport = tk.Frame(self.body, bg=MENU_CARD)
        viewport.pack(fill='both', expand=True)
        row_height = self.menu.row_height
        height = min(max(row_height, len(actions) * row_height),
                     max(row_height, self.winfo_screenheight() - 120))
        canvas = tk.Canvas(viewport, width=self.card_width - 38, height=height,
                           bg=MENU_CARD, bd=0, highlightthickness=0)
        scroll = tk.Scrollbar(viewport, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        if len(actions) * row_height > height:
            scroll.pack(side='right', fill='y')
        content = tk.Frame(canvas, bg=MENU_CARD)
        window = canvas.create_window(0, 0, anchor='nw', window=content)
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        self.action_rows = []
        if not actions:
            tk.Label(content, text='此分类没有可用操作', font=(UI_FONT, 9),
                     fg=MENU_MUTED, bg=MENU_CARD).pack(padx=8, pady=5)
        for action in actions:
            row = Row(content, self.menu, None, action.title,
                      command=lambda key=action.id: self.menu.app.invoke_action(key),
                      enabled=self.menu.app.registry.available(action),
                      height=row_height, font_size=9, in_submenu=True)
            row.pack(fill='x')
            self.action_rows.append(row)
            def reveal(event, target=row):
                canvas.update_idletasks()
                total = max(1, content.winfo_reqheight())
                top, bottom = target.winfo_y(), target.winfo_y() + target.winfo_height()
                visible_top = canvas.canvasy(0)
                if top < visible_top:
                    canvas.yview_moveto(top / total)
                elif bottom > visible_top + canvas.winfo_height():
                    canvas.yview_moveto((bottom - canvas.winfo_height()) / total)
            row.bind('<FocusIn>', reveal, add='+')
        def wheel(event):
            step = -1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else 1
            canvas.yview_scroll(step, 'units')
            return 'break'
        def bind_wheel(widget):
            widget.bind('<MouseWheel>', wheel)
            widget.bind('<Button-4>', wheel)
            widget.bind('<Button-5>', wheel)
            for child in widget.winfo_children():
                bind_wheel(child)
        bind_wheel(viewport)
        self.bind('<Escape>', lambda event: self.menu.close())
        self.bind('<Button-3>', lambda event: self.menu.close())
        self.bind('<Left>', lambda event: self._back())
        self.bind('<FocusOut>', self.menu._schedule_focus_check)

    def _back(self):
        self.menu.close_submenu()
        # Returning focus to the category row would immediately schedule it again.
        self.menu.focus_set()
        return 'break'

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
                 fg=MENU_MUTED, bg=MENU_CARD, anchor='w').pack(fill='x', padx=10, pady=(0, 2))

    def finish(self, x, y, focus=False):
        return super().finish(x, y, focus=False)


class ContextMenu(Card):
    def __init__(self, app, x, y):
        width, self.row_height = menu_metrics(app.root)
        super().__init__(app, width, background=MENU_CARD, border=MENU_BORDER)
        self.flyout = None
        self.submenu_job = None
        self.active_anchor = None
        self.category_rows = {}
        self.focus_job = None
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
        self.bind('<FocusOut>', self._schedule_focus_check)

    def _build(self):
        header = tk.Frame(self.body, bg=MENU_CARD)
        header.pack(fill='x', pady=(2, 4))
        avatar = tk.Canvas(header, width=36, height=36, bg=MENU_CARD, highlightthickness=0)
        avatar.pack(side='left', padx=(4, 6))
        if self.avatar_image is not None:
            avatar.create_image(18, 18, image=self.avatar_image)
        else:
            avatar.create_oval(2, 2, 34, 34, fill=MENU_HOVER, outline=MENU_BORDER)
            avatar.create_text(18, 18, text='汐', fill=MENU_ACCENT, font=(UI_FONT, 10, 'bold'))
        info = tk.Frame(header, bg=MENU_CARD)
        info.pack(side='left')
        tk.Label(info, text='小汐', font=(UI_FONT, 10, 'bold'), fg=MENU_INK,
                 bg=MENU_CARD, anchor='w').pack(anchor='w')
        tk.Label(info, text=self._status_line(), font=(UI_FONT, 7), fg=MENU_MUTED,
                 bg=MENU_CARD, anchor='w').pack(anchor='w')
        home = tk.Button(header, text='小屋', font=(UI_FONT, 9), fg=MENU_ACCENT,
                         bg=MENU_HOVER, activebackground=MENU_BORDER, relief='flat', bd=0,
                         padx=6, pady=4, command=self._open_home, cursor='hand2')
        home.pack(side='right', padx=4)
        self.quick_actions = tuple(recommended_actions(self.app.registry, self.app.store))
        quick = tk.Frame(self.body, bg=MENU_CARD)
        quick.pack(fill='x', pady=(0, 5), padx=2)
        self.quick_buttons = []
        for index, action in enumerate(self.quick_actions):
            quick.columnconfigure(index, weight=1, uniform='quick')
            button = QuickButton(quick, self, action)
            button.grid(row=0, column=index, sticky='ew', padx=2)
            self.quick_buttons.append(button)
        tk.Frame(self.body, bg=MENU_SEP, height=1).pack(fill='x', padx=5, pady=(1, 4))
        for category, (title, _) in CATEGORIES.items():
            row = Row(self.body, self, CATEGORY_ICONS[category], title, chevron=True,
                      category=category, height=self.row_height)
            row.pack(fill='x', padx=2)
            self.category_rows[category] = row
        tk.Frame(self.body, bg=MENU_SEP, height=1).pack(fill='x', padx=5, pady=4)
        bottom = tk.Frame(self.body, bg=MENU_CARD)
        bottom.pack(fill='x', pady=(0, 2))
        Row(bottom, self, 'circle', '显示' if self.app.pet_hidden else '隐藏',
            command=self.app.toggle_pet_visibility, height=self.row_height).pack(side='left', fill='x', expand=True)
        Row(bottom, self, 'circle', '退出', command=self.app.close,
            danger=True, height=self.row_height).pack(side='right', fill='x', expand=True)

    def _open_home(self):
        self.close()
        self.app.show_hub()

    def _status_line(self):
        try:
            if self.app.store.get('dnd', False):
                return '免打扰'
            if getattr(self.app, 'focused', False):
                return '专注模式'
        except Exception:
            pass
        return '在这里陪你'

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
        y = anchor.winfo_rooty() - 6
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

    def _schedule_focus_check(self, event=None):
        if getattr(self, '_closing', False):
            return
        if self.focus_job is not None:
            self.after_cancel(self.focus_job)
        self.focus_job = self.after(120, self._check_focus)

    def _check_focus(self):
        self.focus_job = None
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
        if getattr(self, '_closing', False):
            return
        self._closing = True
        if self.focus_job is not None:
            self.after_cancel(self.focus_job)
            self.focus_job = None
        self._cancel_submenu_job()
        flyout, self.flyout = self.flyout, None
        if flyout is not None:
            try:
                flyout.destroy()
            except tk.TclError:
                pass
        super().destroy()
