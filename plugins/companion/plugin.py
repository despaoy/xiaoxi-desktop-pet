import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from desktop_pet.ui import heading, buttons
from desktop_pet.companion import FrameClock


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None
        for key, title in [('greeting','打招呼'), ('blink','眨眨眼'), ('stretch','舒展翅膀'), ('mouth','嘴型演示'), ('idle','恢复待机')]:
            ctx.add_action(title, lambda k=key:self.perform(k), action_id='companion.'+key)

    def perform(self, action):
        app = self.ctx.app
        if app.live2d:
            if not app.live2d.ready:
                raise ValueError('角色还在加载，请稍后再试。')
            app.pet_hidden = False
            app.live2d.state(visible=True, interaction=action)
            if self.frame is not None and self.frame.winfo_exists():
                self.caption.config(text='正在请求桌面角色播放…')
        elif app.sprite:
            app.sprite.play({'greeting':'reminder','stretch':'success','mouth':'click'}.get(action,'idle'))
        else:
            raise ValueError('当前没有可用的角色形象，请先处理“Live2D 形象加载失败”窗口中的错误。')
        if action == 'greeting' and not app.live2d:
            app.react('greeting', force=True)

    def playback_started(self, action):
        titles={'greeting':'打招呼：轻摆身体并张嘴','blink':'眨眨眼：连续眨眼两次',
                'stretch':'舒展翅膀：收拢再展开','mouth':'嘴型演示：连续开合','idle':'已恢复待机'}
        if self.frame is not None and self.frame.winfo_exists():
            self.caption.config(text='桌面角色 · '+titles.get(action,action))

    def build(self, notebook):
        app = self.ctx.app
        self.frame = ttk.Frame(notebook,padding=18)
        notebook.add(self.frame,text='动作与互动')
        app.tabs['companion'] = self.frame
        heading(self.frame,'和小汐互动','动作直接在桌面角色上播放。自动动作和双击偏好可在「宠物与设置」调整。')
        actions = ttk.Frame(self.frame); actions.pack(fill='x',pady=10)
        for i, action in enumerate(app.registry.category('companion')):
            ttk.Button(actions,text=action.title,command=lambda key=action.id:app.invoke_action(key)).grid(row=i//3,column=i%3,padx=6,pady=6,sticky='ew')
        for col in range(3): actions.columnconfigure(col,weight=1)
        right = ttk.LabelFrame(self.frame,text='互动短句',padding=12)
        right.pack(fill='both',expand=True,pady=10)
        self.events = ttk.Combobox(right,state='readonly',values=list(app.dialogue.data['events']))
        self.events.set('click'); self.events.pack(fill='x',pady=5)
        self.events.bind('<<ComboboxSelected>>',lambda e:self.load_lines())
        ttk.Label(right,text='每行一句；保存后立即生效。短句暂不发声。',style='Muted.TLabel').pack(anchor='w')
        self.editor = tk.Text(right,height=7,width=35,wrap='word',font=('Microsoft YaHei UI',10),undo=True)
        self.editor.pack(fill='both',expand=True,pady=5)
        buttons(right,[('保存台词',self.save_lines),('随机试说',self.try_line)])
        self.caption = ttk.Label(right,text='待机短句不会自动连续弹出。',style='Muted.TLabel')
        self.caption.pack(anchor='w',pady=8)
        self.load_lines()

    def try_line(self):
        self.ctx.app.react(self.events.get(),force=True)

    def load_lines(self):
        self.editor.delete('1.0','end')
        self.editor.insert('1.0','\n'.join(self.ctx.app.dialogue.data['events'][self.events.get()]['lines']))

    def save_lines(self):
        lines = [x.strip() for x in self.editor.get('1.0','end').splitlines() if x.strip()]
        if not lines or any(len(x)>120 for x in lines):
            messagebox.showerror('台词格式','至少保留一句，每句不超过120字。',parent=self.frame)
            return
        app = self.ctx.app
        data = json.loads(json.dumps(app.dialogue.data,ensure_ascii=False))
        data['events'][self.events.get()]['lines'] = lines
        # User edits live in data; bundled defaults remain untouched.
        path = app.store.directory/'language-zh-CN.json'
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        app.dialogue.path = path
        app.dialogue.reload()
        self.caption.config(text='已保存，下一次触发立即使用。')

