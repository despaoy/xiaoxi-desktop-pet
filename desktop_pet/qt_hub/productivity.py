"""Productivity and shortcuts views. All changes are dispatched to the Tk host.

Editors own their unsaved values: incoming snapshots only refresh tables, never
recreate an open dialog. No store, filesystem mutation, or command execution is
performed in this process.
"""
from __future__ import annotations

from datetime import datetime
import json
import re
from functools import partial

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QSpinBox,
    QProgressBar, QDialog, QDialogButtonBox, QLineEdit, QFormLayout, QComboBox,
    QCheckBox, QDateTimeEdit, QListWidget, QListWidgetItem, QMessageBox,
    QFileDialog, QStackedWidget,
)
from .common import button, label, duration, Scene, CardColumns


def _card(title):
    frame = QFrame()
    frame.setObjectName('cozyCard')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14,12,14,12)
    layout.setSpacing(8)
    layout.addWidget(label(title, 'cardTitle'))
    return frame, layout


def _row(*widgets):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    return container


def _table(headers, height=180):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().hide()
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)
    table.setShowGrid(False)
    table.setFixedHeight(min(height,145))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return table


def _selected(table):
    row = table.currentRow()
    item = table.item(row, 0) if row >= 0 else None
    return item.data(Qt.ItemDataRole.UserRole) if item else None


def _fill_table(table, rows):
    selected_id = _selected(table)
    table.setRowCount(len(rows))
    selected_row = -1
    for index, (key, values) in enumerate(rows):
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column == 0:
                item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(str(value))
            table.setItem(index, column, item)
        table.setRowHeight(index, 44)
        if key == selected_id:
            selected_row = index
    if selected_row >= 0:
        table.selectRow(selected_row)
    elif rows:
        table.selectRow(0)


def _confirm(parent, title, text):
    return QMessageBox.question(parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


class Editor(QDialog):
    """Nonmodal single editor retained until the host acknowledges its save."""
    def __init__(self, page, title):
        super().__init__(page)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.page = page
        self.owner = page.owner
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(410)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(24, 24, 24, 24)
        self.outer.setSpacing(14)
        self.outer.addWidget(label(title, 'cardTitle'))
        self.form = QFormLayout()
        self.form.setSpacing(12)
        self.outer.addLayout(self.form)
        self.error = label('', 'error')
        self.error.setWordWrap(True)
        self.outer.addWidget(self.error)
        self.save_button = button('保存', 'check', primary=True)
        self.cancel_button = button('取消', 'close')
        self.cancel_button.clicked.connect(self.reject)
        self.outer.addWidget(_row(self.cancel_button, self.save_button))
        self.pending = False

    def submit(self, command, payload):
        if not self.save_button.isEnabled():
            return
        self.error.clear()
        # Keep the dialog on failure; owner reports errors and re-enables source.
        # A local timer isn't needed: pending requests are tracked by the owner.
        def saved(*_):
            self.pending = False
            self.accept()
        request_id = self.owner.dispatch(command, payload, source_button=self.save_button,
                                         on_success=saved)
        if request_id is None:
            self.pending = False
        return request_id

    def reset_failed(self):
        self.pending = False
        self.save_button.setEnabled(True)

    def showEvent(self, event):
        super().showEvent(event)
        self.pending = False


class FocusPage(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.snapshot = {}
        self._todos_signature = None
        self._reminders_signature = None
        self._editors = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.addWidget(label('专注与事项', 'title'))
        outer.addWidget(label('把注意力放在重要的事上，一点一点变得更好。', 'muted'))
        scene = Scene('focus', '慢慢来，我陪你专心做好这一件事。', compact=True)
        scene.setFixedHeight(86)
        outer.addWidget(scene)
        timer_card, content = _card('当前专注')
        mode_row = QHBoxLayout()
        self.status = label('暂时没有计时，先选一个舒服的时长。', 'muted')
        self.focus_mode = QCheckBox('专注模式')
        self.focus_mode.toggled.connect(self._set_focus_mode)
        mode_row.addWidget(self.status, 1)
        mode_row.addWidget(self.focus_mode)
        content.addLayout(mode_row)
        self.clock = label('25:00', 'timer');self.clock.setStyleSheet('font-size:40px;font-weight:600;')
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(self.clock)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        content.addWidget(self.progress)
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 240)
        self.minutes.setValue(25)
        self.minutes.setSuffix(' 分钟')
        self.minutes.setAccessibleName('专注时长')
        self.start_button = button('开始专注', 'clock', primary=True)
        self.pause_button = button('暂停', 'pause')
        self.resume_button = button('继续', 'play')
        self.stop_button = button('结束', 'stop')
        self.break_button = button('休息 5 分钟', 'leaf')
        self.start_button.clicked.connect(lambda: self.owner.dispatch('timer.start', {'minutes': self.minutes.value()}, self.start_button))
        self.pause_button.clicked.connect(lambda: self.owner.dispatch('timer.pause', {}, self.pause_button))
        self.resume_button.clicked.connect(lambda: self.owner.dispatch('timer.resume', {}, self.resume_button))
        self.stop_button.clicked.connect(self._stop)
        self.break_button.clicked.connect(lambda: self.owner.dispatch('timer.break', {}, self.break_button))
        content.addWidget(_row(self.minutes,self.start_button,self.break_button))
        content.addWidget(_row(self.pause_button,self.resume_button,self.stop_button))
        timer_card.setToolTip('计时完成记录计划时长，不代表实际注意力；完成计时不会自动勾选待办。')
        self.daily_summary=label('', 'muted')

        todo_card, content = _card('今日待办')
        self.todo_table = _table(['事项', '状态'])
        self.todo_table.setAccessibleName('待办列表')
        self.todo_table.itemDoubleClicked.connect(lambda *_: self._todo_editor())
        content.addWidget(self.todo_table)
        self.todo_empty = label('还没有待办。写下一件小事，就从这里开始。', 'muted')
        content.addWidget(self.todo_empty)
        add = button('添加', 'plus'); add.clicked.connect(lambda: self._todo_editor(create=True))
        edit = button('编辑', 'edit'); edit.clicked.connect(lambda: self._todo_editor())
        toggle = button('完成/恢复', 'check'); toggle.clicked.connect(self._toggle_todo)
        delete = button('删除', 'trash'); delete.clicked.connect(self._delete_todo)
        self.todo_selection_buttons = [edit, toggle, delete]
        self.todo_table.itemSelectionChanged.connect(self._selection_state)
        content.addWidget(_row(add,edit,toggle,delete))
        outer.addWidget(CardColumns(timer_card,todo_card))
        outer.addWidget(self.daily_summary)

        reminders_card, content = _card('我的提醒')
        self.reminder_table = _table(['内容', '下次提醒', '重复 / 状态'])
        self.reminder_table.setFixedHeight(86)
        self.reminder_table.setAccessibleName('提醒列表')
        self.reminder_table.itemDoubleClicked.connect(lambda *_: self._reminder_editor())
        content.addWidget(self.reminder_table)
        self.reminder_empty = label('暂无提醒。单次和重复提醒可以在同一张表单里设置。', 'muted')
        content.addWidget(self.reminder_empty)
        add_reminder = button('添加提醒', 'plus'); add_reminder.clicked.connect(lambda: self._reminder_editor(create=True))
        edit_reminder = button('编辑', 'edit'); edit_reminder.clicked.connect(lambda: self._reminder_editor())
        snooze = button('稍后 5 分钟', 'clock'); snooze.clicked.connect(self._snooze)
        delete_reminder = button('删除', 'trash'); delete_reminder.clicked.connect(self._delete_reminder)
        self.reminder_selection_buttons = [edit_reminder, snooze, delete_reminder]
        self.reminder_table.itemSelectionChanged.connect(self._selection_state)
        content.addWidget(_row(add_reminder, edit_reminder, snooze, delete_reminder))
        content.addWidget(label('程序运行时触发提醒；免打扰期间仅进入通知记录。', 'muted'))
        outer.addWidget(reminders_card)
        outer.addStretch()
        self._selection_state()

    def _set_focus_mode(self, value):
        self.owner.dispatch('settings.focused', {'enabled': bool(value)}, self.focus_mode)

    def _stop(self):
        if _confirm(self, '结束当前计时', '结束这一轮计时？未到期的一轮不会计入完成记录。'):
            self.owner.dispatch('timer.stop', {}, self.stop_button)

    def _selection_state(self):
        for widget in getattr(self, 'todo_selection_buttons', []):
            widget.setEnabled(_selected(self.todo_table) is not None)
        for widget in getattr(self, 'reminder_selection_buttons', []):
            widget.setEnabled(_selected(self.reminder_table) is not None)

    def _selected_row(self, key, table):
        selected = _selected(table)
        return next((row for row in self.snapshot.get(key, []) if row.get('id') == selected), None)

    def _show_editor(self, editor):
        self._editors.append(editor)
        editor.finished.connect(lambda *_: self._editors.remove(editor) if editor in self._editors else None)
        editor.open()

    def _todo_editor(self, create=False):
        item = None if create else self._selected_row('todos', self.todo_table)
        if not create and item is None:
            return
        editor = Editor(self, '添加待办' if create else '编辑待办')
        title = QLineEdit(item.get('title', '') if item else '')
        title.setMaxLength(200)
        title.setPlaceholderText('写下一件想完成的小事')
        editor.form.addRow('事项', title)
        def save():
            if not title.text().strip():
                editor.error.setText('请填写事项。'); title.setFocus(); return
            payload = {'title': title.text().strip()}
            if item: payload['id'] = item['id']
            editor.submit('todo.save', payload)
        editor.save_button.clicked.connect(save)
        title.returnPressed.connect(save)
        self._show_editor(editor)
        title.setFocus()

    def _toggle_todo(self):
        item = self._selected_row('todos', self.todo_table)
        if item:
            self.owner.dispatch('todo.toggle', {'id': item['id'], 'done': not item.get('done', False)}, self.todo_selection_buttons[1])

    def _delete_todo(self):
        item = self._selected_row('todos', self.todo_table)
        if item and _confirm(self, '删除待办', '删除“' + item['title'] + '”？'):
            self.owner.dispatch('todo.delete', {'id': item['id']}, self.todo_selection_buttons[2])

    def _reminder_editor(self, create=False):
        item = None if create else self._selected_row('reminders', self.reminder_table)
        if not create and item is None:
            return
        editor = Editor(self, '添加提醒' if create else '编辑提醒')
        title = QLineEdit(item.get('title', '') if item else '')
        title.setMaxLength(200)
        editor.form.addRow('提醒内容', title)
        when = QComboBox(); when.addItems(['多少分钟后', '指定日期时间'])
        editor.form.addRow('时间方式', when)
        minutes = QSpinBox(); minutes.setRange(1, 525600); minutes.setValue(30); minutes.setSuffix(' 分钟后')
        when_at = QDateTimeEdit(QDateTime.currentDateTime().addSecs(1800))
        when_at.setCalendarPopup(True); when_at.setDisplayFormat('yyyy-MM-dd HH:mm')
        stack = QStackedWidget(); stack.addWidget(minutes); stack.addWidget(when_at)
        when.currentIndexChanged.connect(stack.setCurrentIndex)
        editor.form.addRow('首次提醒', stack)
        repeat = QCheckBox('重复提醒')
        interval = QSpinBox(); interval.setRange(1, 525600); interval.setValue(60); interval.setSuffix(' 分钟一次')
        interval.setEnabled(False); repeat.toggled.connect(interval.setEnabled)
        editor.form.addRow('重复', _row(repeat, interval))
        if item:
            dt = QDateTime.fromString(item.get('due', ''), Qt.DateFormat.ISODate)
            if dt.isValid(): when_at.setDateTime(dt); when.setCurrentIndex(1)
            repeat.setChecked(bool(item.get('interval', 0)))
            interval.setValue(max(1, int(item.get('interval') or 60)))
        def save():
            if not title.text().strip(): editor.error.setText('请填写提醒内容。'); return
            payload = {'title': title.text().strip(), 'interval': interval.value() if repeat.isChecked() else 0}
            if when.currentIndex() == 0:
                payload['minutes'] = minutes.value()
            else:
                if when_at.dateTime() <= QDateTime.currentDateTime():
                    editor.error.setText('请选择未来的日期与时间。'); return
                payload['due'] = when_at.dateTime().toPython().isoformat()
            if item: payload['id'] = item['id']
            editor.submit('reminder.save', payload)
        editor.save_button.clicked.connect(save)
        self._show_editor(editor)
        title.setFocus()

    def _snooze(self):
        item = self._selected_row('reminders', self.reminder_table)
        if item: self.owner.dispatch('reminder.snooze', {'id': item['id']}, self.reminder_selection_buttons[1])

    def _delete_reminder(self):
        item = self._selected_row('reminders', self.reminder_table)
        if item and _confirm(self, '删除提醒', '删除“' + item['title'] + '”？'):
            self.owner.dispatch('reminder.delete', {'id': item['id']}, self.reminder_selection_buttons[2])

    def update_snapshot(self, snapshot):
        self.snapshot = snapshot
        summary=snapshot.get('summary',{});records=snapshot.get('usage',{}).get('records',[])
        self.daily_summary.setText(f"今日小结 · 已安排专注 {summary.get('focus_minutes',0)} 分钟 · 完成待办 {summary.get('completed_todos',0)} 项"+(' · 最常用：'+records[0].get('display','') if records else ''))
        timer = snapshot.get('timer')
        focused = bool(snapshot.get('focused'))
        self.focus_mode.blockSignals(True); self.focus_mode.setChecked(focused); self.focus_mode.blockSignals(False)
        if timer:
            if timer.get('paused'):
                remaining = max(0, float(timer.get('remaining', 0)))
            elif 'remaining_seconds' in timer:
                remaining = max(0, float(timer['remaining_seconds']))
            else:
                try:
                    now = datetime.fromisoformat(snapshot.get('now', datetime.now().isoformat()))
                    remaining = max(0, (datetime.fromisoformat(timer['due']) - now).total_seconds())
                except (TypeError, ValueError, KeyError): remaining = 0
            total = max(1, float(timer.get('minutes', 25)) * 60)
            self.clock.setText(duration(remaining))
            self.status.setText(str(timer.get('kind', '专注')) + (' · 已暂停' if timer.get('paused') else ' · 正在进行'))
            self.progress.setValue(int(min(1000, max(0, (total - remaining) / total * 1000))))
        else:
            self.clock.setText(duration(self.minutes.value() * 60))
            self.status.setText('暂时没有计时，先选一个舒服的时长。')
            self.progress.setValue(0)
        self.start_button.setEnabled(not timer)
        self.minutes.setEnabled(not timer)
        self.pause_button.setEnabled(bool(timer and not timer.get('paused')))
        self.resume_button.setEnabled(bool(timer and timer.get('paused')))
        self.stop_button.setEnabled(bool(timer))
        self.break_button.setEnabled(not timer)
        todos = snapshot.get('todos', [])
        signature = json.dumps(todos, sort_keys=True, ensure_ascii=False)
        if signature != self._todos_signature:
            self._todos_signature = signature
            _fill_table(self.todo_table, [(x['id'], [x.get('title', ''), '已完成' if x.get('done') else '待完成']) for x in todos])
            self.todo_empty.setVisible(not todos)
        reminders = snapshot.get('reminders', [])
        signature = json.dumps(reminders, sort_keys=True, ensure_ascii=False)
        if signature != self._reminders_signature:
            self._reminders_signature = signature
            rows = []
            for item in reminders:
                due = item.get('due', '')
                try: due = datetime.fromisoformat(due).strftime('%m-%d %H:%M')
                except (ValueError, TypeError): pass
                state = ('每 %s 分钟' % item['interval']) if item.get('interval') else '单次'
                if item.get('done'): state += ' · 已提醒'
                rows.append((item['id'], [item.get('title', ''), due, state]))
            _fill_table(self.reminder_table, rows)
            self.reminder_empty.setVisible(not reminders)
        self._selection_state()


class ShortcutsPage(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.snapshot = {}
        self._signature = None
        self._editors = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.addWidget(label('快捷工具', 'title'))
        outer.addWidget(label('常用的东西，都在手边。场景只打开你保存的入口，不执行额外脚本。', 'muted'))
        scene=Scene('interaction','需要的东西，我帮你放在手边。',compact=True);scene.setFixedHeight(86);outer.addWidget(scene)
        favorites, content = _card('常用收藏');content.setContentsMargins(14,10,14,10);content.setSpacing(5)
        self.favorite_row = QHBoxLayout()
        favorite_line=QHBoxLayout();favorite_line.addLayout(self.favorite_row,1);content.addLayout(favorite_line)
        edit_favorites = button('编辑四个收藏', 'star')
        edit_favorites.clicked.connect(self._favorites)
        self.favorite_edit_button=edit_favorites
        favorite_line.addWidget(edit_favorites)
        outer.addWidget(favorites)
        tools, content = _card('我的快捷入口')
        self.search = QLineEdit(); self.search.setPlaceholderText('搜索名称或目标…'); self.search.setClearButtonEnabled(True)
        self.filter = QComboBox(); self.filter.addItems(['全部', '应用', '文件', '文件夹', '网址'])
        self.search.textChanged.connect(self._fill_entries)
        self.filter.currentTextChanged.connect(self._fill_entries)
        content.addWidget(_row(self.search, self.filter))
        self.entries = _table(['名称', '类型', '目标'], 125)
        self.entries.itemDoubleClicked.connect(lambda *_: self._launch('入口'))
        content.addWidget(self.entries)
        self.entries_empty = label('还没有快捷入口。添加一个常用软件、文件、文件夹或网址。', 'muted')
        content.addWidget(self.entries_empty)
        add = button('添加入口', 'plus'); add.clicked.connect(lambda: self._entry_editor(create=True))
        edit = button('编辑', 'edit'); edit.clicked.connect(lambda: self._entry_editor())
        launch = button('打开', 'play', primary=True); launch.clicked.connect(lambda: self._launch('入口'))
        delete = button('删除', 'trash'); delete.clicked.connect(lambda: self._delete('入口'))
        self.entry_buttons = [edit, launch, delete]
        self.entries.itemSelectionChanged.connect(self._selection_state)
        content.addWidget(_row(add,launch,edit,delete))
        scenes, content = _card('工作场景')
        self.scenes = _table(['场景', '包含的入口'], 125)
        self.scenes.itemDoubleClicked.connect(lambda *_: self._launch('场景'))
        content.addWidget(self.scenes)
        self.scenes_empty = label('把已有入口组合起来，一次打开学习或工作的准备材料。', 'muted')
        content.addWidget(self.scenes_empty)
        add_scene = button('新建', 'plus'); add_scene.clicked.connect(lambda: self._scene_editor(create=True))
        edit_scene = button('编辑', 'edit'); edit_scene.clicked.connect(lambda: self._scene_editor())
        launch_scene = button('启动', 'play', primary=True); launch_scene.clicked.connect(lambda: self._launch('场景'))
        delete_scene = button('删除', 'trash'); delete_scene.clicked.connect(lambda: self._delete('场景'))
        self.scene_buttons = [edit_scene, launch_scene, delete_scene]
        self.scenes.itemSelectionChanged.connect(self._selection_state)
        content.addWidget(_row(add_scene,launch_scene,edit_scene,delete_scene))
        outer.addWidget(CardColumns(tools,scenes))
        system, content = _card('系统快捷')
        actions = []
        for title, key, symbol in [('音量 −', 'volume_down', 'minus'), ('音量 ＋', 'volume_up', 'plus'), ('静音 / 恢复', 'mute', 'sound'), ('锁定电脑', 'lock', 'lock')]:
            control = button(title, symbol)
            control.clicked.connect(partial(self._system, key, control))
            actions.append(control)
        self.system_buttons = actions
        content.addWidget(_row(*actions))
        outer.addWidget(system)
        outer.addStretch()
        self._selection_state()

    def _favorites(self):
        if hasattr(self.owner, 'edit_favorites'):
            self.owner.edit_favorites()
        else:
            self.owner.toast('请从小屋的常用操作设置中编辑收藏。')

    def _selected_row(self, kind):
        key = _selected(self.scenes if kind == '场景' else self.entries)
        return next((x for x in self.snapshot.get('shortcuts', []) if x.get('id') == key), None)

    def _selection_state(self):
        for widget in getattr(self, 'entry_buttons', []): widget.setEnabled(_selected(self.entries) is not None)
        for widget in getattr(self, 'scene_buttons', []): widget.setEnabled(_selected(self.scenes) is not None)

    def _show_editor(self, editor):
        self._editors.append(editor)
        editor.finished.connect(lambda *_: self._editors.remove(editor) if editor in self._editors else None)
        editor.open()

    def _entry_editor(self, create=False):
        item = None if create else self._selected_row('入口')
        if not create and item is None: return
        editor = Editor(self, '添加快捷入口' if create else '编辑快捷入口')
        name = QLineEdit(item.get('name', '') if item else ''); name.setMaxLength(100)
        target = QLineEdit(item.get('target', '') if item else ''); target.setMaxLength(4096)
        target.setPlaceholderText('完整文件路径、文件夹路径或 https:// 网址')
        editor.form.addRow('名称', name); editor.form.addRow('目标', target)
        file_btn = button('选择文件', 'file'); folder_btn = button('选择文件夹', 'folder')
        def choose_file():
            value, _ = QFileDialog.getOpenFileName(editor, '选择软件或文件')
            if value: target.setText(value)
        def choose_folder():
            value = QFileDialog.getExistingDirectory(editor, '选择文件夹')
            if value: target.setText(value)
        file_btn.clicked.connect(choose_file); folder_btn.clicked.connect(choose_folder)
        editor.form.addRow('', _row(file_btn, folder_btn))
        def save():
            if not name.text().strip() or not target.text().strip(): editor.error.setText('请填写名称和目标。'); return
            payload = {'name': name.text().strip(), 'target': target.text().strip(), 'kind': '入口'}
            if item: payload['id'] = item['id']
            editor.submit('shortcut.save', payload)
        editor.save_button.clicked.connect(save)
        self._show_editor(editor); name.setFocus()

    def _scene_editor(self, create=False):
        item = None if create else self._selected_row('场景')
        if not create and item is None: return
        entries = [x for x in self.snapshot.get('shortcuts', []) if x.get('kind') != '场景']
        editor = Editor(self, '新建工作场景' if create else '编辑工作场景')
        name = QLineEdit(item.get('name', '') if item else ''); name.setMaxLength(100)
        editor.form.addRow('场景名称', name)
        choices = QListWidget(); choices.setMinimumHeight(180)
        selected = set(re.split('[,，]', item.get('target', ''))) if item else set()
        selected = {x.strip() for x in selected}
        for entry in entries:
            choice = QListWidgetItem(entry['name'])
            choice.setFlags(choice.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            choice.setCheckState(Qt.CheckState.Checked if entry['name'] in selected else Qt.CheckState.Unchecked)
            choices.addItem(choice)
        editor.form.addRow('要打开的入口', choices)
        editor.form.addRow('', label('按上面的顺序打开。改名或删除入口后，请同步检查关联场景。', 'muted'))
        def save():
            names = [choices.item(i).text() for i in range(choices.count()) if choices.item(i).checkState() == Qt.CheckState.Checked]
            if not name.text().strip() or not names: editor.error.setText('请填写名称，并至少选择一个入口。'); return
            payload = {'name': name.text().strip(), 'target': ', '.join(names), 'kind': '场景'}
            if item: payload['id'] = item['id']
            editor.submit('shortcut.save', payload)
        editor.save_button.clicked.connect(save)
        self._show_editor(editor); name.setFocus()

    def _launch(self, kind):
        item = self._selected_row(kind)
        if item: self.owner.dispatch('shortcut.launch', {'id': item['id']}, (self.scene_buttons if kind == '场景' else self.entry_buttons)[1])

    def _delete(self, kind):
        item = self._selected_row(kind)
        if item and _confirm(self, '删除快捷入口', '只删除“' + item['name'] + '”的快捷记录，不删除原文件。继续？'):
            self.owner.dispatch('shortcut.delete', {'id': item['id']}, (self.scene_buttons if kind == '场景' else self.entry_buttons)[2])

    def _system(self, key, source, *_):
        if key == 'lock' and not _confirm(self, '锁定电脑', '现在锁定电脑？'):
            return
        self.owner.dispatch('action.invoke', {'id': 'shortcuts.' + key}, source)

    @staticmethod
    def _kind(item):
        target = item.get('target', '')
        lower = target.lower()
        if lower.startswith(('https://', 'http://')): return '网址'
        if lower.endswith(('.exe', '.app', '.lnk', '.bat', '.cmd')): return '应用'
        # Display-only classification: do not inspect the host's filesystem.
        last = re.split(r'[/\\]', target.rstrip('/\\'))[-1]
        return '文件' if '.' in last else '文件夹'

    def _fill_entries(self, *_):
        needle = self.search.text().strip().casefold()
        kind = self.filter.currentText()
        entries = [x for x in self.snapshot.get('shortcuts', []) if x.get('kind') != '场景']
        filtered = [x for x in entries if (kind == '全部' or self._kind(x) == kind) and
                    (not needle or needle in (x.get('name', '') + ' ' + x.get('target', '')).casefold())]
        _fill_table(self.entries, [(x['id'], [x.get('name', ''), self._kind(x), x.get('target', '')]) for x in filtered])
        self.entries_empty.setVisible(not filtered)
        self.entries_empty.setText('没有匹配的入口。' if entries else '还没有快捷入口。添加一个常用软件、文件、文件夹或网址。')
        self._selection_state()

    def update_snapshot(self, snapshot):
        self.snapshot = snapshot
        signature = json.dumps({key: snapshot.get(key) for key in ('shortcuts', 'favorites', 'actions')}, ensure_ascii=False, sort_keys=True)
        if signature == self._signature: return
        self._signature = signature
        self._fill_entries()
        scenes = [x for x in snapshot.get('shortcuts', []) if x.get('kind') == '场景']
        _fill_table(self.scenes, [(x['id'], [x.get('name', ''), x.get('target', '')]) for x in scenes])
        self.scenes_empty.setVisible(not scenes)
        while self.favorite_row.count():
            item = self.favorite_row.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        actions = {x['id']: x for x in snapshot.get('actions', [])}
        favorites = snapshot.get('favorites', [])
        for index, action_id in enumerate(favorites[:4]):
            action = actions.get(action_id)
            if action:
                control = button(f'{index + 1} · {action["title"]}', 'star')
                control.setEnabled(bool(action.get('enabled', True)))
                control.clicked.connect(lambda checked=False, key=action_id, source=control: self.owner.dispatch('action.invoke', {'id': key}, source))
                self.favorite_row.addWidget(control)
        if not favorites: self.favorite_row.addWidget(label('把常用操作放在这里。', 'muted'))
        self.favorite_row.addStretch()
        for control, key in zip(self.system_buttons, ('volume_down', 'volume_up', 'mute', 'lock')):
            action = actions.get('shortcuts.' + key)
            control.setEnabled(bool(action and action.get('enabled')))
        self._selection_state()
