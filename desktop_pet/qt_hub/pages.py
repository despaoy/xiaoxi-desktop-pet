"""Snapshot-only hub pages. Mutations always go through the host command bridge."""
from datetime import datetime
from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QCheckBox,QComboBox,QSlider,QSpinBox,QLineEdit,QPlainTextEdit,QDialog,
    QDialogButtonBox,QListWidget,QListWidgetItem,QAbstractItemView,QMessageBox,
    QProgressBar,QFrame,QInputDialog)
from .common import Card,Scene,label,button,row,clear_layout,duration,CardColumns


def set_checked(control,value):
    with QSignalBlocker(control):control.setChecked(bool(value))


def simple_choice(owner,title,current,choices,command,payload_key,extra=None,editable=False):
    dialog=QDialog(owner);dialog.setWindowTitle(title);dialog.setMinimumWidth(380)
    layout=QVBoxLayout(dialog);layout.addWidget(label(title,'cardTitle'))
    choice=QComboBox();choice.setEditable(editable)
    for text,value in choices:choice.addItem(text,value)
    ix=choice.findData(current)
    if ix>=0:choice.setCurrentIndex(ix)
    elif editable:choice.setCurrentText(str(current or ''))
    layout.addWidget(choice);actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(actions);actions.rejected.connect(dialog.reject)
    def save():
        value=choice.currentText() if editable else choice.currentData()
        owner.dispatch(command,{**(extra or {}),payload_key:value},actions.button(QDialogButtonBox.StandardButton.Save),lambda result:dialog.accept())
    actions.accepted.connect(save);dialog.open();owner.keep_dialog(dialog)
    return dialog


class HomePage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.signature=None
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(16)
        hero=QHBoxLayout();hero.setSpacing(20)
        self.scene=Scene('home','欢迎回来，\n陪你坐一会儿。');self.scene.setMinimumWidth(280);self.scene.setMinimumHeight(300)
        hero.addWidget(self.scene,5)
        side=QWidget();sl=QVBoxLayout(side);sl.setContentsMargins(0,12,0,0)
        sl.addWidget(label('眼前的一件事','eyebrow'))
        self.goal=label('按自己的节奏，慢慢来。','heading');sl.addWidget(self.goal)
        self.timer=label('25:00','timer');sl.addWidget(self.timer)
        self.focus=button('一起专注','clock',True);self.focus.clicked.connect(lambda:owner.select_page('focus'));sl.addWidget(self.focus)
        self.next_reminder=label('暂无待提醒事项','muted');sl.addWidget(self.next_reminder)
        b=button('查看提醒与待办','bell');b.clicked.connect(lambda:owner.select_page('focus'));sl.addWidget(b)
        sl.addStretch();hero.addWidget(side,5);outer.addLayout(hero)
        self.greet_buttons=[];greet=row()
        for text,aid,ico in [('打招呼','companion.greeting','heart'),('看看周围','companion.look','eye'),('轻轻放松','companion.relax','spark')]:
            b=button(text,ico);b.clicked.connect(lambda checked=False,a=aid,w=b:owner.dispatch('action.invoke',{'id':a},w));greet.layout().addWidget(b);self.greet_buttons.append((b,aid))
        outer.addWidget(greet)
        self.fav_card=Card('常用操作');self.favorites=QHBoxLayout();self.fav_card.layout.addLayout(self.favorites)
        edit=button('编辑常用操作','edit');edit.clicked.connect(owner.edit_favorites);self.fav_card.layout.addWidget(edit,0,Qt.AlignmentFlag.AlignRight)
        outer.addWidget(self.fav_card)
        command=Card('一句话安排');self.input=QLineEdit();self.input.setPlaceholderText('例如：10分钟后提醒我喝水 / 添加待办 读书')
        self.input.setMaxLength(1000);self.send=button('执行','play',True);self.send.clicked.connect(self.run_command);self.input.returnPressed.connect(self.run_command)
        command.layout.addWidget(row(self.input,self.send));command.layout.addWidget(label('本地规则解析，不上传输入内容。','muted'));outer.addWidget(command)
        outer.addStretch()
    def run_command(self):
        text=self.input.text().strip()
        if not text:return
        def done(result):
            if self.input.text().strip()==text:self.input.clear()
        self.owner.dispatch('command.run',{'text':text},self.send,done)
    def update_snapshot(self,s):
        timer=s.get('timer');todo=next((x for x in s.get('todos',[]) if not x.get('done')),None)
        self.goal.setText(todo['title'] if todo else '先选一件小事，也可以直接开始。')
        if timer:
            self.timer.setText(duration(self.owner.timer_remaining(s)));self.focus.setText(('继续' if timer.get('paused') else '查看')+timer.get('kind','计时'))
            self.scene.caption.setText('我会轻轻的，不打扰你。' if not timer.get('paused') else '歇一歇也很好，我在这里。')
        else:self.timer.setText('25:00');self.focus.setText('一起专注');self.scene.caption.setText('欢迎回来，\n陪你坐一会儿。')
        reminders=[x for x in s.get('reminders',[]) if not x.get('done')]
        reminders.sort(key=lambda x:x.get('due',''))
        self.next_reminder.setText(('下次提醒 · '+str(reminders[0].get('due',''))[5:16].replace('T',' ')+'\n'+reminders[0].get('title','')) if reminders else '暂无待提醒事项，随时可以添加。')
        actions={x['id']:x for x in s.get('actions',[])}
        for b,key in self.greet_buttons:b.setEnabled(key in actions and actions[key].get('enabled',True) and not self.owner.is_pending(b))
        sig=repr([(key,actions.get(key)) for key in s.get('favorites',[])])
        if sig!=self.signature:
            self.signature=sig;clear_layout(self.favorites)
            for key in s.get('favorites',[]):
                a=actions.get(key)
                if not a:continue
                b=button(a['title'],'spark');b.setEnabled(a.get('enabled',True));b.clicked.connect(lambda checked=False,k=key,w=b:self.owner.dispatch('action.invoke',{'id':k},w));self.favorites.addWidget(b)
            if not self.favorites.count():self.favorites.addWidget(label('还没有常用操作，点击下方按钮选几项吧。','muted'))


class InteractionPage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.sig=None;self.snapshot={}
        l=QVBoxLayout(self);l.setContentsMargins(0,0,0,0);l.setSpacing(15)
        h=QHBoxLayout();self.scene=Scene('interaction','嗨，今天也一起加油呀。');h.addWidget(self.scene,5)
        side=QWidget();sl=QVBoxLayout(side);sl.setContentsMargins(0,0,0,0);sl.addWidget(label('陪小汐玩一会儿。','heading'))
        self.actions=QGridLayout();sl.addLayout(self.actions);sl.addStretch();h.addWidget(side,6);l.addLayout(h)
        prefs=Card('自动行为');grid=QGridLayout();self.behavior={}
        for i,(key,title) in enumerate([('breathe','呼吸'),('blink','眨眼'),('wings','翅膀'),('hair','头发'),('mouth','嘴型'),('actions','自然小动作')]):
            c=QCheckBox(title);c.toggled.connect(lambda value,k=key,w=c:owner.dispatch('settings.behavior',{'key':k,'enabled':value},w));self.behavior[key]=c;grid.addWidget(c,i//3,i%3)
        prefs.layout.addLayout(grid)
        self.speech=QCheckBox('动作和日常短句');self.speech.toggled.connect(lambda v:owner.dispatch('settings.speech',{'enabled':v},self.speech))
        language=button('编辑台词','edit');language.clicked.connect(self.language_editor);prefs.layout.addWidget(row(self.speech,language));l.addWidget(prefs)
        display=Card('角色显示');self.visible=QCheckBox('显示桌面角色');self.visible.toggled.connect(lambda v:owner.dispatch('settings.visible',{'visible':v},self.visible))
        self.scale=QSlider(Qt.Orientation.Horizontal);self.scale.setRange(50,125);self.scale_value=label('100%');self.scale.valueChanged.connect(lambda v:self.scale_value.setText(f'{v}%'))
        self.scale_commit=QTimer(self);self.scale_commit.setSingleShot(True);self.scale_commit.setInterval(200)
        self.scale_commit.timeout.connect(lambda:owner.dispatch('settings.scale',{'scale':self.scale.value()/100},self.scale))
        self.scale.actionTriggered.connect(lambda action:self.scale_commit.start() if not self.scale.isSliderDown() else None)
        self.scale.sliderReleased.connect(lambda:owner.dispatch('settings.scale',{'scale':self.scale.value()/100},self.scale))
        display.layout.addWidget(row(self.visible,label('角色大小'),self.scale,self.scale_value));l.addWidget(display)
        legacy=button('原形象与语言高级设置','settings');legacy.clicked.connect(lambda:owner.dispatch('legacy.open',{'page':'companion'},legacy));l.addWidget(legacy)
        l.addWidget(label('小屋插画按页面切换；桌面角色动作仍由现有模型播放。','muted'));l.addStretch()
    def update_snapshot(self,s):
        self.snapshot=s;settings=s.get('settings',{})
        for key,c in self.behavior.items():
            if not self.owner.is_pending(c):set_checked(c,settings.get('behavior',{}).get(key,True))
        if not self.owner.is_pending(self.speech):set_checked(self.speech,settings.get('speech',True))
        if not self.owner.is_pending(self.visible):set_checked(self.visible,settings.get('pet_visible',True))
        if not self.scale.isSliderDown() and not self.scale_commit.isActive() and not self.owner.is_pending(self.scale):
            with QSignalBlocker(self.scale):self.scale.setValue(round(settings.get('scale',1)*100))
            self.scale_value.setText(f'{self.scale.value()}%')
        self.scale.setEnabled(bool(settings.get('live2d_mode',False)) and not self.owner.is_pending(self.scale))
        self.scale.setToolTip('当前 Live2D 角色缩放' if settings.get('live2d_mode') else '图片形象请使用原形象高级设置')
        actions=[a for a in s.get('actions',[]) if a.get('category')=='companion']
        sig=repr(actions)
        if sig!=self.sig:
            self.sig=sig;clear_layout(self.actions)
            for i,a in enumerate(actions):
                b=button(a['title'],'heart');b.setMinimumHeight(55);b.setEnabled(a.get('enabled',True));b.clicked.connect(lambda checked=False,k=a['id'],w=b:self.owner.dispatch('action.invoke',{'id':k},w));self.actions.addWidget(b,i//2,i%2)
            if not actions:self.actions.addWidget(label('互动插件未启用，请前往设置查看。','muted'),0,0)
    def language_editor(self):
        data=self.snapshot.get('language',{});d=QDialog(self.owner);d.setWindowTitle('编辑小汐台词');d.resize(560,420);l=QVBoxLayout(d)
        choice=QComboBox();entries=[]
        for kind in ('events','actions'):
            for key,lines in data.get(kind,{}).items():
                choice.addItem(('日常 · ' if kind=='events' else '动作 · ')+key,(kind,key));entries.append(lines)
        l.addWidget(choice);l.addWidget(label('每行一句。保存后生效；预览只播放所选现有事件。','muted'))
        editor=QPlainTextEdit();l.addWidget(editor)
        def select(index):
            lines=entries[index] if 0<=index<len(entries) else []
            if isinstance(lines,dict):lines=lines.get('lines',[])
            editor.setPlainText('\n'.join(str(x) for x in lines))
        choice.currentIndexChanged.connect(select);select(0)
        save=button('保存台词','check',True);preview=button('预览','play');cancel=button('关闭','close')
        def commit():
            if choice.currentData():
                kind,key=choice.currentData();lines=[x.strip() for x in editor.toPlainText().splitlines() if x.strip()]
                self.owner.dispatch('language.save',{'kind':kind,'key':key,'lines':lines},save,lambda result:d.accept())
        save.clicked.connect(commit)
        preview.clicked.connect(lambda:self.owner.dispatch('language.preview',dict(zip(('kind','key'),choice.currentData())),preview) if choice.currentData() else None)
        cancel.clicked.connect(d.reject);l.addWidget(row(preview,save,cancel));self.owner.keep_dialog(d);d.open()


class UsagePage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.sig=None;self.snapshot={}
        l=QVBoxLayout(self);l.setContentsMargins(0,0,0,0);l.setSpacing(15)
        l.addWidget(label('慢慢来，看看时间去了哪里。','heading'))
        scene=Scene('focus','忙碌之外，也留一点时间给自己。',compact=True);scene.setFixedHeight(86);l.addWidget(scene)
        self.range=QComboBox();self.range.addItem('今天',1);self.range.addItem('近 7 天',7);self.range.addItem('近 30 天',30)
        self.range.activated.connect(lambda index:owner.dispatch('usage.range',{'days':self.range.itemData(index)},self.range))
        self.pause=button('暂停统计','pause');self.pause.clicked.connect(lambda:owner.dispatch('usage.enabled',{'enabled':not self.snapshot.get('usage',{}).get('enabled',True)},self.pause))
        l.addWidget(row(self.range,self.pause));self.status=label('正在读取使用记录…','muted');l.addWidget(self.status)
        self.total=label('—','timer');self.total.setStyleSheet('font-size:32px;font-weight:600;');l.addWidget(self.total)
        self.daily=Card('每日使用时长');self.daily_rows=QVBoxLayout();self.daily.layout.addLayout(self.daily_rows);l.addWidget(self.daily)
        self.apps=Card('应用使用排行');self.app_rows=QVBoxLayout();self.apps.layout.addLayout(self.app_rows);l.addWidget(self.apps)
        self.categories=Card('分类使用分布');self.category_rows=QVBoxLayout();self.categories.layout.addLayout(self.category_rows);l.addWidget(self.categories)
        rest=Card('连续使用提醒');self.break_minutes=QSpinBox();self.break_minutes.setRange(0,1440);self.break_minutes.setSuffix(' 分钟');self.break_minutes.setSpecialValueText('关闭');self.break_dirty=False
        self.break_minutes.valueChanged.connect(lambda value:setattr(self,'break_dirty',True))
        save=button('保存','check');save.clicked.connect(lambda:owner.dispatch('usage.break',{'minutes':self.break_minutes.value()},save,lambda result:setattr(self,'break_dirty',False)));rest.layout.addWidget(row(self.break_minutes,save));l.addWidget(rest)
        l.addWidget(label('使用时长不等于专注时长；不采集网页正文、聊天内容或键盘文字。','muted'))
        for card in (self.daily,self.apps,self.categories,rest):l.removeWidget(card)
        l.insertWidget(5,CardColumns(self.daily,self.apps));l.insertWidget(6,CardColumns(self.categories,rest))
        legacy=button('原统计管理与更多设置','chart');legacy.clicked.connect(lambda:owner.dispatch('legacy.open',{'page':'usage'},legacy));l.addWidget(legacy);l.addStretch()
    def update_snapshot(self,s):
        self.snapshot=s;u=s.get('usage',{});error=u.get('error')
        self.status.setText('读取失败：'+str(error) if error else ('正在记录' if u.get('enabled',True) else '统计已暂停，历史记录仍保留'))
        self.total.setText('—' if error else duration(u.get('total',0)))
        self.pause.setText('暂停统计' if u.get('enabled',True) else '恢复统计')
        with QSignalBlocker(self.range):self.range.setCurrentIndex(max(0,self.range.findData(u.get('days',1))))
        if not self.break_dirty:
            with QSignalBlocker(self.break_minutes):self.break_minutes.setValue(int(u.get('break_minutes',0) or 0))
        sig=repr((u.get('daily'),u.get('records'),u.get('categories'),error))
        if sig==self.sig:return
        self.sig=sig
        for layout in (self.daily_rows,self.app_rows,self.category_rows):clear_layout(layout)
        if error:
            self.daily_rows.addWidget(label('暂时无法读取记录，请稍后重试；不会把错误当成零记录。','muted'));return
        daily=u.get('daily',[]);maximum=max([x.get('seconds',0) for x in daily]+[1])
        for record in daily:
            bar=QProgressBar();bar.setRange(0,1000);bar.setValue(round(record.get('seconds',0)/maximum*1000));bar.setTextVisible(False);bar.setMaximumHeight(12)
            text=label(str(record.get('day',''))[5:],wrap=False);text.setMinimumWidth(45)
            self.daily_rows.addWidget(row(text,bar,label(duration(record.get('seconds',0)),wrap=False)))
        if not daily:self.daily_rows.addWidget(label('暂无使用记录。','muted'))
        for a in u.get('records',[]):
            item=QWidget();r=QHBoxLayout(item);r.setContentsMargins(0,3,0,3)
            info=label(a.get('display',a.get('id',''))+'\n'+a.get('category','其他'));r.addWidget(info,1);r.addWidget(label(duration(a.get('seconds',0)),wrap=False))
            cat=button('分类','folder');cat.clicked.connect(lambda checked=False,rec=a:self.change_category(rec));r.addWidget(cat)
            limit=button('限时','clock');limit.clicked.connect(lambda checked=False,rec=a:self.change_limit(rec));r.addWidget(limit);self.app_rows.addWidget(item)
        if not u.get('records'):self.app_rows.addWidget(label('暂无应用记录。','muted'))
        for c in u.get('categories',[]):self.category_rows.addWidget(row(label(c.get('name','其他')),label(duration(c.get('seconds',0)))))
    def change_category(self,a):
        choices=[(x['label'],x['label']) for x in self.snapshot.get('usage',{}).get('category_choices',[])]
        simple_choice(self.owner,'应用分类',a.get('category'),choices,'usage.category','category',{'id':a['id']},False)
    def change_limit(self,a):
        value,ok=QInputDialog.getInt(self,'每日限时','分钟（0 为关闭；只提醒，不结束进程）',int(a.get('limit',0) or 0),0,1440)
        if ok:self.owner.dispatch('usage.limit',{'id':a['id'],'minutes':value})


class SettingsPage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.snapshot={};self.plugin_sig=None
        l=QVBoxLayout(self);l.setContentsMargins(0,0,0,0);l.setSpacing(15)
        l.addWidget(label('让小汐按你的习惯陪伴。','heading'))
        scene=Scene('home','你喜欢的陪伴方式，我会记住。',compact=True);scene.setFixedHeight(86);l.addWidget(scene)
        general=Card('通用');self.startup=QCheckBox('开机启动');self.startup.toggled.connect(lambda v:owner.dispatch('settings.startup',{'enabled':v},self.startup));general.layout.addWidget(self.startup)
        self.focused=QCheckBox('专注模式：减少角色动作与闲聊');self.focused.toggled.connect(lambda v:owner.dispatch('settings.focused',{'enabled':v},self.focused));general.layout.addWidget(self.focused)
        self.double=QComboBox();self.double.activated.connect(lambda index:owner.dispatch('settings.double_click',{'id':self.double.itemData(index)},self.double));general.layout.addWidget(row(label('双击角色'),self.double));l.addWidget(general)
        notify=Card('通知');self.dnd=QCheckBox('免打扰');self.dnd.toggled.connect(lambda v:owner.dispatch('settings.dnd',{'enabled':v},self.dnd));notify.layout.addWidget(self.dnd)
        notify.layout.addWidget(label('开启后提醒只进入记录，不显示气泡；与专注模式不同。','muted'))
        history=button('通知记录','history');history.clicked.connect(owner.show_history);notify.layout.addWidget(history);l.addWidget(notify)
        shortcuts=Card('快捷键');self.hotkey=label('呼出小屋：Ctrl + Alt + P','muted');shortcuts.layout.addWidget(self.hotkey)
        self.favorite_hotkeys=QCheckBox('启用收藏快捷键 Ctrl + Alt + 1～4（重启生效）');self.favorite_hotkeys.toggled.connect(lambda v:owner.dispatch('settings.favorite_hotkeys',{'enabled':v},self.favorite_hotkeys));shortcuts.layout.addWidget(self.favorite_hotkeys)
        f=button('编辑四个常用操作','edit');f.clicked.connect(owner.edit_favorites);shortcuts.layout.addWidget(f);l.addWidget(shortcuts)
        self.plugins=Card('插件');self.plugin_rows=QVBoxLayout();self.plugins.layout.addLayout(self.plugin_rows);self.plugins.layout.addWidget(label('更改启用状态后重启生效。插件按当前用户权限运行，只安装可信代码。','muted'))
        folder=button('打开插件目录','folder');folder.clicked.connect(lambda:owner.dispatch('plugins.open',{},folder));self.plugins.layout.addWidget(folder);l.addWidget(self.plugins)
        data=Card('数据与兼容入口');data.layout.addWidget(label('数据保存在本机。备份前请完全退出桌宠，再复制整个 data 文件夹。','muted'))
        opened=button('打开数据目录','folder');opened.clicked.connect(lambda:owner.dispatch('data.open',{},opened))
        old=button('原设置面板（托盘、形象等）','settings');old.clicked.connect(lambda:owner.dispatch('legacy.open',{'page':'settings'},old));data.layout.addWidget(row(opened,old));l.addWidget(data)
        for card in (general,notify,shortcuts,self.plugins,data):l.removeWidget(card)
        run=Card('后台运行');run.layout.addWidget(label('收起小屋不会退出桌宠，计时和提醒继续运行。','muted'))
        quit_button=button('退出桌宠','close');quit_button.clicked.connect(owner.confirm_exit);run.layout.addWidget(quit_button)
        l.addWidget(CardColumns(general,notify,shortcuts,self.plugins,data,run))
        self.favorite_hotkeys.setText('启用收藏热键（重启生效）');self.favorite_hotkeys.setToolTip('Ctrl + Alt + 1～4')
        self.focused.setText('专注模式：减少动作与闲聊')
        old.setText('原设置与形象');opened.setText('数据目录')
        l.addStretch()
    def update_snapshot(self,s):
        self.snapshot=s;settings=s.get('settings',{})
        for control,value in [(self.startup,settings.get('startup',False)),(self.focused,s.get('focused',False)),(self.dnd,s.get('dnd',False)),(self.favorite_hotkeys,settings.get('favorite_hotkeys',False))]:
            if not self.owner.is_pending(control):set_checked(control,value)
        actions=[a for a in s.get('actions',[]) if a.get('category')=='companion'];ids=[self.double.itemData(i) for i in range(self.double.count())]
        if ids!=[a['id'] for a in actions] and not self.double.view().isVisible():
            with QSignalBlocker(self.double):
                self.double.clear()
                for a in actions:self.double.addItem(a['title'],a['id'])
        if not self.owner.is_pending(self.double):
            with QSignalBlocker(self.double):self.double.setCurrentIndex(self.double.findData(settings.get('double_click','companion.greeting')))
        self.hotkey.setText('呼出小屋：Ctrl + Alt + P'+('' if settings.get('hotkey_registered') else ' · 未注册成功，可单击角色或使用托盘'))
        sig=repr(s.get('plugins',[]))
        if sig!=self.plugin_sig:
            self.plugin_sig=sig;clear_layout(self.plugin_rows)
            for p in s.get('plugins',[]):
                c=QCheckBox(p.get('name',p['id'])+'  '+str(p.get('version','')));c.setChecked(p.get('enabled',True));c.setToolTip(p.get('description','')+'\n能力：'+str(p.get('permissions',[])))
                c.toggled.connect(lambda value,key=p['id'],w=c:self.owner.dispatch('plugin.enabled',{'id':key,'enabled':value},w))
                self.plugin_rows.addWidget(row(c,label(str(p.get('status','')),'muted')))
            if not s.get('plugins'):self.plugin_rows.addWidget(label('未发现插件，请检查插件目录。','muted'))
