from datetime import datetime, timedelta
import os
import sys
import time
from tkinter import ttk, simpledialog, messagebox
from desktop_pet import apps, platform_win
from desktop_pet.ui import heading, table, buttons, duration


def split_interval(start, end):
    while start < end:
        midnight = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        stop = min(end, midnight)
        yield start.date().isoformat(), (stop-start).total_seconds()
        start = stop


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.last_mono = time.monotonic()
        self.last_wall = datetime.now()
        self.last_app = None
        self.continuous = 0
        self.alerted = set()
        self.last_refresh = 0
        self.frame = None
        self.current_records = []
        self.ctx.add_action('今日应用排行', lambda: ctx.app.show_usage_dashboard(), action_id='usage.today')

    def _self_pids(self):
        pids = {os.getpid()}
        live2d = getattr(self.ctx.app, 'live2d', None)
        process = getattr(live2d, 'process', None)
        pid = getattr(process, 'pid', None)
        if pid:
            pids.add(pid)
        return pids

    def _self_paths(self):
        return {sys.executable} if getattr(sys, 'frozen', False) else set()

    def _overrides(self):
        return self.ctx.get('categories', {}) or {}

    def _limits_by_id(self):
        result = {}
        for key, value in (self.ctx.get('limits', {}) or {}).items():
            entry = apps.resolve_key(key, self._overrides())
            result[entry.id] = max(result.get(entry.id, 0), value or 0)
        return result

    def tick(self, now):
        mono = time.monotonic()
        elapsed = mono - self.last_mono
        active = platform_win.unlocked() and platform_win.idle_seconds() < self.ctx.get('idle_minutes', 3) * 60
        if not self.ctx.get('enabled', True):
            active = False
        current = None
        if active:
            info = platform_win.foreground_app_info()
            if info is not None:
                entry = apps.resolve_info(
                    info, self._overrides(), self._self_pids(), self._self_paths())
                if not entry.self_process:
                    current = entry.id
            else:
                name = platform_win.foreground_app()
                if name:
                    entry = apps.resolve_key(name, self._overrides())
                    if not entry.self_process:
                        current = entry.id
        # Ignore suspend, clock changes, and idle boundaries. Polling error <= 1 second.
        if current and self.last_app and 0 < elapsed < 5 and abs((now-self.last_wall).total_seconds()-elapsed) < 2:
            for day, seconds in split_interval(self.last_wall, now):
                self.ctx.app.store.add_usage(day, self.last_app, seconds)
            self.continuous += elapsed
        else:
            self.continuous = 0
        self.last_app, self.last_wall, self.last_mono = current, now, mono
        threshold = self.ctx.get('break_minutes', 50) * 60
        if threshold > 0 and self.continuous >= threshold:
            self.continuous = 0
            self.ctx.notify('休息一下吧', '已经连续使用电脑 ' + duration(threshold) + '。', [('稍后 5 分钟', self.snooze)])
        day = now.date().isoformat()
        limits = self._limits_by_id()
        for record in self.ctx.app.store.usage_records(day, include_hidden=True):
            key = (day, record.id)
            limit = limits.get(record.id, 0)
            if limit > 0 and record.seconds >= limit * 60 and key not in self.alerted:
                self.alerted.add(key)
                self.ctx.notify('应用使用提醒', f'{record.display} 今日已使用 {duration(record.seconds)}。')
        if mono - self.last_refresh > 5:
            self.refresh()
            self.last_refresh = mono

    def snooze(self):
        timer = self.ctx.app.plugins.plugins.get('productivity')
        if timer:
            timer.add_reminder('休息一下', 5)

    def build(self, notebook):
        self.frame = ttk.Frame(notebook, padding=20)
        notebook.add(self.frame, text='应用时间')
        self.ctx.app.tabs['usage'] = self.frame
        heading(self.frame, '把时间花在哪里，一目了然', '仅统计前台应用；名称按别名和文件属性归一，java 等宿主只在内存中匹配标题，不写数据库。锁屏、休眠和空闲时暂停。')
        self.summary = ttk.Label(self.frame, font=('Microsoft YaHei UI', 12, 'bold'))
        self.summary.pack(anchor='w', pady=5)
        row = ttk.Frame(self.frame)
        row.pack(fill='x')
        self.period = ttk.Combobox(row, values=['今天', '最近7天', '最近30天'], state='readonly', width=15)
        self.period.set('今天')
        self.period.pack(side='left')
        self.period.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        self.tree = table(self.frame, ['应用', '分类', '使用时长', '每日限时'], [250, 100, 140, 120])
        buttons(self.frame, [('打开图表', self.ctx.app.show_usage_dashboard), ('设置分类', self.category), ('设置每日限时', self.limit), ('连续使用提醒', self.break_setting), ('暂停/恢复统计', self.toggle)])
        self.trend = ttk.Label(self.frame, style='Muted.TLabel', wraplength=710)
        self.trend.pack(anchor='w', pady=8)
        self.refresh()

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('选择应用', '请先在列表中选择一个应用。', parent=self.frame)
            return None
        display = self.tree.item(selection[0])['values'][0]
        for record in self.current_records:
            if record.display == display:
                return record
        return None

    def category(self):
        record = self.selected()
        if record:
            value = simpledialog.askstring(
                '应用分类', '输入分类：开发 / 浏览 / AI / 娱乐 / 系统 / 其他',
                initialvalue=record.label, parent=self.frame)
            if value:
                categories = self.ctx.get('categories', {})
                categories[record.id] = value.strip()
                categories.pop(record.display, None)
                self.ctx.set('categories', categories)
                self.refresh()

    def limit(self):
        record = self.selected()
        if record:
            minutes = simpledialog.askinteger('每日限时', '累计多少分钟提醒？0 表示关闭（提醒不会强制退出应用）', minvalue=0, maxvalue=1440, parent=self.frame)
            if minutes is not None:
                limits = self.ctx.get('limits', {})
                limits[record.id] = minutes
                limits.pop(record.display, None)
                self.ctx.set('limits', limits)
                self.alerted.discard((datetime.now().date().isoformat(), record.id))
                self.refresh()

    def break_setting(self):
        value = simpledialog.askinteger('连续使用提醒', '连续使用多少分钟后提醒？0 表示关闭', initialvalue=self.ctx.get('break_minutes', 50), minvalue=0, maxvalue=1440, parent=self.frame)
        if value is not None:
            self.ctx.set('break_minutes', value)
            self.continuous = 0

    def toggle(self):
        self.ctx.set('enabled', not self.ctx.get('enabled', True))
        self.refresh()

    def refresh(self):
        if self.frame is None or not self.frame.winfo_exists():
            return
        days = {'今天':1, '最近7天':7, '最近30天':30}[self.period.get()]
        totals = {}
        daily = []
        selected_id = self._selected_id()
        limits = self._limits_by_id()
        for offset in range(days):
            day = (datetime.now()-timedelta(days=offset)).date().isoformat()
            records = self.ctx.app.store.usage_records(day)
            daily.append(f'{day[5:]} {duration(sum(record.seconds for record in records))}')
            for record in records:
                item = totals.setdefault(record.id, {
                    'record': record, 'seconds': 0.0, 'variants': 0})
                item['seconds'] += record.seconds
                item['variants'] += record.variants
        self.tree.delete(*self.tree.get_children())
        self.current_records = []
        category_totals = {}
        for app_id, item in sorted(totals.items(), key=lambda pair: -pair[1]['seconds']):
            record = item['record']
            self.current_records.append(record)
            category_totals[record.label] = category_totals.get(record.label, 0) + item['seconds']
            limit = limits.get(app_id, 0)
            row = self.tree.insert('', 'end', values=(
                record.display, record.label, duration(item['seconds']),
                f'{limit} 分钟' if limit else '未设置'))
            if app_id == selected_id:
                self.tree.selection_set(row)
        total = sum(item['seconds'] for item in totals.values())
        self.summary.config(text=f'{self.period.get()} · {duration(total)}  |  ' +
                                ('正在统计' if self.ctx.get('enabled', True) else '已暂停'))
        categories = '  ·  '.join(
            f'{label} {seconds / total:.0%}' for label, seconds in category_totals.items()
        ) if total else '暂无记录，使用其他应用后会自动更新。'
        self.trend.config(text=categories + '\n\n每日趋势：' + '  |  '.join(reversed(daily)))

    def _selected_id(self):
        selection = self.tree.selection()
        if not selection:
            return None
        display = self.tree.item(selection[0])['values'][0]
        record = next((record for record in self.current_records
                       if record.display == display), None)
        return record.id if record else None
