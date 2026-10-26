import re
import uuid
from tkinter import ttk, simpledialog, messagebox, filedialog
from desktop_pet import platform_win
from desktop_pet.ui import heading, table, buttons, safe


class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None
        self.ctx.add_action('静音 / 恢复', lambda: platform_win.system_action('mute'), action_id='shortcuts.mute')
        self.ctx.add_action('音量 ＋', lambda: platform_win.system_action('volume_up'), action_id='shortcuts.volume_up')
        self.ctx.add_action('音量 −', lambda: platform_win.system_action('volume_down'), action_id='shortcuts.volume_down')
        self.ctx.add_action('锁定电脑', lambda: platform_win.system_action('lock'), action_id='shortcuts.lock')
        self.sync_actions()

    def sync_actions(self):
        registry = getattr(self.ctx.app, 'registry', None)
        if registry is None:
            return
        from desktop_pet.actions import Action
        registry.remove_prefix('shortcuts.item.')
        for item in self.items():
            registry.add(Action('shortcuts.item.'+item['id'], 'shortcuts', item['name'],
                lambda row=item:self.launch(row), 'shortcuts'))

    def build(self, notebook):
        self.frame = ttk.Frame(notebook, padding=20)
        notebook.add(self.frame, text='快捷操作')
        self.ctx.app.tabs['shortcuts'] = self.frame
        heading(self.frame, '常用操作，少点几下', '添加软件、文件夹、文件或网址。场景可以一次打开多个入口。')
        self.tree = table(self.frame, ['名称', '类型', '目标'], [160, 85, 370])
        self.tree.bind('<Double-1>', lambda e: self.run())
        buttons(self.frame, [('打开', self.run), ('添加', self.add), ('编辑', self.edit), ('删除', self.delete), ('新建场景', self.scene)])
        buttons(self.frame, [('音量 −', lambda: self.ctx.app.invoke_action('shortcuts.volume_down')), ('音量 ＋', lambda: self.ctx.app.invoke_action('shortcuts.volume_up')), ('静音 / 恢复', lambda: self.ctx.app.invoke_action('shortcuts.mute')), ('锁定电脑', lambda: self.ctx.app.invoke_action('shortcuts.lock'))])
        self.refresh()

    def items(self):
        return self.ctx.get('items', [])

    def save(self, items):
        self.ctx.set('items', items)
        self.sync_actions()
        self.refresh()

    def selected(self):
        keys = self.tree.selection()
        if keys:
            return next((x for x in self.items() if x['id'] == keys[0]), None)
        messagebox.showinfo('选择入口', '请先选择一个入口。', parent=self.frame)

    def add(self):
        name = simpledialog.askstring('添加入口', '入口名称', parent=self.frame)
        if not name:
            return
        target = simpledialog.askstring('入口目标', '输入完整路径或 https:// 网址\n留空可选择本地文件；文件夹请直接粘贴路径。', parent=self.frame)
        if target is None:
            return
        if not target.strip():
            target = filedialog.askopenfilename(parent=self.frame)
        if target:
            self.add_item(name, target)

    def add_item(self, name, target):
        items = self.items()
        items.append({'id':uuid.uuid4().hex, 'name':name.strip(), 'target':target.strip().strip('"'), 'kind':'入口'})
        self.save(items)

    def edit(self):
        item = self.selected()
        if not item:
            return
        name = simpledialog.askstring('编辑名称', '名称', initialvalue=item['name'], parent=self.frame)
        if not name:
            return
        value = simpledialog.askstring('编辑目标', '场景填写入口名称，以中文或英文逗号分隔' if item['kind']=='场景' else '完整路径或网址', initialvalue=item['target'], parent=self.frame)
        if value:
            item.update(name=name.strip(), target=value.strip())
            self.save([item if x['id']==item['id'] else x for x in self.items()])

    def delete(self):
        item = self.selected()
        if item and messagebox.askyesno('删除入口', '只删除快捷入口，不删除原文件。继续？', parent=self.frame):
            self.save([x for x in self.items() if x['id'] != item['id']])

    def scene(self):
        name = simpledialog.askstring('新建场景', '场景名称，例如 开始办公', parent=self.frame)
        if not name:
            return
        entries = [x['name'] for x in self.items() if x['kind']=='入口']
        target = simpledialog.askstring('场景入口', '已有入口：' + '、'.join(entries) + '\n输入要打开的入口名称，用逗号分隔', parent=self.frame)
        if not target:
            return
        names = [x.strip() for x in re.split('[,，]', target) if x.strip()]
        if any(x not in entries for x in names):
            messagebox.showerror('入口不存在', '请先添加对应入口，再创建场景。', parent=self.frame)
            return
        items = self.items()
        items.append({'id':uuid.uuid4().hex, 'name':name, 'target':', '.join(names), 'kind':'场景'})
        self.save(items)

    def run(self):
        item = self.selected()
        if item:
            safe(self.frame, lambda: self.launch(item))

    def launch(self, item):
        if item['kind'] == '入口':
            platform_win.open_target(item['target'])
        else:
            available = {x['name']:x for x in self.items() if x['kind']=='入口'}
            targets = [x.strip() for x in re.split('[,，]', item['target']) if x.strip()]
            missing = [x for x in targets if x not in available]
            if missing:
                raise ValueError('场景中的入口已被改名或删除：' + '、'.join(missing))
            for name in targets:
                platform_win.open_target(available[name]['target'])

    def system(self, action):
        safe(self.frame, lambda: platform_win.system_action(action))

    def refresh(self):
        if self.frame is not None and self.frame.winfo_exists():
            self.tree.delete(*self.tree.get_children())
            for x in self.items():
                self.tree.insert('', 'end', iid=x['id'], values=(x['name'],x['kind'],x['target']))

    def command(self, text):
        match = re.fullmatch(r'(?:添加快捷入口|添加快捷操作|添加按钮)\s+(.+?)\s*[|｜]\s*(.+)', text)
        if match:
            self.add_item(match[1], match[2])
            return f'已添加“{match[1]}”。在快捷操作页点击即可打开。'
