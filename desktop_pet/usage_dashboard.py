"""Full usage dashboard (U1): category donut and rounded application rows."""
import tkinter as tk
from datetime import datetime, timedelta

from desktop_pet.menu import (
    CARD, CAPTION, HOVER, ICON, INK, MUTED, SEP, UI_FONT, Card, icon_family,
    usage_text,
)
from desktop_pet import apps
from desktop_pet.ui import SOFT


class UsageDashboard(Card):
    WIDTH = 580
    HEIGHT = 600

    def __init__(self, app):
        super().__init__(app, self.WIDTH, inset=10, radius=14)
        self.attributes('-topmost', False)
        self.app = app
        self.period = tk.StringVar(value='今天')
        self._drag = None
        self._records = []
        self._hidden = 0
        self._build()
        x = (self.winfo_screenwidth() - self.WIDTH) // 2 + 20
        y = (self.winfo_screenheight() - self.HEIGHT) // 2 - 20
        self.finish(x, y)
        self.bind('<Escape>', lambda event: self.hide())
        self.refresh()

    def _build(self):
        self.content_canvas = tk.Canvas(self.body, width=560, height=580, bg=CARD,
                                highlightthickness=0, bd=0)
        self.content_canvas.pack(fill='both', expand=True)
        self.content_canvas.bind('<ButtonPress-1>', self._start_drag)
        self.content_canvas.bind('<B1-Motion>', self._move_drag)
        self.content_canvas.bind('<ButtonRelease-1>', self._end_drag)
        self.period_menu = tk.OptionMenu(
            self.body, self.period, '今天', '最近7天', '最近30天',
            command=lambda value: self.refresh())
        self.period_menu.configure(bg=SOFT, fg=INK, activebackground=HOVER,
                                   relief='flat', bd=0, highlightthickness=0,
                                   font=(UI_FONT, 8), cursor='hand2')
        self.period_menu.place(x=408, y=10, width=104, height=28)
        close = tk.Label(self.body, text='×', font=(UI_FONT, 16), bg=CARD,
                         fg=MUTED, cursor='hand2')
        close.place(x=534, y=8, anchor='ne')
        close.bind('<Button-1>', lambda event: self.hide())
        self.manage = tk.Label(self.body, text='管理分类 / 限时', font=(UI_FONT, 7),
                               bg=CARD, fg=MUTED, cursor='hand2')
        self.manage.place(x=536, y=560, anchor='se')
        self.manage.bind('<Button-1>', self._manage)

    def _start_drag(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _move_drag(self, event):
        if self._drag:
            self.geometry(f'+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}')

    def _end_drag(self, event=None):
        self._drag = None

    def _manage(self, event=None):
        self.hide()
        self.app.show_panel('usage')

    def _load(self):
        days = {'今天': 1, '最近7天': 7, '最近30天': 30}[self.period.get()]
        grouped = {}
        hidden = 0
        for offset in range(days):
            day = (datetime.now() - timedelta(days=offset)).date().isoformat()
            for record in self.app.store.usage_records(day, include_hidden=True):
                if record.hidden:
                    hidden += 1
                    continue
                item = grouped.setdefault(record.id, {
                    'record': record, 'seconds': 0.0,
                    'variants': 0,
                })
                item['seconds'] += record.seconds
                item['variants'] = max(item['variants'], record.variants)
        records = []
        for item in grouped.values():
            record = item['record']
            records.append(apps.UsageRecord(
                record.id, record.display, record.category, item['seconds'],
                variants=item['variants']))
        records.sort(key=lambda record: record.seconds, reverse=True)
        return records, hidden

    def refresh(self):
        self._records, self._hidden = self._load()
        self._draw()

    def _draw(self):
        c = self.content_canvas
        c.delete('all')
        records = self._records
        total = sum(record.seconds for record in records)
        days = {'今天': 1, '最近7天': 7, '最近30天': 30}[self.period.get()]
        period_label = self.period.get()
        c.create_text(24, 12, text='使用统计', anchor='nw',
                      font=(UI_FONT, 15, 'bold'), fill=INK)
        c.create_text(24, 42, text=f'{period_label} · {usage_text(total)} · '
                                   f'{len(records)} 个应用 · 已合并重复进程',
                      anchor='nw', font=(UI_FONT, 8), fill=MUTED)

        if total <= 0:
            c.create_text(280, 240, text='今天还没有应用记录', anchor='center',
                          font=(UI_FONT, 10), fill=MUTED)
        else:
            categories = apps.category_totals(records)
            order = [key for key in apps.CATEGORY_ORDER if categories.get(key)]
            self._draw_donut(100, 154, 62, 18, categories, total, order)
            self._draw_legend(196, 78, categories, total, order)
            c.create_text(24, 258, text='应用明细', anchor='nw',
                          font=(UI_FONT, 9, 'bold'), fill=INK)
            c.create_text(536, 260, text='按时长排序', anchor='ne',
                          font=(UI_FONT, 7), fill=CAPTION)
            self._draw_rows(24, 280, 512, records)
        c.create_text(24, 552, text=f'已隐藏 {self._hidden} 个系统 / 安装 / 自身项',
                      anchor='nw', font=(UI_FONT, 7), fill=CAPTION)
        c.create_text(24, 566, text='数据仅保存在本地；窗口标题不落盘',
                      anchor='nw', font=(UI_FONT, 7), fill=CAPTION)

    def _draw_donut(self, cx, cy, radius, width, categories, total, order):
        c = self.content_canvas
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        if not order:
            c.create_oval(*bbox, outline='#E3EADF', width=width)
        start = 90
        for key in order:
            value = categories[key]
            extent = -360 * value / total
            gap = 2.5
            c.create_arc(*bbox, start=start - gap, extent=extent + gap,
                         style='pieslice', fill=apps.CATEGORIES[key][1],
                         outline='')
            start += extent
        inner = radius - width
        c.create_oval(cx - inner, cy - inner, cx + inner, cy + inner,
                      fill=CARD, outline='')
        c.create_text(cx, cy - 8, text=usage_text(total), anchor='center',
                      font=(UI_FONT, 12, 'bold'), fill=INK)
        c.create_text(cx, cy + 12, text='总计', anchor='center',
                      font=(UI_FONT, 7), fill=MUTED)

    def _draw_legend(self, x, y, categories, total, order):
        c = self.content_canvas
        for index, key in enumerate(order):
            top = y + index * 30
            label, color, _ = apps.CATEGORIES[key]
            c.create_oval(x, top + 5, x + 8, top + 13, fill=color, outline='')
            c.create_text(x + 16, top, text=label, anchor='nw',
                          font=(UI_FONT, 9, 'bold'), fill=INK)
            c.create_text(x + 116, top + 1, text=usage_text(categories[key]),
                          anchor='nw', font=(UI_FONT, 8), fill=MUTED)
            pct = categories[key] / total if total else 0
            c.create_text(x + 196, top, text=f'{pct:.0%}', anchor='ne',
                          font=(UI_FONT, 8, 'bold'), fill=color)

    def _draw_rows(self, x, y, width, records):
        c = self.content_canvas
        maximum = max((record.seconds for record in records), default=1)
        for index, record in enumerate(records[:6]):
            top = y + index * 42
            color = apps.CATEGORIES[record.category][1]
            c.create_oval(x, top + 5, x + 8, top + 13, fill=color, outline='')
            c.create_text(x + 14, top, text=record.display, anchor='nw',
                          font=(UI_FONT, 9, 'bold'), fill=INK)
            if record.id == 'java':
                label = '待识别'
            elif record.variants > 1:
                label = f'合并 {record.variants} 进程'
            else:
                label = ''
            if label:
                bx = x + 14 + max(70, len(record.display) * 9) + 8
                c.create_rectangle(bx, top + 1, bx + len(label) * 7 + 8, top + 15,
                                   fill='#ECF1E7', outline='')
                c.create_text(bx + 4, top + 4, text=label, anchor='nw',
                              font=(UI_FONT, 6), fill=apps.CATEGORIES['dev'][1])
            c.create_text(x + width - 4, top, text=usage_text(record.seconds),
                          anchor='ne', font=(UI_FONT, 9, 'bold'), fill=INK)
            c.create_text(x + 14, top + 15, text=record.label, anchor='nw',
                          font=(UI_FONT, 7), fill=MUTED)
            track = [x + 100, top + 24, x + width - 10, top + 30]
            c.create_rectangle(*track, fill='#EBEFE6', outline='')
            fill_width = max(3, (width - 110) * min(1, record.seconds / maximum))
            c.create_rectangle(x + 100, top + 24, x + 100 + fill_width, top + 30,
                               fill=color, outline='')
            # rounded ends for the soft bar
            c.create_oval(x + 100, top + 24, x + 106, top + 30, fill=color, outline='')
            c.create_oval(x + 100 + fill_width - 6, top + 24,
                          x + 100 + fill_width, top + 30, fill=color, outline='')

    def show(self):
        self.deiconify()
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
