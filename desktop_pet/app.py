import argparse
from collections import deque
from datetime import datetime
import logging
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from desktop_pet.storage import Store
from desktop_pet.plugin_api import PluginManager
from desktop_pet import platform_win
from desktop_pet.ui import style, heading, table, buttons, PetArt, safe, BG
from desktop_pet.companion import Dialogue, FrameClock
from desktop_pet.live2d_host import Live2DHost
from desktop_pet.actions import ActionRegistry, CATEGORIES
from desktop_pet.navigation import Navigation

BASE = Path(__file__).resolve().parent.parent
if getattr(sys, 'frozen', False):
    BASE = Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    APP_HOME = Path(sys.executable).resolve().parent
else:
    APP_HOME = BASE
DATA_HOME = APP_HOME / 'data'


class App(Navigation):
    def __init__(self, data_dir=None, smoke=False, live2d=False,
                 live2d_no_sandbox=False, background=False):
        self.live2d = None
        self.store = Store(data_dir or DATA_HOME)
        self.smoke = smoke
        self.root = tk.Tk()
        self.root.title('小汐桌宠')
        try:
            icon = BASE / 'assets/ui/app-icon.ico'
            if icon.exists():
                self.root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
        self.root.withdraw()
        style(self.root)
        self.focused = self.store.get('focused', False)
        self.actions, self.tabs = [], {}
        self.registry = ActionRegistry(lambda owner: owner in self.plugins.plugins)
        self.init_navigation()
        self.background = bool(background and not smoke)
        if self.background:
            self.pet_hidden = True
        self.tray = None
        self.show_event = None
        self.show_thread = None
        self.show_stop = threading.Event()
        self.show_requests = queue.Queue()
        self.panel = None
        self.bubble = None
        self.queue = deque()
        self.history = self.store.get('notification_history', [])
        self.hotkey = platform_win.Hotkey(self.store.get('navigation.favorite_hotkeys', False)) if not smoke else None
        self.plugins = PluginManager(self, BASE / 'plugins')
        self.plugins.load()
        self.sprite = None
        self.live2d_mode = bool(live2d and not smoke)
        self.live2d_no_sandbox = bool(live2d_no_sandbox)
        try:
            self.live2d_scale = min(1.25, max(0.5, float(self.store.get('live2d.scale', 0.8))))
        except (TypeError, ValueError):
            self.live2d_scale = 0.8
        self.live2d_failure = None
        self.live2d_stage = '未启动'
        language = self.store.directory/'language-zh-CN.json'
        if not language.exists():
            language = BASE/'assets/language/zh-CN.json'
        try:
            self.dialogue = Dialogue(language)
        except Exception:
            logging.exception('Invalid custom language; using defaults')
            self.dialogue = Dialogue(BASE/'assets/language/zh-CN.json')
        if not self.live2d_mode and 'companion' in self.plugins.plugins:
            try:
                from desktop_pet.smooth_motion import SmoothPlayer
            except ImportError as exc:
                raise RuntimeError('图片形象依赖缺失：请确认 .runtime 与 requirements-motion.txt；'
                                   '如需 Live2D，请使用“启动Live2D桌宠.cmd”。') from exc
            self.sprite = SmoothPlayer(self.root,BASE/'assets/characters/silver-dragon/character.json')
        if self.live2d_mode:
            self.pet_width, self.pet_height = self.live2d_size()
        elif self.sprite:
            self.pet_width, self.pet_height = 330, 345
        else:
            self.pet_width, self.pet_height = 180, 202
        self.tick_count = 0
        self.dragging = False
        self.pet = tk.Toplevel(self.root)
        self.pet.title('小汐 · 桌面伙伴')
        self.pet.overrideredirect(True)
        self.pet.attributes('-topmost', True)
        self.transparent = '#F4F6FB'
        self.pet.configure(bg=self.transparent)
        if platform_win.IS_WINDOWS:
            self.pet.attributes('-transparentcolor', self.transparent)
        self.canvas = tk.Canvas(self.pet, width=self.pet_width, height=self.pet_height, bg=self.transparent, highlightthickness=0)
        self.canvas.pack()
        self.art = PetArt(self.canvas)
        self.custom_image = None
        self.load_skin()
        x, y = self.store.get('pet_position', [self.root.winfo_screenwidth()-240, self.root.winfo_screenheight()-300])
        if self.live2d_mode and not self.store.get('live2d.tight_window', False):
            # Old renderer window was 330x345 with transparent margins. Keep the
            # visible character's bottom centre when switching to a tight window.
            old_scale = min((330 - 18) / 1086.0, (345 - 20) / 1448.0) * self.live2d_scale
            old_center = 330 / 2 + (557 - 543) * old_scale
            old_bottom = 341 - 38 * old_scale
            x += round(old_center - self.pet_width / 2)
            y += round(old_bottom - self.pet_height)
            self.store.set('live2d.tight_window', True)
        self.move_pet(x,y)
        if self.live2d_mode:
            # Live2D is the only appearance; keep the Tk pet hidden instead of
            # letting the old image canvas act as a visible fallback.
            self.pet.withdraw()
            self.start_live2d()
        elif self.background:
            self.pet.withdraw()
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.menu)
        self.canvas.bind('<Enter>', self.hover)
        self.canvas.bind('<Leave>', self.leave)
        self.tooltip = None
        self.hover_job = None
        if not self.live2d_mode:
            self.animate()
        if not smoke:
            self.root.after(1000, self.tick)
            self.root.after(100, self.poll_hotkey)
            self.root.after(1500,lambda:self.react('greeting'))
        self.start_show_listener()
        self.start_tray()
        if not self.store.get('welcomed', False):
            if not self.background:
                self.show_hub()
            self.store.set('welcomed', True)

    def resource(self, relative):
        return BASE / relative

    def start_show_listener(self):
        if self.smoke:
            return
        self.show_event = platform_win.create_show_event()
        if not self.show_event:
            logging.warning('Show event unavailable; second launch cannot reveal the app')
            return
        self.show_thread = threading.Thread(
            target=platform_win.wait_show_event,
            args=(self.show_event, self.show_stop,
                  lambda: self.show_requests.put(True)),
            daemon=True)
        self.show_thread.start()
        self.root.after(250, self.poll_show_requests)

    def poll_show_requests(self):
        requested = False
        while True:
            try:
                self.show_requests.get_nowait()
                requested = True
            except queue.Empty:
                break
        if requested and self.root.winfo_exists():
            logging.info('Show requested by a second launch')
            self.set_pet_hidden(False)
            self.show_hub()
        try:
            self.root.after(250, self.poll_show_requests)
        except Exception:
            pass

    def start_tray(self):
        if self.smoke:
            return
        try:
            from desktop_pet.tray import Tray
            self.tray = Tray(self)
            self.root.after(250, self.tray.poll)
            if self.background:
                self.root.after(1800, lambda: self.tray and self.tray.notify(
                    '小汐在后台运行；双击桌面快捷方式即可显示角色和小屋。'))
        except Exception:
            logging.exception('Tray unavailable')
            self.tray = None

    def load_skin(self):
        path = self.store.get('skin_path')
        if path:
            try:
                image = tk.PhotoImage(file=path)
                factor = max(1, (max(image.width(),image.height()) + 179)//180)
                self.custom_image = image.subsample(factor)
            except Exception:
                logging.exception('Skin load failed; using original')
                self.custom_image = None

    def live2d_size(self):
        scale = (325.0 / 1448.0) * self.live2d_scale
        return max(80, round(1014 * scale)), max(80, round(1387 * scale))

    def move_pet(self, x,y):
        x = max(0, min(int(x), self.root.winfo_screenwidth()-self.pet_width))
        y = max(0, min(int(y), self.root.winfo_screenheight()-self.pet_height))
        self.pet_x, self.pet_y = x, y
        self.pet.geometry(f'{self.pet_width}x{self.pet_height}+{x}+{y}')

    def visual_top(self):
        return self.pet_y

    def press(self, event):
        self.origin = (event.x_root,event.y_root,self.pet_x,self.pet_y)
        self.dragging = False
        self.leave()

    def drag(self, event):
        ox,oy,x,y = self.origin
        if abs(event.x_root-ox)+abs(event.y_root-oy)>5:
            self.dragging = True
            self.cancel_pet_click()
            self.move_pet(x+event.x_root-ox,y+event.y_root-oy)

    def release(self, event):
        if self.dragging:
            self.store.set('pet_position', [self.pet_x,self.pet_y])
            self.react('drag')
        else:
            self.pet_click()

    def animate(self):
        if not hasattr(self,'animation_clock'):
            self.animation_clock=FrameClock()
        self.tick_count += 1
        if self.custom_image:
            self.canvas.delete('all')
            self.canvas.create_image(90,90,image=self.custom_image)
            self.canvas.create_text(90,190,text='小汐 · 点击打开',fill='#60708E',font=('Microsoft YaHei UI',9))
        elif self.sprite:
            self.canvas.delete('all')
            self.canvas.create_image(self.pet_width//2,160,image=self.sprite.image(self.focused))
            self.canvas.create_text(self.pet_width//2,self.pet_height-13,text='小汐 · 专注陪伴' if self.focused else '小汐 · 点击打开',fill='#60708E',font=('Microsoft YaHei UI',9))
        else:
            self.art.draw(8 if self.focused else self.tick_count, self.focused, self.store.get('accent','#778EE3'))
        self.root.after(self.animation_clock.delay(), self.animate)

    def start_live2d(self):
        """Start the renderer; never substitute the old Tk sprite on failure."""
        self.close_live2d_failure()
        self.live2d_stage = '启动渲染进程'
        try:
            self.live2d = Live2DHost((self.pet_x, self.pet_y),
                                     disable_sandbox=self.live2d_no_sandbox,
                                     size=(self.pet_width, self.pet_height),
                                     visible=not self.pet_hidden)
        except Exception as exc:
            self.live2d = None
            self.live2d_failed(self.live2d_stage, f'{type(exc).__name__}: {exc}',
                               traceback.format_exc())
            return
        if self.live2d_no_sandbox:
            logging.warning('Live2D compatibility mode: Chromium sandbox disabled '
                            '(local pages only)')
        logging.info('Live2D renderer starting: pid=%s position=%s,%s',
                     self.live2d.process.pid, self.pet_x, self.pet_y)
        self.root.after(100, self.poll_live2d)

    def poll_live2d(self):
        from types import SimpleNamespace
        host = self.live2d
        if host is None:
            return
        for event in host.events():
            name = event.get('event')
            if 'x' in event and 'y' in event:
                # Hidden Tk pet remains the anchor for existing plugin bubbles.
                self.pet_x, self.pet_y = int(event['x']), int(event['y'])
                self.pet.geometry(f'+{self.pet_x}+{self.pet_y}')
            if name == 'loading':
                self.live2d_stage = event.get('stage', '加载中')
                logging.info('Live2D stage: %s', self.live2d_stage)
            elif name == 'loaded':
                if not event.get('ok'):
                    self.live2d_failed('页面加载',
                        'QWebEngine 页面加载失败（loadFinished=false）。渲染端无法启动，'
                        '请确认 review/live2d 资源完整，并查看日志。')
                    return
                logging.info('Live2D page loaded')
            elif name == 'console':
                text = f"{event.get('message', '')} ({event.get('source', '')}:{event.get('line', '?')})"
                if event.get('level') == 2:
                    logging.error('Live2D console error: %s', text)
                elif event.get('level') == 1:
                    logging.warning('Live2D console warning: %s', text)
            elif name == 'ready':
                host.ready = True
                self.live2d_stage = '运行中'
                self.pet.withdraw()
                self.close_live2d_failure()
                logging.info('Live2D ready: model V%s, renderer PID %s, scale %.2f',
                             event.get('modelVersion', '?'), host.process.pid, self.live2d_scale)
            elif name == 'click':
                self.pet_click()
            elif name == 'action_started':
                plugin = self.plugins.plugins.get('companion')
                if plugin and hasattr(plugin, 'playback_started'):
                    plugin.playback_started(event['action'])
            elif name == 'menu':
                self.menu(SimpleNamespace(x_root=self.root.winfo_pointerx(),
                                          y_root=self.root.winfo_pointery()))
            elif name == 'hover':
                self.hover(None)
            elif name == 'leave':
                self.leave()
            elif name == 'moved':
                self.cancel_pet_click()
                self.store.set('pet_position', [self.pet_x, self.pet_y])
            elif name == 'error':
                detail = event.get('traceback') or event.get('message') or '未知错误'
                logging.error('Live2D renderer error:\n%s', detail)
                self.live2d_failed(event.get('stage') or self.live2d_stage,
                                   event.get('message') or '渲染端报告错误', detail)
                return
        if not host.ready and time.monotonic() - host.started > 45:
            self.live2d_failed(self.live2d_stage,
                f'渲染进程 45 秒内未就绪（最后阶段：{self.live2d_stage}）。'
                '常见原因是 Qt WebEngine 初始化失败、模型文件缺失或 WebChannel 连接失败。')
            return
        if not host.process.is_alive():
            code = host.process.exitcode
            self.live2d_failed('渲染进程退出',
                f'渲染进程已退出（exit code {code if code is not None else "未知"}），形象无法显示。')
            return
        host.state(**self.live2d_context())
        self.root.after(100, self.poll_live2d)

    def live2d_context(self):
        # Only whether our own input has focus is shared, never typed content.
        try:
            widget = self.root.focus_get()
            editing = bool(widget and widget.winfo_class() in
                           ('Entry', 'TEntry', 'Text', 'TCombobox', 'Spinbox', 'TSpinbox'))
        except (tk.TclError, KeyError):
            editing = False
        return dict(focused=self.focused, preferences=self.store.get('pet.behavior', {}),
                    scale=self.live2d_scale, visible=not self.pet_hidden,
                    dnd=self.store.get('dnd', False),
                    speechEnabled=self.store.get('companion.speech', True),
                    notificationBusy=bool(self.bubble or self.queue), editing=editing,
                    actionLines=self.dialogue.data.get('actions', {}))

    def handle_tray(self, action):
        if action == 'toggle':
            self.set_pet_hidden(not self.pet_hidden)
        elif action == 'hub':
            self.show_hub()
        elif action == 'startup':
            self.set_startup_enabled(not platform_win.startup_enabled())
        elif action == 'exit':
            self.close()

    def set_startup_enabled(self, enabled):
        try:
            platform_win.set_startup(bool(enabled), background=self.live2d_mode)
        except Exception as exc:
            logging.exception('Startup registration failed')
            messagebox.showerror('开机自启', f'{type(exc).__name__}: {exc}', parent=self.root)
            return False
        if hasattr(self, 'startup_var'):
            self.startup_var.set(bool(enabled))
        logging.info('Startup registration set to %s', bool(enabled))
        return True

    def live2d_failed(self, stage, message, detail=''):
        """Close the renderer and show the real error; never restore the Tk pet."""
        host, self.live2d = self.live2d, None
        if host is not None:
            try:
                host.close()
            except Exception:
                logging.exception('Live2D host cleanup failed')
        self.live2d_stage = '失败'
        logging.error('Live2D failed [%s] %s\n%s', stage, message, detail)
        self.pet.withdraw()
        self.show_live2d_failure(stage, message, detail)

    def show_live2d_failure(self, stage, message, detail):
        stage_label = {
            'imports': '加载依赖', 'application': '初始化 Qt', 'server': '启动本地服务',
            'webview': '创建渲染视图', 'page': '加载页面', 'waiting-ready': '等待模型就绪',
            'chromium': 'Chromium 渲染进程', '页面脚本': '页面脚本',
            '启动渲染进程': '启动渲染进程'}.get(stage, stage)
        if self.live2d_failure is not None and self.live2d_failure.winfo_exists():
            self.failure_stage.config(text='失败阶段：' + stage_label)
            self.failure_message.config(text=message)
            self.failure_detail.configure(state='normal')
            self.failure_detail.delete('1.0', 'end')
            self.failure_detail.insert('1.0', detail or '')
            self.failure_detail.configure(state='disabled')
            self.live2d_failure.deiconify()
            self.live2d_failure.lift()
            return
        win = self.live2d_failure = tk.Toplevel(self.root)
        win.title('Live2D 形象加载失败')
        win.configure(bg='#F4F6FB')
        win.geometry('640x430')
        win.minsize(520, 360)
        win.attributes('-topmost', True)
        win.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(win, padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='Live2D 形象加载失败',
                  font=('Microsoft YaHei UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(body,
                  text='程序不会再回退到旧形象。请按失败阶段排查，或点击“重试加载”。',
                  style='Muted.TLabel', wraplength=590).pack(anchor='w', pady=(6, 12))
        self.failure_stage = ttk.Label(body, text='失败阶段：' + stage_label,
                                       font=('Microsoft YaHei UI', 10, 'bold'))
        self.failure_stage.pack(anchor='w')
        self.failure_message = ttk.Label(body, text=message, foreground='#B23A48',
                                         wraplength=590)
        self.failure_message.pack(anchor='w', pady=(4, 8))
        if stage == 'chromium':
            hint = ('已关闭 Chromium 沙箱仍失败，请查看下方详情和日志。'
                    if self.live2d_no_sandbox else
                    '受限或远程会话中 Chromium 沙箱可能无法初始化。'
                    '可用“兼容模式重试”关闭沙箱；页面仍只来自本机，但这是明确的安全取舍。')
            ttk.Label(body, text=hint, style='Muted.TLabel',
                      wraplength=590).pack(anchor='w', pady=(0, 8))
        box = ttk.Frame(body)
        box.pack(fill='both', expand=True)
        self.failure_detail = tk.Text(box, height=8, wrap='word',
                                      font=('Consolas', 9), bg='white',
                                      relief='solid', borderwidth=1)
        scroll = ttk.Scrollbar(box, orient='vertical', command=self.failure_detail.yview)
        self.failure_detail.configure(yscrollcommand=scroll.set)
        self.failure_detail.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.failure_detail.insert('1.0', detail or '')
        self.failure_detail.configure(state='disabled')
        ttk.Label(body, text='完整日志：' + str(self.store.directory/'app.log'),
                  style='Muted.TLabel', wraplength=590).pack(anchor='w', pady=(8, 0))
        row = ttk.Frame(body)
        row.pack(fill='x', pady=10)
        ttk.Button(row, text='重试加载', style='Accent.TButton',
                   command=self.retry_live2d).pack(side='left')
        if stage == 'chromium' and not self.live2d_no_sandbox:
            ttk.Button(row, text='兼容模式重试',
                       command=self.retry_live2d_no_sandbox).pack(side='left', padx=8)
        ttk.Button(row, text='打开日志',
                   command=lambda: platform_win.open_target(self.store.directory/'app.log')).pack(side='left', padx=8)
        ttk.Button(row, text='退出程序', command=self.close).pack(side='right')
        win.update_idletasks()
        x = max(0, (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2)
        y = max(0, (win.winfo_screenheight() - win.winfo_reqheight()) // 2)
        win.geometry(f'+{x}+{y}')
        win.focus_force()

    def retry_live2d(self):
        # Let the button callback return before its window is destroyed.
        self.root.after_idle(self.start_live2d)

    def retry_live2d_no_sandbox(self):
        self.live2d_no_sandbox = True
        logging.warning('User selected Live2D compatibility mode: Chromium sandbox disabled')
        self.root.after_idle(self.start_live2d)

    def close_live2d_failure(self):
        win, self.live2d_failure = self.live2d_failure, None
        if win is not None and win.winfo_exists():
            win.destroy()

    def react(self,event,force=False):
        if 'companion' not in self.plugins.plugins:
            return
        if self.live2d_mode and not (self.live2d and self.live2d.ready):
            return
        entry = self.dialogue.data['events'].get(event)
        if not entry:
            return
        if self.sprite and (force or not self.focused or event not in ('click','drag','greeting')):
            self.sprite.play(entry['action'])
        if not force and (self.focused or self.bubble or self.queue or
                          self.store.get('dnd',False) or not self.store.get('companion.speech',True)):
            return
        line = self.dialogue.choose(event,force)
        if line:
            self.notify('小汐',line,character_event=False)

    def menu(self, event):
        self.cancel_pet_click()
        self.leave()
        self.toggle_context_popup(event.x_root, event.y_root)

    def hover(self, event):
        self.hover_job = self.root.after(650,self.show_tooltip)

    def leave(self, event=None):
        if self.hover_job:
            self.root.after_cancel(self.hover_job)
            self.hover_job = None
        if getattr(self,'tooltip',None):
            self.tooltip.destroy()
            self.tooltip = None

    def show_tooltip(self):
        self.hover_job = None
        upcoming = [x for x in self.store.get('plugin.productivity.reminders',[]) if not x['done']]
        upcoming.sort(key=lambda x:x['due'])
        text = self.status_summary()
        if upcoming:
            text += '\n下次提醒：' + upcoming[0]['title'] + ' ' + datetime.fromisoformat(upcoming[0]['due']).strftime('%H:%M')
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes('-topmost',True)
        tk.Label(self.tooltip,text=text,bg='#273149',fg='white',padx=12,pady=9,font=('Microsoft YaHei UI',10)).pack()
        self.tooltip.bind('<Button-1>', lambda e:self.show_panel('usage'))
        self.tooltip.geometry(f'+{max(0,self.pet_x-150)}+{max(0,self.visual_top()-65)}')

    def show_panel(self, tab=None):
        self.leave()
        if self.panel is None or not self.panel.winfo_exists():
            self.panel = tk.Toplevel(self.root)
            self.panel.title('小汐 · 你的桌面助手')
            self.panel.geometry('920x740')
            self.panel.minsize(780,630)
            self.panel.configure(bg=BG)
            self.panel.protocol('WM_DELETE_WINDOW', self.panel.withdraw)
            top = ttk.Frame(self.panel,padding=(25,20,25,8))
            top.pack(fill='x')
            ttk.Label(top,text='小汐  /  DESKTOP COMPANION',style='Title.TLabel').pack(anchor='w')
            ttk.Label(top,text='轻一点的陪伴，多一点的效率。数据只保存在本机。',style='Muted.TLabel').pack(anchor='w',pady=6)
            self.notebook = ttk.Notebook(self.panel)
            self.notebook.pack(fill='both',expand=True,padx=18,pady=8)
            self.plugins.call('build', self.notebook)
            self.build_settings()
            for index, (key, (label, _)) in enumerate(CATEGORIES.items()):
                if key not in self.tabs:
                    frame = ttk.Frame(self.notebook, padding=24)
                    ttk.Label(frame,text='此功能插件已停用，可在宠物与设置中启用。').pack()
                    self.tabs[key] = frame
                self.notebook.insert(index, self.tabs[key], text=label)
            bottom = ttk.Frame(self.panel,padding=(20,5,20,16))
            bottom.pack(fill='x')
            ttk.Label(bottom,text='用一句话设置 · 本地规则识别（不联网、不调用模型）',style='Muted.TLabel').pack(anchor='w')
            line = ttk.Frame(bottom)
            line.pack(fill='x',pady=5)
            self.command_entry = ttk.Entry(line)
            self.command_entry.pack(side='left',fill='x',expand=True,padx=(0,8))
            self.command_entry.bind('<Return>',lambda e:self.command())
            ttk.Button(line,text='执行设置',style='Accent.TButton',command=self.command).pack(side='right')
            self.command_status = ttk.Label(bottom,text='例：每小时提醒我休息 / 添加待办 买牛奶 / 开始25分钟专注',wraplength=790,style='Muted.TLabel')
            self.command_status.pack(anchor='w')
        self.panel.deiconify()
        self.panel.lift()
        if tab in self.tabs:
            self.notebook.select(self.tabs[tab])
        self.plugins.call('refresh')
        self.refresh_navigation()

    def command(self):
        text = self.command_entry.get().strip()
        if not text:
            return
        result = self.plugins.command(text)
        self.command_status.config(text=result)
        if not result.startswith(('未完成','暂时')):
            self.command_entry.delete(0,'end')

    def build_settings(self):
        frame = ttk.Frame(self.notebook,padding=20)
        self.notebook.add(frame,text='宠物与设置')
        self.tabs['settings'] = frame
        heading(frame,'你的桌宠，你来决定','插件可增加功能面板、菜单、指令和定时处理。启用 / 停用将在重新启动后生效。')
        self.plugin_tree = table(frame,['插件','版本','状态'],[210,90,320])
        self.plugin_tree.configure(height=4)
        for record in self.plugins.records:
            self.plugin_tree.insert('', 'end',iid=record['id'],values=(record['name'],record.get('version','—'),record['status']))
        buttons(frame,[('启用 / 停用',self.toggle_plugin),('插件说明',self.plugin_info),('打开插件文件夹',lambda:platform_win.open_target(BASE/'plugins'))])
        if not self.live2d_mode:
            buttons(frame,[('选择 PNG 外观',self.select_skin),('恢复原创外观',self.reset_skin),('选择配色',self.choose_accent)])
        buttons(frame,[('免打扰 开/关',self.toggle_dnd)])
        buttons(frame,[('通知记录',self.show_history),('打开数据文件夹',lambda:platform_win.open_target(self.store.directory)),('退出程序',self.close)])
        buttons(frame,[('编辑常用操作',self.edit_favorites),('返回功能小屋',self.show_hub)])
        behavior = ttk.LabelFrame(frame,text='自动行为',padding=6); behavior.pack(fill='x',pady=6)
        values = self.store.get('pet.behavior', {})
        for i,(key,title) in enumerate([('breathe','呼吸'),('blink','眨眼'),('wings','翅膀'),('hair','头发'),('mouth','偶尔张嘴'),('actions','自然小动作')]):
            variable = tk.BooleanVar(value=values.get(key,True))
            def save_behavior(k=key,v=variable):
                prefs=self.store.get('pet.behavior',{}); prefs[k]=v.get(); self.store.set('pet.behavior',prefs)
            ttk.Checkbutton(behavior,text=title,variable=variable,command=save_behavior).grid(row=0,column=i,sticky='w')
        speech = tk.BooleanVar(value=self.store.get('companion.speech',True))
        ttk.Checkbutton(behavior,text='互动短句',variable=speech,command=lambda:self.store.set('companion.speech',speech.get())).grid(row=1,column=0,columnspan=2,sticky='w')
        favorite_keys = tk.BooleanVar(value=self.store.get('navigation.favorite_hotkeys',False))
        ttk.Checkbutton(behavior,text='Ctrl+Alt+1～4 执行对应常用操作（重启生效）',variable=favorite_keys,
            command=lambda:self.store.set('navigation.favorite_hotkeys',favorite_keys.get())).grid(row=1,column=2,columnspan=4,sticky='w')
        if self.live2d_mode:
            ttk.Label(behavior,text='形象大小').grid(row=2,column=0,sticky='w',pady=(6,0))
            size = ttk.Combobox(behavior,state='readonly',values=['70%','80%','90%','100%'],width=8)
            current = f'{int(round(self.live2d_scale*100))}%'
            if current not in size['values']:
                current = '80%'
            size.set(current)
            size.grid(row=2,column=1,sticky='w',pady=(6,0))
            def save_scale(event=None):
                value = int(size.get().rstrip('%'))/100
                old_w, old_h = self.pet_width, self.pet_height
                self.live2d_scale = value
                self.store.set('live2d.scale',value)
                new_w, new_h = self.live2d_size()
                new_x = self.pet_x + (old_w - new_w)//2
                new_y = self.pet_y + (old_h - new_h)
                new_x = max(0, min(new_x, self.root.winfo_screenwidth() - new_w))
                new_y = max(0, min(new_y, self.root.winfo_screenheight() - new_h))
                self.pet_width, self.pet_height = new_w, new_h
                self.pet_x, self.pet_y = new_x, new_y
                self.pet.geometry(f'{new_w}x{new_h}+{new_x}+{new_y}')
                if self.live2d:
                    self.live2d.resize((new_w, new_h), (new_x, new_y))
                self.store.set('pet_position',[new_x,new_y])
                logging.info('Live2D scale set to %.2f, window %sx%s', value, new_w, new_h)
            size.bind('<<ComboboxSelected>>',save_scale)
            ttk.Label(behavior,text='即时生效；觉得大可以选 70%。',
                      style='Muted.TLabel').grid(row=2,column=2,columnspan=4,
                                                 sticky='w',padx=8,pady=(6,0))
        self.startup_var = tk.BooleanVar(value=platform_win.startup_enabled())
        def save_startup():
            if not self.set_startup_enabled(self.startup_var.get()):
                self.startup_var.set(platform_win.startup_enabled())
        ttk.Checkbutton(
            behavior,
            text='开机自启（后台运行，显示托盘）' if self.live2d_mode else '开机自启',
            variable=self.startup_var, command=save_startup
        ).grid(row=3,column=0,columnspan=4,sticky='w',pady=(6,0))
        choices = self.registry.category('companion')
        if choices:
            ttk.Label(frame,text='双击角色时执行').pack(anchor='w')
            choice = ttk.Combobox(frame,state='readonly',values=[a.title for a in choices])
            current = self.store.get('navigation.double_click','companion.greeting')
            choice.current(next((i for i,a in enumerate(choices) if a.id==current),0))
            choice.pack(anchor='w')
            choice.bind('<<ComboboxSelected>>',lambda e:self.store.set('navigation.double_click',choices[choice.current()].id))
        hotkey = 'Ctrl + Alt + P' if self.hotkey and self.hotkey.registered else '快捷键未注册（可能被占用）；单击角色仍可打开'
        ttk.Label(frame,text='呼出面板：' + hotkey + '\n关闭面板后桌宠继续运行；在右键菜单中退出。\n插件是本地 Python 代码，具有当前用户权限。请只放入你信任的插件。',style='Muted.TLabel',wraplength=720).pack(anchor='w',pady=8)

    def toggle_plugin(self):
        selected = self.plugin_tree.selection()
        if not selected:
            return
        plugin_id = selected[0]
        disabled = self.store.get('disabled_plugins',[])
        if plugin_id in disabled:
            disabled.remove(plugin_id)
        else:
            disabled.append(plugin_id)
        self.store.set('disabled_plugins',disabled)
        values = list(self.plugin_tree.item(plugin_id,'values'))
        values[2] = '待重启：停用' if plugin_id in disabled else '待重启：启用'
        self.plugin_tree.item(plugin_id,values=values)

    def plugin_info(self):
        selected = self.plugin_tree.selection()
        if selected:
            record = next(x for x in self.plugins.records if x['id']==selected[0])
            messagebox.showinfo(record['name'],record.get('description','')+'\n\n使用能力：\n'+'\n'.join(record.get('permissions',[]))+'\n\n能力声明用于说明，不是操作系统沙箱。',parent=self.panel)

    def select_skin(self):
        path = filedialog.askopenfilename(parent=self.panel,filetypes=[('PNG 图片','*.png')])
        if path:
            try:
                tk.PhotoImage(file=path)
            except tk.TclError:
                messagebox.showerror('无法读取图片','请选择有效 PNG 图片。',parent=self.panel)
                return
            self.store.set('skin_path',path)
            self.load_skin()

    def reset_skin(self):
        self.store.set('skin_path',None)
        self.custom_image = None

    def choose_accent(self):
        from tkinter.colorchooser import askcolor
        color = askcolor(self.store.get('accent','#778EE3'),parent=self.panel,title='选择头发和配饰颜色')[1]
        if color:
            self.store.set('accent',color)

    def toggle_dnd(self):
        value = not self.store.get('dnd',False)
        self.store.set('dnd',value)
        messagebox.showinfo('免打扰','已开启：提醒仅进入通知记录。' if value else '已关闭：到期提醒将显示气泡。',parent=self.panel or self.pet)

    def show_history(self):
        text = '\n\n'.join(f"{x['at']} · {x['title']}\n{x['body']}" for x in self.history[-20:]) or '暂无通知'
        window = tk.Toplevel(self.root)
        window.title('最近通知')
        box = tk.Text(window,width=66,height=24,font=('Microsoft YaHei UI',10),wrap='word')
        box.pack(fill='both',expand=True,padx=12,pady=12)
        box.insert('1.0',text)
        box.configure(state='disabled')

    def notify(self,title,body,actions=None,character_event=True):
        if character_event and 'companion' in self.plugins.plugins:
            event = {'休息一下吧':'break','应用使用提醒':'limit','到时间了':'reminder',
                     '专注开始':'focus_start','专注计时结束':'focus_end','休息结束':'break_end'}.get(title)
            if event:
                entry = self.dialogue.data['events'].get(event)
                if self.sprite and entry and not self.store.get('dnd',False):
                    self.sprite.play(entry['action'])
                if self.store.get('companion.speech',True):
                    line = self.dialogue.choose(event,force=True)
                    if line:
                        body = line+'\n'+body
        self.history.append({'at':datetime.now().strftime('%m-%d %H:%M'),'title':title,'body':body})
        self.history = self.history[-100:]
        self.store.set('notification_history',self.history)
        if not self.store.get('dnd',False):
            self.queue.append((title,body,actions))
            self.next_bubble()

    def next_bubble(self):
        if self.bubble or not self.queue:
            return
        title,body,actions = self.queue.popleft()
        if self.live2d and self.live2d.ready:
            self.live2d.state(notificationBusy=True, speechMs=min(6500, max(1600, len(body) * 110)))
        bubble = tk.Toplevel(self.root)
        self.bubble = bubble
        bubble.overrideredirect(True)
        bubble.attributes('-topmost',True)
        body_frame = ttk.Frame(bubble,padding=15)
        body_frame.pack(fill='both',expand=True)
        ttk.Label(body_frame,text=title,font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
        ttk.Label(body_frame,text=body,wraplength=280).pack(anchor='w',pady=8)
        row = ttk.Frame(body_frame)
        row.pack(fill='x')
        def close(callback=None):
            if self.bubble is bubble:
                self.bubble = None
                bubble.destroy()
                if self.live2d and self.live2d.ready:
                    self.live2d.state(notificationBusy=bool(self.queue), speechMs=0)
                if callback:
                    safe(self.pet,callback)
                self.root.after(200,self.next_bubble)
        for label,callback in actions or []:
            ttk.Button(row,text=label,command=lambda cb=callback:close(cb)).pack(side='left',padx=2)
        ttk.Button(row,text='关闭',command=close).pack(side='right')
        x = max(0,min(self.pet_x-140,self.root.winfo_screenwidth()-330))
        y = max(0,self.visual_top()-170)
        bubble.geometry(f'320x165+{x}+{y}')
        self.root.after(6500 if title=='小汐' else 20000,close)

    def tick(self):
        self.plugins.call('tick',datetime.now())
        self.refresh_navigation()
        self.root.after(1000,self.tick)

    def poll_hotkey(self):
        if self.hotkey and self.hotkey.poll():
            self.show_hub()
        if self.hotkey:
            slot = self.hotkey.poll_favorite()
            ids = self.favorite_ids()
            if slot is not None and slot < len(ids):
                self.invoke_action(ids[slot])
        self.root.after(100,self.poll_hotkey)

    def close(self):
        self.show_stop.set()
        if self.show_thread:
            self.show_thread.join(timeout=0.5)
            self.show_thread = None
        if self.show_event:
            platform_win.close_show_event(self.show_event)
            self.show_event = None
        if self.tray:
            self.tray.stop()
            self.tray = None
        if self.live2d:
            self.live2d.close()
            self.live2d = None
        self.plugins.call('shutdown')
        self.store.set('pet_position',[self.pet_x,self.pet_y])
        if self.hotkey:
            self.hotkey.close()
        self.store.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--data-dir')
    frozen = bool(getattr(sys, 'frozen', False))
    parser.add_argument('--live2d', action='store_true', default=frozen,
                        help='使用真实 Live2D 透明窗口（试用）')
    parser.add_argument('--live2d-no-sandbox', action='store_true', default=frozen,
                        help='兼容模式：关闭 Chromium 沙箱（仅加载本机页面）')
    parser.add_argument('--home', action='store_true', help='启动时显示功能小屋')
    parser.add_argument('--background', action='store_true',
                        help='后台启动：只显示托盘，不显示角色')
    args = parser.parse_args()
    if args.background and not args.live2d:
        parser.error('--background 需要 --live2d（托盘由渲染进程提供）')
    directory = Path(args.data_dir) if args.data_dir else DATA_HOME
    directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=directory/'app.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    mutex = None
    try:
        if not args.smoke:
            mutex = platform_win.acquire_instance()
            if platform_win.IS_WINDOWS and mutex is None:
                if platform_win.request_show():
                    logging.info('Existing instance asked to show; exiting second launch')
                    return
                raise RuntimeError('桌宠已经在运行，请双击桌面快捷方式或按 Ctrl+Alt+P 打开面板。')
        app = App(directory,args.smoke,live2d=args.live2d,
                  live2d_no_sandbox=args.live2d_no_sandbox,
                  background=args.background)
        if args.home:
            app.show_hub()
        if args.smoke:
            app.show_panel()
            app.root.update()
            expected = {'usage','shortcuts','productivity','settings'}
            assert expected.issubset(app.tabs), app.tabs
            if 'companion' in app.plugins.plugins:
                assert 'companion' in app.tabs
                assert app.sprite and len(app.sprite.frames)>=16
                app.react('success',force=True)
            assert all(r['status']=='运行中' for r in app.plugins.records), app.plugins.records
            app.plugins.call('tick',datetime.now())
            app.notify('测试提醒','通知组件能够正常创建。')
            app.root.update()
            print('SMOKE OK: tabs, plugins, native Tk windows, notification')
            app.close()
        else:
            app.root.mainloop()
    except Exception as exc:
        logging.exception('Application error')
        if args.smoke:
            raise
        messagebox.showerror('小汐桌宠 启动失败',
            f'{type(exc).__name__}: {exc}\n\n详细日志：{directory / "app.log"}')
    finally:
        if mutex:
            platform_win.kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    main()
