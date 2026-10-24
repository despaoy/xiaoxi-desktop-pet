"""Production Qt view: snapshots in, validated command requests out."""
import json
import time
import uuid
import weakref
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication,QWidget,QHBoxLayout,QVBoxLayout,QScrollArea,
    QStackedWidget,QButtonGroup,QFrame,QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,
    QSpinBox,QDoubleSpinBox,QAbstractSpinBox,QDialog,QDialogButtonBox,QListWidget,QListWidgetItem,
    QMessageBox,QSizePolicy)
from shiboken6 import isValid
from .common import button,label,Card,Scene,duration,CardColumns
from .pages import HomePage,InteractionPage,UsagePage,SettingsPage
from .productivity import FocusPage,ShortcutsPage

PAGES=[('home','小屋首页','home'),('focus','专注与事项','clock'),('interaction','动作互动','heart'),
       ('shortcuts','快捷工具','tools'),('usage','时间回顾','chart'),('settings','设置','settings')]
STYLE='''
QWidget { color:#514363; font-size:14px; }
QWidget#cozyRoot, QStackedWidget, QScrollArea, QWidget#pageContent { background:transparent; }
QLabel { background:transparent; }
QLabel[role="title"] { font-size:25px; font-weight:700; color:#685283; }
QLabel[role="heading"] { font-size:22px; font-weight:600; color:#5e477c; }
QLabel[role="cardTitle"] { font-size:17px; font-weight:600; }
QLabel[role="eyebrow"] { font-size:13px; color:#8b75a5; }
QLabel[role="muted"] { font-size:12px; color:#8b8196; }
QLabel[role="timer"] { font-size:48px; font-weight:600; color:#70578c; }
QLabel#sceneSpeech { background:rgba(255,251,248,235); padding:13px; border:1px solid #e9deed; border-radius:17px; color:#735985; }
QFrame#cozyCard { background:rgba(255,255,255,218); border:1px solid #eae2ee; border-radius:17px; }
QPushButton { background:#f3edf8; border:1px solid #e5d9ee; border-radius:11px; padding:7px 12px; }
QPushButton:hover { background:#ece1f5; border-color:#c7b1de; }
QPushButton:pressed { background:#dfcfed; }
QPushButton:focus { border:2px solid #a98acb; }
QPushButton:disabled { color:#aaa3b1; background:#f0edf2; border-color:#e9e4ec; }
QPushButton[primary="true"] { color:white; background:#a184c5; border:1px solid #9677bc; font-weight:600; }
QPushButton[primary="true"]:hover { background:#9071b5; }
QPushButton[primary="true"]:disabled { background:#d7cce3; border-color:#d7cce3; }
QPushButton[nav="true"] { text-align:left; padding:12px 10px; border:1px solid transparent; background:transparent; }
QPushButton[nav="true"]:checked { background:#eadef6; color:#765498; }
QLineEdit,QPlainTextEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateTimeEdit { background:#fffcfa; border:1px solid #ded2e8; border-radius:8px; padding:7px; selection-background-color:#c1a8df; min-height:20px; }
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QSpinBox:focus { border:2px solid #a98acb; }
QComboBox::drop-down { border:0; width:20px; }
QCheckBox { spacing:9px; padding:5px 1px; }
QCheckBox::indicator { width:18px; height:18px; border-radius:5px; border:1px solid #b49acb; background:#fff; }
QCheckBox::indicator:checked { background:#a184c5; border:2px solid #8461aa; }
QCheckBox:disabled { color:#aaa3b1; }
QSlider::groove:horizontal { height:6px; background:#e7ddee; border-radius:3px; }
QSlider::handle:horizontal { width:18px; margin:-6px 0; border:2px solid #a184c5; border-radius:9px; background:#fff; }
QProgressBar { border:none; border-radius:5px; background:#ede6f2; min-height:9px; }
QProgressBar::chunk { background:#baa0d5; border-radius:5px; }
QScrollArea { border:none; }
QScrollBar:vertical { background:transparent; width:8px; margin:3px 0; }
QScrollBar::handle:vertical { background:#d4c5e2; border-radius:4px; min-height:28px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QTableWidget,QListWidget { background:#fffdfb; border:1px solid #eae2ee; border-radius:10px; gridline-color:#eee6f2; }
QHeaderView::section { background:#f6f0fa; padding:7px; border:none; color:#7e6398; }
QTableWidget::item:selected,QListWidget::item:selected { background:#eadef6; color:#514363; }
QDialog { background:#fffaf6; }
QToolTip { background:#fffaf6; border:1px solid #d9c8e9; padding:6px; color:#514363; }
'''


class HubWindow(QWidget):
    def __init__(self,send_command,on_hide=None,preview=False):
        super().__init__();self.send_command=send_command;self.on_hide=on_hide;self.preview=preview
        self.snapshot={};self.pending={};self.pending_keys={};self.dialogs=[];self.drag_origin=None;self.last_editing=False;self.suspended_dialogs=[]
        self.setObjectName('cozyRoot');self.setWindowTitle('小汐的小屋');self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setStyleSheet(STYLE)
        self.setFont(QFont('Microsoft YaHei UI',10))
        screen=QApplication.primaryScreen().availableGeometry();self.resize(min(1120,screen.width()-24),min(790,screen.height()-24));self.setMinimumSize(min(680,screen.width()-24),min(460,screen.height()-24))
        self.move(screen.x()+(screen.width()-self.width())//2,screen.y()+(screen.height()-self.height())//2)
        outer=QVBoxLayout(self);outer.setContentsMargins(20,15,20,14);outer.setSpacing(10)
        head=QHBoxLayout();title=label('小汐的小屋','title');head.addWidget(title);head.addStretch()
        all_actions=button('全部操作','tools');all_actions.clicked.connect(self.show_actions);head.addWidget(all_actions)
        self.history_button=button('通知记录','bell');self.history_button.clicked.connect(self.show_history);head.addWidget(self.history_button)
        close=button('收起','close');close.clicked.connect(self.close);head.addWidget(close);outer.addLayout(head)
        body=QHBoxLayout();body.setSpacing(18);nav=QWidget();nav.setFixedWidth(156);nl=QVBoxLayout(nav);nl.setContentsMargins(0,7,0,0);nl.setSpacing(7)
        self.nav_group=QButtonGroup(self);self.nav_buttons={};self.page_names=[x[0] for x in PAGES]
        for index,(key,text,ico) in enumerate(PAGES):
            b=button(text,ico);b.setProperty('nav',True);b.setCheckable(True);b.setMinimumHeight(48);self.nav_group.addButton(b,index);self.nav_buttons[key]=b;nl.addWidget(b)
        nl.addStretch();nl.addWidget(label('慢慢来，\n一件一件完成。','muted'));body.addWidget(nav)
        self.stack=QStackedWidget();self.page_widgets={};self.scrolls={}
        for key,cls in [('home',HomePage),('focus',FocusPage),('interaction',InteractionPage),('shortcuts',ShortcutsPage),('usage',UsagePage),('settings',SettingsPage)]:
            page=cls(self);page.setObjectName('pageContent');area=QScrollArea();area.setWidgetResizable(True);area.setWidget(page);area.setFrameShape(QFrame.Shape.NoFrame)
            self.page_widgets[key]=page;self.scrolls[key]=area;self.stack.addWidget(area)
        body.addWidget(self.stack,1);outer.addLayout(body,1)
        self.status=label('正在连接桌宠…','muted');self.status.setMinimumHeight(24);outer.addWidget(self.status)
        self.navigation_shortcuts=[]
        for index,page in enumerate(self.page_names,1):
            shortcut=QShortcut(QKeySequence(f'Ctrl+{index}'),self);shortcut.activated.connect(lambda key=page:self.select_page(key));self.navigation_shortcuts.append(shortcut)
        self.nav_group.idClicked.connect(lambda index:self.select_page(self.page_names[index]));self.select_page('home')
        app=QApplication.instance();app.focusChanged.connect(self.focus_changed)
        self.watchdog=QTimer(self);self.watchdog.timeout.connect(self.check_pending);self.watchdog.start(1000)
        self.stack.setEnabled(preview)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # The scroll child's old minimum width must not prevent responsive stacking.
        available=max(0,event.size().width()-214)
        for columns in self.findChildren(CardColumns):
            columns.reflow(2 if available>=columns.breakpoint else 1)

    def select_page(self,page):
        aliases={'productivity':'focus','companion':'interaction','review':'usage'};page=aliases.get(page,page)
        if page not in self.page_widgets:return
        self.stack.setCurrentIndex(self.page_names.index(page));self.nav_buttons[page].setChecked(True)

    def keep_dialog(self,dialog):
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda result,d=dialog:self._release_dialog(d))
    def _release_dialog(self,dialog):
        if dialog in self.dialogs:self.dialogs.remove(dialog)
        dialog.deleteLater()

    def is_pending(self,widget):
        return any(ref and ref() is widget for _,ref,_,_,_ in self.pending.values())

    def dispatch(self,action,payload=None,source_button=None,on_success=None):
        payload=payload or {};key=action+'\0'+json.dumps(payload,sort_keys=True,ensure_ascii=False)
        if action=='window.editing':key+='\0'+uuid.uuid4().hex
        if key in self.pending_keys:return self.pending_keys[key]
        if self.preview:
            self.toast('界面预览：未连接真实数据，不执行操作。');return None
        request_id=uuid.uuid4().hex
        ref=weakref.ref(source_button) if source_button is not None else None
        self.pending[request_id]=(key,ref,on_success,time.monotonic(),False);self.pending_keys[key]=request_id
        if source_button is not None:source_button.setEnabled(False)
        try:self.send_command({'id':request_id,'action':action,'payload':payload})
        except Exception as exc:
            self.apply_result({'id':request_id,'ok':False,'error':'发送失败：'+str(exc)})
        return request_id

    def apply_result(self,message):
        widget=None
        pending=self.pending.pop(message.get('id'),None)
        if pending:
            key,ref,callback,_,_=pending;self.pending_keys.pop(key,None);widget=ref() if ref else None
            if widget is not None and isValid(widget):widget.setEnabled(True)
        else:callback=None
        if message.get('snapshot'):self.apply_snapshot(message['snapshot'])
        if not message.get('ok',False):
            error=str(message.get('error') or '操作没有完成，请重试。');self.toast(error,True)
            if widget is not None and isValid(widget) and isinstance(widget.window(),QDialog):
                dialog=widget.window();notice=getattr(dialog,'error',None) or getattr(dialog,'command_error',None)
                if notice is None:
                    notice=label('');notice.setStyleSheet('color:#ae5f76;');dialog.layout().insertWidget(0,notice);dialog.command_error=notice
                notice.setText(error)
        else:
            result=message.get('result')
            if isinstance(result,str) and result:self.toast(result)
            elif pending and not pending[0].startswith('window.editing'):self.toast('已更新。')
            if callback:
                try:callback(result)
                except RuntimeError:pass  # The user may already have dismissed the form.
        # Reapply state-dependent disabled buttons after releasing request lock.
        for page in self.page_widgets.values():page.update_snapshot(self.snapshot)
        self._lock_pending()

    def apply_snapshot(self,snapshot):
        if not isinstance(snapshot,dict) or snapshot.get('version',1)!=1:
            self.toast('不兼容的界面数据，请使用原版小屋。',True);return
        self.snapshot=snapshot;self.stack.setEnabled(True)
        for page in self.page_widgets.values():page.update_snapshot(snapshot)
        self._lock_pending()
        if self.status.text()=='正在连接桌宠…':self.toast('小汐在这里，慢慢来。')

    def _lock_pending(self):
        for _,ref,_,_,_ in self.pending.values():
            widget=ref() if ref else None
            if widget is not None and isValid(widget):widget.setEnabled(False)

    # Aliases useful for simple view adapters and older development harnesses.
    update_snapshot=apply_snapshot
    def show_result(self,request_id,ok,result=None,error=''):
        self.apply_result({'id':request_id,'ok':ok,'result':result,'error':error})

    def toast(self,text,error=False):
        self.status.setText(('提示：' if error else '')+str(text));self.status.setStyleSheet('color:#ae5f76;' if error else '')

    def check_pending(self):
        now=time.monotonic()
        for request_id,(key,ref,cb,started,warned) in list(self.pending.items()):
            if now-started>12 and not warned:
                self.pending[request_id]=(key,ref,cb,started,True)
                self.toast('操作结果尚未确认，请勿重复提交。可先收起窗口，稍后查看。',True)

    def focus_changed(self,old,new):
        editable=isinstance(new,(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox)) or (isinstance(new,QComboBox) and new.isEditable())
        # Dialogs also belong to this view; no text content leaves the widget here.
        if editable!=self.last_editing:
            self.last_editing=editable
            if not self.preview:self.dispatch('window.editing',{'editing':editable})

    @staticmethod
    def timer_remaining(snapshot):
        timer=snapshot.get('timer')
        if not timer:return 0
        if timer.get('paused'):return max(0,float(timer.get('remaining',0)))
        if 'remaining_seconds' in timer:return max(0,float(timer['remaining_seconds']))
        try:return max(0,(datetime.fromisoformat(timer['due'])-datetime.fromisoformat(snapshot.get('now') or datetime.now().isoformat())).total_seconds())
        except (ValueError,KeyError,TypeError):return 0

    def edit_favorites(self):
        d=QDialog(self);d.setWindowTitle('编辑常用操作');d.resize(500,430);l=QVBoxLayout(d);l.addWidget(label('最多选择四项；顺序沿用动作列表。','muted'))
        box=QListWidget();l.addWidget(box)
        for a in self.snapshot.get('actions',[]):
            item=QListWidgetItem(a['title']);item.setData(Qt.ItemDataRole.UserRole,a['id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if a['id'] in self.snapshot.get('favorites',[]) else Qt.CheckState.Unchecked);box.addItem(item)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);l.addWidget(buttons);buttons.rejected.connect(d.reject)
        def save():
            ids=[box.item(i).data(Qt.ItemDataRole.UserRole) for i in range(box.count()) if box.item(i).checkState()==Qt.CheckState.Checked]
            if len(ids)>4:QMessageBox.information(d,'常用操作','最多选择四项。');return
            self.dispatch('settings.favorites',{'ids':ids},buttons.button(QDialogButtonBox.StandardButton.Save),lambda result:d.accept())
        buttons.accepted.connect(save);self.keep_dialog(d);d.open()

    def show_actions(self):
        d=QDialog(self);d.setWindowTitle('全部已注册操作');d.resize(520,520);layout=QVBoxLayout(d)
        layout.addWidget(label('包含插件扩展操作；不可用的操作会显示为灰色。','muted'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();items=QVBoxLayout(content);scroll.setWidget(content);layout.addWidget(scroll)
        for action in self.snapshot.get('actions',[]):
            b=button(action['title'],'spark');b.setEnabled(action.get('enabled',True));b.clicked.connect(lambda checked=False,a=action['id'],w=b:self.dispatch('action.invoke',{'id':a},w));items.addWidget(b)
        items.addStretch();self.keep_dialog(d);d.open()

    def hideEvent(self,event):
        # Owned editors are top-level Qt windows: hide them too, but retain drafts.
        self.suspended_dialogs=[d for d in self.findChildren(QDialog) if isValid(d) and d.isVisible()]
        for dialog in self.suspended_dialogs:dialog.hide()
        if self.last_editing:self.focus_changed(None,None)
        super().hideEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        for dialog in self.suspended_dialogs:
            if isValid(dialog):dialog.show()
        self.suspended_dialogs=[]

    def show_history(self):
        d=QDialog(self);d.setWindowTitle('通知记录');d.resize(580,480);l=QVBoxLayout(d);l.addWidget(label('免打扰期间的提醒也会保留在这里。','muted'));history=QListWidget();l.addWidget(history)
        for event in reversed(self.snapshot.get('history',[])):
            history.addItem(str(event.get('at',''))+'  '+str(event.get('title',''))+'\n'+str(event.get('body','')))
        if not history.count():history.addItem('暂无通知。')
        close=button('关闭','close');close.clicked.connect(d.accept);l.addWidget(close);self.keep_dialog(d);d.open()

    def confirm_exit(self):
        answer=QMessageBox.question(self,'退出桌宠','退出后计时和提醒将停止运行。确定退出吗？',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self.dispatch('app.exit',{})

    def closeEvent(self,event):
        if self.last_editing and not self.preview:self.dispatch('window.editing',{'editing':False})
        self.last_editing=False
        if not self.preview:self.dispatch('window.close',{})
        if self.on_hide:self.on_hide()
        event.ignore();self.hide()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.close()
        else:super().keyPressEvent(event)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and event.position().y()<64:self.drag_origin=event.globalPosition().toPoint()-self.frameGeometry().topLeft()
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.drag_origin is not None and event.buttons()&Qt.MouseButton.LeftButton:self.move(event.globalPosition().toPoint()-self.drag_origin)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):self.drag_origin=None;super().mouseReleaseEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(8,0,-1):
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(91,66,112,max(1,12-i)))
            p.drawRoundedRect(QRectF(8-i/2,8-i/2,self.width()-16+i,self.height()-16+i),24,24)
        p.setPen(QColor('#d8c8e6'));p.setBrush(QColor('#fffaf6'));p.drawRoundedRect(QRectF(8,8,self.width()-16,self.height()-16),22,22);p.end()
