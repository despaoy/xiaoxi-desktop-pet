"""Data-driven sprite player and local dialogue. No model or speech API."""
import json
import random
import time
from pathlib import Path
import tkinter as tk


class FrameClock:
    """Deadline scheduling avoids adding render time to every frame interval."""
    def __init__(self, fps=60, clock=time.monotonic):
        self.clock=clock
        self.interval=1/fps
        self.deadline=clock()

    def delay(self):
        now=self.clock()
        self.deadline+=self.interval
        if self.deadline<=now:
            self.deadline+=(int((now-self.deadline)/self.interval)+1)*self.interval
        return max(1,round((self.deadline-now)*1000))


class Dialogue:
    def __init__(self, path, clock=time.monotonic):
        self.path = Path(path)
        self.clock = clock
        self.last_time = float('-inf')
        self.last_lines = {}
        self.reload()

    def reload(self):
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data.get('events'), dict):
            raise ValueError('语言包缺少 events')
        for event, entry in data['events'].items():
            lines = entry.get('lines', [])
            if not lines or not all(isinstance(x,str) and x.strip() for x in lines):
                raise ValueError(f'语言包 {event} 的台词不能为空')
        self.data = data

    def choose(self, event, force=False):
        entry = self.data['events'].get(event)
        if not entry:
            return None
        now = self.clock()
        cooldown = self.data.get('policy', {}).get('cooldown_seconds',20)
        if not force and now - self.last_time < cooldown:
            return None
        lines = entry['lines']
        candidates = [x for x in lines if x != self.last_lines.get(event)] or lines
        line = random.choice(candidates)
        self.last_lines[event] = line
        self.last_time = now
        return line


class Timeline:
    def __init__(self, actions, clock=time.monotonic):
        self.actions = actions
        self.clock = clock
        self.state = 'idle'
        self.started = clock()
        for name, action in actions.items():
            if len(action['frames']) != len(action['durations_ms']) or not action['frames']:
                raise ValueError(f'{name}: 帧与时长不匹配')
            if any(t <= 0 for t in action['durations_ms']):
                raise ValueError(f'{name}: 帧时长必须大于零')

    def play(self, action):
        if action not in self.actions:
            return False
        self.state = action
        self.started = self.clock()
        return True

    def frame(self):
        item = self.actions[self.state]
        elapsed = (self.clock()-self.started)*1000
        duration = sum(item['durations_ms'])
        if elapsed >= duration:
            if item.get('loop'):
                elapsed %= duration
            else:
                self.play('idle')
                item = self.actions['idle']
                elapsed = 0
        for frame, ms in zip(item['frames'], item['durations_ms']):
            if elapsed < ms:
                return frame
            elapsed -= ms
        return item['frames'][-1]


class SpritePlayer:
    def __init__(self, root, path):
        self.path = Path(path)
        self.config = json.loads(self.path.read_text(encoding='utf-8'))
        self.timeline = Timeline(self.config['actions'])
        atlas = (self.path.parent/self.config['atlas']).resolve()
        if not atlas.is_relative_to(self.path.parent.resolve()):
            raise ValueError('角色素材必须位于角色包目录')
        self.source = tk.PhotoImage(master=root,file=str(atlas))
        self.frames = []
        columns, rows = self.config['columns'], self.config['rows']
        self.width = self.source.width()//columns
        self.height = self.source.height()//rows
        for row in range(rows):
            for col in range(columns):
                # Decode atlas cells at display time; source RGBA remains unmodified.
                x0 = round(col*self.source.width()/columns)
                y0 = round(row*self.source.height()/rows)
                x1 = round((col+1)*self.source.width()/columns)
                y1 = round((row+1)*self.source.height()/rows)
                frame = tk.PhotoImage(master=root,width=self.width+1,height=self.height+1)
                root.tk.call(str(frame),'copy',str(self.source),'-from',x0,y0,x1,y1,'-to',0,0)
                self.frames.append(frame)
        for action in self.config['actions'].values():
            if any(i < 0 or i >= len(self.frames) for i in action['frames']):
                raise ValueError('动作帧超出素材范围')

    def play(self, action):
        return self.timeline.play(action)

    def image(self, focused=False):
        index = self.timeline.frame()
        if focused and self.timeline.state == 'idle':
            index = 0
        return self.frames[index]
