"""Single persisted timer state machine, independent of plugin and GUI.

Existing timer JSON remains readable. A persisted revision invalidates actions
from older completion notifications, including across a stop or restart.
"""
from datetime import datetime, timedelta
import math


class TimerService:
    KEY = 'plugin.productivity.timer'
    REVISION = 'plugin.productivity.timer_revision'

    def __init__(self, store, set_focused, clock=datetime.now):
        self.store, self.set_focused, self.clock = store, set_focused, clock

    @property
    def current(self):
        return self.store.get(self.KEY)

    @property
    def revision(self):
        return self.store.get(self.REVISION, 0)

    def _write(self, timer, events=()):
        focused = bool(timer and timer['kind'] == '专注' and not timer.get('paused'))
        self.store.write_batch({self.REVISION: self.revision + 1,
                                self.KEY: timer, 'focused': focused}, events)
        # Synchronize legacy hosts only after the durable transition succeeds.
        self.set_focused(focused)

    def start(self, minutes, kind='专注', expected_revision=None):
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not 1 <= minutes <= 240:
            raise ValueError('专注时长应为 1–240 分钟')
        if self.current:
            raise ValueError('已有计时在运行，请先结束当前计时')
        if expected_revision is not None and expected_revision != self.revision:
            raise ValueError('这条计时提醒已过期，请从小屋开始新的计时')
        now = self.clock()
        timer = {'kind': kind, 'start': now.isoformat(),
                 'due': (now + timedelta(minutes=minutes)).isoformat(), 'minutes': minutes}
        self._write(timer)
        return timer

    def toggle_pause(self):
        timer = self.current
        if not timer:
            raise ValueError('当前没有计时')
        now = self.clock()
        if timer.get('paused'):
            timer['due'] = (now + timedelta(seconds=timer['remaining'])).isoformat()
            timer['paused'] = False
        else:
            timer['remaining'] = max(0, (datetime.fromisoformat(timer['due']) - now).total_seconds())
            timer['paused'] = True
        self._write(timer)
        return timer

    def stop(self):
        self._write(None)

    def complete_due(self, now=None):
        timer = self.current
        if not timer or timer.get('paused') or (now or self.clock()) < datetime.fromisoformat(timer['due']):
            return None
        events = [(timer['due'], 'focus_planned_minutes', timer['minutes'])] if timer['kind'] == '专注' else []
        self._write(None, events)
        return timer, self.revision
