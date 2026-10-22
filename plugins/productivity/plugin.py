from datetime import datetime, timedelta
import re
import uuid
from tkinter import ttk, simpledialog, messagebox
from desktop_pet.ui import heading, table, buttons, duration


def number(text):
    if text.isdigit():
        return int(text)
    digits = {'零':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    if text == '半':
        return 0.5
    if text in digits:
        return digits[text]
    if '十' in text:
        a,b = text.split('十', 1)
        return digits.get(a,1)*10 + digits.get(b,0)
    raise ValueError('时长请使用数字，例如 30 分钟')


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None
        self.ctx.add_action(self.focus_label, self.focus_action, action_id='productivity.focus')
        self.ctx.add_action('结束计时', self.stop_focus, action_id='productivity.stop', enabled=lambda:bool(ctx.get('timer')))
        self.ctx.add_action('添加提醒', self.reminder_dialog, action_id='productivity.reminder')
        self.ctx.add_action('添加待办', self.todo_dialog, action_id='productivity.todo')
        # Old timer survives a restart; expired timers report once when next tick runs.

    def build(self, notebook):
        self.frame = ttk.Frame(notebook, padding=20)
        notebook.add(self.frame, text='专注与提醒')
        self.ctx.app.tabs['productivity'] = self.frame
        heading(self.frame, '今天，按自己的节奏来', '提醒在程序运行时触发；关机期间不会唤醒电脑，重新打开后会提示到期事项。')
        self.timer_label = ttk.Label(self.frame, font=('Microsoft YaHei UI', 16, 'bold'))
        self.timer_label.pack(anchor='w', pady=4)
        row = buttons(self.frame, [('开始 25 分钟专注', self.focus_action), ('自定时长', self.start_dialog), ('结束计时', self.stop_focus), ('专注模式 开/关', self.toggle_focus)])
        self.focus_button = row.winfo_children()[0]
        self.tree = table(self.frame, ['事项', '类型', '状态 / 下次提醒'], [260, 90, 270])
        buttons(self.frame, [('添加待办', self.todo_dialog), ('完成 / 恢复', self.toggle_todo), ('添加提醒', self.reminder_dialog), ('删除', self.delete), ('今日小结', self.summary)])
        self.refresh()

    def add_reminder(self, title, minutes, interval=0):
        if minutes <= 0 or minutes > 525600:
            raise ValueError('时长须在 0 到 525600 分钟之间')
        rows = self.ctx.get('reminders', [])
        rows.append({'id':uuid.uuid4().hex, 'title':title, 'due':(datetime.now()+timedelta(minutes=minutes)).isoformat(), 'interval':interval, 'done':False})
        self.ctx.set('reminders', rows)
        self.refresh()

    def add_at(self, title, hour, minute):
        now = datetime.now()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
        self.add_reminder(title, (due-now).total_seconds()/60)
        return due.strftime('%m月%d日 %H:%M')

    def add_todo(self, title):
        rows = self.ctx.get('todos', [])
        rows.append({'id':uuid.uuid4().hex, 'title':title, 'done':False, 'completed':None})
        self.ctx.set('todos', rows)
        self.refresh()

    def start_focus(self, minutes):
        if minutes < 1 or minutes > 240:
            raise ValueError('专注时长应为 1–240 分钟')
        if self.ctx.get('timer'):
            raise ValueError('已有计时在运行，请先结束当前计时')
        self.ctx.set('timer', {'kind':'专注', 'start':datetime.now().isoformat(), 'due':(datetime.now()+timedelta(minutes=minutes)).isoformat(), 'minutes':minutes})
        self.ctx.app.focused = True
        self.ctx.app.store.set('focused', True)
        self.ctx.notify('专注开始', f'接下来的 {minutes:g} 分钟，一起专心做好一件事。')
        self.refresh()

    def focus_label(self):
        timer = self.ctx.get('timer')
        if not timer:
            return '开始 25 分钟专注'
        return ('继续' if timer.get('paused') else '暂停') + timer['kind']

    def focus_action(self):
        if not self.ctx.get('timer'):
            return self.start_focus(25)
        return self.toggle_pause()

    def toggle_pause(self):
        timer = self.ctx.get('timer')
        if not timer:
            raise ValueError('当前没有计时')
        if timer.get('paused'):
            timer['due'] = (datetime.now()+timedelta(seconds=timer['remaining'])).isoformat()
            timer['paused'] = False
        else:
            timer['remaining'] = max(0, (datetime.fromisoformat(timer['due'])-datetime.now()).total_seconds())
            timer['paused'] = True
        self.ctx.set('timer', timer)
        self.ctx.app.focused = timer['kind']=='专注' and not timer['paused']
        self.ctx.app.store.set('focused', self.ctx.app.focused)
        self.refresh()

    def start_dialog(self):
        minutes = simpledialog.askinteger('专注计时', '专注多少分钟？', initialvalue=25, minvalue=1, maxvalue=240, parent=self.frame)
        if minutes:
            try:
                self.start_focus(minutes)
            except ValueError as exc:
                messagebox.showinfo('专注计时', str(exc), parent=self.frame)

    def stop_focus(self):
        self.ctx.set('timer', None)
        self.ctx.app.focused = False
        self.ctx.app.store.set('focused', False)
        self.refresh()

    def start_break(self):
        self.ctx.set('timer', {'kind':'休息', 'due':(datetime.now()+timedelta(minutes=5)).isoformat(), 'minutes':5})

    def toggle_focus(self):
        self.ctx.app.focused = not self.ctx.app.focused
        self.ctx.app.store.set('focused', self.ctx.app.focused)
        self.refresh()

    def tick(self, now):
        timer = self.ctx.get('timer')
        if timer and not timer.get('paused') and now >= datetime.fromisoformat(timer['due']):
            self.ctx.set('timer', None)
            self.ctx.app.focused = False
            self.ctx.app.store.set('focused', False)
            if timer['kind'] == '专注':
                # Record on scheduled completion date even if app was closed overnight.
                self.ctx.app.store.event(timer['due'], 'focus_planned_minutes', timer['minutes'])
                self.ctx.notify('专注计时结束', '做得不错，休息五分钟吧。计时完成不代表期间一直在电脑前。', [('休息 5 分钟', self.start_break)])
            else:
                self.ctx.notify('休息结束', '准备好开始下一轮了吗？', [('再专注 25 分钟', lambda:self.start_focus(25))])
        rows = self.ctx.get('reminders', [])
        changed = False
        for item in rows:
            if not item['done'] and now >= datetime.fromisoformat(item['due']):
                title = item['title']
                self.ctx.notify('到时间了', title, [('稍后 5 分钟', lambda t=title:self.add_reminder(t,5)), ('知道了', lambda:None)])
                if item['interval']:
                    item['due'] = (now+timedelta(minutes=item['interval'])).isoformat()
                else:
                    item['done'] = True
                changed = True
        if changed:
            self.ctx.set('reminders', rows)
            self.refresh()
        if self.frame is not None and self.frame.winfo_exists():
            timer = self.ctx.get('timer')
            seconds = timer.get('remaining',0) if timer and timer.get('paused') else max(0,(datetime.fromisoformat(timer['due'])-now).total_seconds()) if timer else 0
            text = f"{timer['kind']} · {duration(seconds)}" + (' · 已暂停' if timer.get('paused') else '') if timer else '没有正在运行的计时'
            self.timer_label.config(text=text + ('  · 专注模式' if self.ctx.app.focused else ''))
            self.focus_button.config(text=self.focus_label())

    def todo_dialog(self):
        title = simpledialog.askstring('添加待办', '需要做什么？', parent=self.frame)
        if title and title.strip():
            self.add_todo(title.strip())

    def reminder_dialog(self):
        title = simpledialog.askstring('添加提醒', '提醒内容', parent=self.frame)
        if not title:
            return
        minutes = simpledialog.askinteger('提醒时间', '多少分钟后提醒？', minvalue=1, maxvalue=525600, parent=self.frame)
        if minutes:
            repeat = messagebox.askyesno('重复提醒', f'是否每 {minutes} 分钟重复？\n选择“否”则只提醒一次。', parent=self.frame)
            self.add_reminder(title, minutes, minutes if repeat else 0)

    def toggle_todo(self):
        selection = self.tree.selection()
        if not selection:
            return
        rows = self.ctx.get('todos', [])
        for item in rows:
            if item['id'] == selection[0]:
                item['done'] = not item['done']
                item['completed'] = datetime.now().isoformat() if item['done'] else None
                if item['done']:
                    self.ctx.emit('success')
        self.ctx.set('todos', rows)
        self.refresh()

    def delete(self):
        selection = self.tree.selection()
        if selection and messagebox.askyesno('删除事项', '确定删除选中的待办或提醒？', parent=self.frame):
            for key in ('todos', 'reminders'):
                self.ctx.set(key, [x for x in self.ctx.get(key, []) if x['id'] != selection[0]])
            self.refresh()

    def summary(self):
        day = datetime.now().date().isoformat()
        records = self.ctx.app.store.usage_records(day)
        done = sum(1 for x in self.ctx.get('todos', []) if x.get('completed','') and x['completed'].startswith(day))
        minutes = self.ctx.app.store.event_sum(day, 'focus_planned_minutes')
        messagebox.showinfo('今日小结', f'前台应用使用：{duration(sum(r.seconds for r in records))}\n完成的专注计时：{minutes:g} 分钟\n今日已完成待办：{done} 项\n\n最常用应用：\n' + ('\n'.join(f'{r.display}  {duration(r.seconds)}' for r in records[:5]) or '暂无记录') + '\n\n专注计时为计划时长，非实际专注行为测量。', parent=self.frame)

    def refresh(self):
        if self.frame is None or not self.frame.winfo_exists():
            return
        self.focus_button.config(text=self.focus_label())
        self.tree.delete(*self.tree.get_children())
        for item in self.ctx.get('todos', []):
            self.tree.insert('', 'end', iid=item['id'], values=(item['title'], '待办', '已完成' if item['done'] else '待完成'))
        for item in self.ctx.get('reminders', []):
            state = '已提醒' if item['done'] else datetime.fromisoformat(item['due']).strftime('%m-%d %H:%M')
            if item['interval']:
                state += f" / 每{item['interval']:g}分钟"
            self.tree.insert('', 'end', iid=item['id'], values=(item['title'], '提醒', state))

    def command(self, text):
        if text in ('暂停专注', '继续专注', '暂停计时', '继续计时'):
            timer = self.ctx.get('timer')
            if not timer:
                return '未完成：当前没有计时。'
            if timer.get('paused',False) != text.startswith('暂停'):
                self.toggle_pause()
            return '计时已暂停。' if text.startswith('暂停') else '计时已继续。'
        if text in ('结束计时', '结束专注'):
            self.stop_focus()
            return '已结束计时。'
        match = re.fullmatch(r'添加待办\s*[:：]?\s*(.+)', text)
        if match:
            self.add_todo(match[1])
            return '已添加待办：' + match[1]
        match = re.fullmatch(r'(每|)([\d一二两三四五六七八九十半]+)?\s*(分钟|小时)(?:后)?提醒我\s*(.+)', text)
        if match:
            n = number(match[2] or '1') * (60 if match[3] == '小时' else 1)
            self.add_reminder(match[4], n, n if match[1] else 0)
            return f'已设置：{("每" if match[1] else "在")}{n:g} 分钟{("" if match[1] else "后")}提醒你{match[4]}。'
        match = re.fullmatch(r'(?:今天|明天)?\s*(\d{1,2})[:：](\d{2})提醒我\s*(.+)', text)
        if match and not text.startswith('明天'):
            due = self.add_at(match[3], int(match[1]), int(match[2]))
            return f'已设置 {due} 提醒：{match[3]}'
        match = re.fullmatch(r'(?:开始)?\s*(\d+)\s*分钟专注', text)
        if match:
            self.start_focus(int(match[1]))
            return f'已开始 {match[1]} 分钟专注。'
        if text in ('开启专注模式', '关闭专注模式'):
            self.ctx.app.focused = text.startswith('开启')
            self.ctx.app.store.set('focused', self.ctx.app.focused)
            return '已' + text[:2] + '专注模式。'
