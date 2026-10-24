"""Allowlisted Qt-hub adapter. All persistence and actions run on the Tk thread.

The Qt process only receives plain snapshots. It cannot access arbitrary store
keys, import plugins, execute Python, or create its own timer/database state.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import math
import os
import re
import tempfile
import uuid

from desktop_pet import platform_win, apps
from desktop_pet.actions import CATEGORIES


class HubBackend:
    def __init__(self, app):
        self.app = app
        self.days = 1

    def plugin(self, key):
        plugin = self.app.plugins.plugins.get(key)
        if plugin is None:
            raise ValueError('此功能插件未运行，请在设置中检查并重启。')
        return plugin

    @staticmethod
    def text(value, name='内容', maximum=300):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            raise ValueError(f'{name}须为 1–{maximum} 个字符')
        return value.strip()

    @staticmethod
    def number(value, lower, upper):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f'数值须在 {lower}–{upper} 之间')
        return value

    @staticmethod
    def boolean(value):
        if not isinstance(value, bool):
            raise ValueError('开关值必须为 true 或 false')
        return value

    def _row(self, rows, value):
        key = self.text(value, '标识', 200)
        row = next((row for row in rows if row.get('id') == key), None)
        if row is None:
            raise ValueError('记录已被删除或更新，请刷新后重试。')
        return row

    def _usage(self):
        store = self.app.store
        result = {'days': self.days, 'enabled': store.get('plugin.usage.enabled', True),
                  'total': 0, 'daily': [], 'records': [], 'categories': [], 'error': None,
                  'break_minutes': store.get('plugin.usage.break_minutes', 50),
                  'category_choices': [{'id': key, 'label': label} for key, label in apps.CATEGORY_LABELS.items()]}
        try:
            totals, groups = {}, {}
            plugin = self.app.plugins.plugins.get('usage')
            limits = plugin._limits_by_id() if plugin else {}
            for offset in reversed(range(self.days)):
                day = (datetime.now() - timedelta(days=offset)).date().isoformat()
                rows = store.usage_records(day)
                result['daily'].append({'day': day, 'seconds': sum(r.seconds for r in rows)})
                for row in rows:
                    item = totals.setdefault(row.id, {'id': row.id, 'display': row.display,
                        'category': row.label, 'seconds': 0, 'limit': limits.get(row.id, 0)})
                    item['seconds'] += row.seconds
            result['records'] = sorted(totals.values(), key=lambda r: -r['seconds'])
            result['total'] = sum(r['seconds'] for r in result['records'])
            for item in result['records']:
                groups[item['category']] = groups.get(item['category'], 0) + item['seconds']
            result['categories'] = [{'name': name, 'seconds': seconds} for name, seconds in sorted(groups.items(), key=lambda pair: -pair[1])]
        except Exception as exc:
            result.update(error=f'读取统计失败：{type(exc).__name__}: {exc}', total=None)
        return result

    def snapshot(self):
        app, store = self.app, self.app.store
        actions = []
        for action in app.registry.items.values():
            try:
                enabled = bool(app.registry.available(action))
                title = str(action.title)
            except Exception:
                enabled, title = False, str(action.id)
            actions.append({'id': action.id, 'title': title, 'category': action.category, 'enabled': enabled})
        disabled = store.get('disabled_plugins', [])
        plugins = [{**record, 'enabled': record['id'] not in disabled} for record in app.plugins.records]
        data = getattr(getattr(app, 'dialogue', None), 'data', {})
        try:
            startup = platform_win.startup_enabled()
        except Exception:
            startup = False
        value = {
            'version': 1, 'now': datetime.now().isoformat(),
            'timer': store.get('plugin.productivity.timer'),
            'timer_revision': store.get('plugin.productivity.timer_revision', 0),
            'focused': bool(app.focused), 'dnd': bool(store.get('dnd', False)),
            'todos': store.get('plugin.productivity.todos', []),
            'reminders': store.get('plugin.productivity.reminders', []),
            'shortcuts': store.get('plugin.shortcuts.items', []),
            'actions': actions, 'favorites': app.favorite_ids(), 'usage': self._usage(),
            'settings': {'behavior': store.get('pet.behavior', {}),
                         'speech': store.get('companion.speech', True),
                         'pet_visible': not app.pet_hidden, 'scale': getattr(app, 'live2d_scale', .8),
                         'double_click': store.get('navigation.double_click', 'companion.greeting'),
                         'favorite_hotkeys': store.get('navigation.favorite_hotkeys', False),
                         'startup': startup, 'live2d_mode': bool(getattr(app, 'live2d_mode', False)),
                         'hotkey_registered': bool(getattr(getattr(app, 'hotkey', None), 'registered', False))},
            'plugins': plugins, 'history': list(getattr(app, 'history', [])),
            'summary': {'focus_minutes': store.event_sum(datetime.now().date().isoformat(), 'focus_planned_minutes'),
                        'completed_todos': sum(1 for row in store.get('plugin.productivity.todos', []) if (row.get('completed') or '').startswith(datetime.now().date().isoformat()))},
            'language': {'events': {key: value.get('lines', []) for key, value in data.get('events', {}).items()},
                         'actions': data.get('actions', {})},
        }
        # Assert the adapter never leaks callback/widget objects into IPC.
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))

    def execute(self, command, payload=None):
        if not isinstance(command, str) or not isinstance(payload, (dict, type(None))):
            raise ValueError('无效操作格式')
        p = payload or {}
        app, store = self.app, self.app.store
        if command == 'action.invoke':
            key = self.text(p.get('id'), '操作', 200)
            # Existing Tk system callbacks show modal errors and swallow them.
            # The Qt caller needs a real result while retaining registry gating.
            if key in ('shortcuts.mute', 'shortcuts.volume_up', 'shortcuts.volume_down', 'shortcuts.lock'):
                action = app.registry.items.get(key)
                if action is None or not app.registry.available(action):
                    raise ValueError('此操作当前不可用，请检查插件状态。')
                return platform_win.system_action(key.split('.', 1)[1])
            return app.registry.invoke(key)
        if command.startswith('timer.'):
            plugin = self.plugin('productivity')
            if command == 'timer.start':
                plugin.start_focus(self.number(p.get('minutes', 25), 1, 240))
            elif command in ('timer.pause', 'timer.resume'):
                timer = plugin.timer.current
                if not timer:
                    raise ValueError('当前没有计时')
                # Intent, not blind toggle: repeat clicks must not undo themselves.
                desired = command == 'timer.pause'
                if bool(timer.get('paused')) != desired:
                    plugin.toggle_pause()
            elif command == 'timer.stop':
                plugin.stop_focus()
            elif command == 'timer.break':
                plugin.start_break()
            else:
                raise ValueError('未知计时操作')
            return '计时已更新'
        if command.startswith('todo.'):
            plugin = self.plugin('productivity')
            rows = plugin.ctx.get('todos', [])
            if command == 'todo.save':
                title = self.text(p.get('title'), '待办', 300)
                if p.get('id'):
                    self._row(rows, p['id'])['title'] = title
                else:
                    rows.append({'id': uuid.uuid4().hex, 'title': title, 'done': False, 'completed': None})
            elif command == 'todo.toggle':
                row = self._row(rows, p.get('id'))
                done = self.boolean(p.get('done'))
                was_done = bool(row.get('done'))
                row.update(done=done, completed=(row.get('completed') or datetime.now().isoformat()) if done else None)
            elif command == 'todo.delete':
                self._row(rows, p.get('id'))
                rows = [row for row in rows if row['id'] != p['id']]
            else:
                raise ValueError('未知待办操作')
            plugin.ctx.set('todos', rows)
            plugin.refresh()
            if command == 'todo.toggle' and done and not was_done:
                plugin.ctx.emit('success')
            return '待办已更新'
        if command.startswith('reminder.'):
            plugin = self.plugin('productivity')
            rows = plugin.ctx.get('reminders', [])
            if command == 'reminder.save':
                title = self.text(p.get('title'), '提醒', 300)
                interval = self.number(p.get('interval', 0), 0, 525600)
                if p.get('due'):
                    due = datetime.fromisoformat(self.text(p['due'], '时间', 80))
                    if due.tzinfo is not None:
                        raise ValueError('请使用本机时间，不包含时区后缀')
                    self.number((due - datetime.now()).total_seconds() / 60, .001, 525600)
                else:
                    minutes = self.number(p.get('minutes'), .001, 525600)
                    due = datetime.now() + timedelta(minutes=minutes)
                row = self._row(rows, p['id']) if p.get('id') else {'id': uuid.uuid4().hex}
                row.update(title=title, due=due.isoformat(), interval=interval, done=False)
                if not p.get('id'):
                    rows.append(row)
            elif command == 'reminder.delete':
                self._row(rows, p.get('id'))
                rows = [row for row in rows if row['id'] != p['id']]
            elif command == 'reminder.snooze':
                row = self._row(rows, p.get('id'))
                # A separate one-shot preserves the repeating reminder schedule.
                rows.append({'id': uuid.uuid4().hex, 'title': row['title'],
                             'due': (datetime.now() + timedelta(minutes=5)).isoformat(), 'interval': 0, 'done': False})
            else:
                raise ValueError('未知提醒操作')
            plugin.ctx.set('reminders', rows)
            plugin.refresh()
            return '提醒已更新'
        if command.startswith('shortcut.'):
            plugin = self.plugin('shortcuts')
            rows = plugin.items()
            if command == 'shortcut.launch':
                return plugin.launch(self._row(rows, p.get('id')))
            if command == 'shortcut.save':
                name = self.text(p.get('name'), '名称', 120)
                target = self.text(p.get('target'), '目标', 4096)
                kind = p.get('kind', '入口')
                if kind not in ('入口', '场景'):
                    raise ValueError('未知入口类型')
                if kind == '场景':
                    available = {row['name'] for row in rows if row['kind'] == '入口'}
                    names = [name.strip() for name in re.split('[,，]', target) if name.strip()]
                    if not names or any(name not in available for name in names):
                        raise ValueError('场景只能包含已有快捷入口的名称')
                    target = ', '.join(names)
                if p.get('id'):
                    self._row(rows, p['id']).update(name=name, target=target, kind=kind)
                else:
                    rows.append({'id': uuid.uuid4().hex, 'name': name, 'target': target, 'kind': kind})
            elif command == 'shortcut.delete':
                self._row(rows, p.get('id'))
                rows = [row for row in rows if row['id'] != p['id']]
            else:
                raise ValueError('未知快捷操作')
            plugin.save(rows)
            return '快捷入口已更新'
        if command.startswith('usage.'):
            plugin = self.plugin('usage')
            if command == 'usage.range':
                if type(p.get('days')) is not int or p['days'] not in (1, 7, 30):
                    raise ValueError('统计范围仅支持 1、7、30 天')
                self.days = p['days']
            elif command == 'usage.enabled':
                plugin.ctx.set('enabled', self.boolean(p.get('enabled')))
                plugin.last_app = None
                plugin.continuous = 0
            elif command in ('usage.category', 'usage.limit'):
                key = self.text(p.get('id'), '应用', 400)
                # Only a displayed, known canonical id may be modified.
                if key not in {row['id'] for row in self._usage()['records']}:
                    raise ValueError('应用不在当前统计中，请刷新后再试')
                field = 'categories' if command.endswith('category') else 'limits'
                values = plugin.ctx.get(field, {}) or {}
                if field == 'categories':
                    category = self.text(p.get('category'), '分类', 40)
                    category = apps.LABEL_TO_CATEGORY.get(category, category)
                    if category not in apps.CATEGORIES:
                        raise ValueError('请选择已有分类')
                    values[key] = category
                else:
                    values[key] = self.number(p.get('minutes'), 0, 1440)
                plugin.ctx.set(field, values)
                if field == 'limits':
                    plugin.alerted.discard((datetime.now().date().isoformat(), key))
            elif command == 'usage.break':
                plugin.ctx.set('break_minutes', self.number(p.get('minutes'), 0, 1440))
                plugin.continuous = 0
            else:
                raise ValueError('未知统计操作')
            plugin.refresh()
            return '统计设置已更新'
        if command.startswith('settings.'):
            return self._settings(command, p)
        if command == 'plugin.enabled':
            key = self.text(p.get('id'), '插件', 100)
            if key not in {r['id'] for r in app.plugins.records}:
                raise ValueError('未知插件')
            disabled = set(store.get('disabled_plugins', []))
            if self.boolean(p.get('enabled')):
                disabled.discard(key)
            else:
                disabled.add(key)
            store.set('disabled_plugins', sorted(disabled))
            return '插件设置已保存，重启后生效'
        if command in ('language.save', 'language.preview'):
            self.plugin('companion')
            kind, key = p.get('kind'), p.get('key')
            if kind not in ('events', 'actions') or key not in app.dialogue.data.get(kind, {}):
                raise ValueError('未知台词分类')
            if command == 'language.preview':
                return self.plugin('companion').perform(key) if kind == 'actions' else app.react(key, force=True)
            lines = p.get('lines')
            if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
                raise ValueError('请保留 1–100 条台词')
            limit = 40 if kind == 'actions' else 120
            lines = [self.text(line, '台词', limit) for line in lines]
            data = deepcopy(app.dialogue.data)
            if kind == 'actions':
                data[kind][key] = lines
            else:
                data[kind][key]['lines'] = lines
            path = store.directory / 'language-zh-CN.json'
            fd, temporary = tempfile.mkstemp(prefix='.language-', suffix='.json', dir=store.directory)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            app.dialogue.path = path
            app.dialogue.reload()
            return '台词已保存'
        if command == 'command.run':
            return app.plugins.command(self.text(p.get('text'), '指令', 1000))
        if command == 'legacy.open':
            page = p.get('page')
            if page not in CATEGORIES:
                raise ValueError('未知页面')
            app.show_panel(page)
            return '已打开完整兼容面板'
        if command == 'data.open':
            return platform_win.open_target(store.directory)
        if command == 'plugins.open':
            return platform_win.open_target(app.resource('plugins'))
        if command == 'app.exit':
            # Deferred so the transport can acknowledge before it is closed.
            app.root.after(100, app.close)
            return '正在退出'
        if command == 'window.editing':
            app.qt_hub_editing = self.boolean(p.get('editing'))
            return None
        if command == 'window.close':
            app.close_hub()
            return None
        raise ValueError('不支持的操作：' + command)

    def _settings(self, command, p):
        app, store = self.app, self.app.store
        if command == 'settings.focused':
            app.focused = self.boolean(p.get('enabled'))
        elif command == 'settings.dnd':
            enabled = self.boolean(p.get('enabled'))
            app.notifications.set_dnd(enabled)
            if enabled and app.bubble:
                app.bubble.destroy()
                app.bubble = None
                if app.live2d and app.live2d.ready:
                    app.live2d.state(notificationBusy=False, speechMs=0)
        elif command == 'settings.speech':
            store.set('companion.speech', self.boolean(p.get('enabled')))
        elif command == 'settings.behavior':
            key = p.get('key')
            if key not in ('breathe', 'blink', 'wings', 'hair', 'mouth', 'actions'):
                raise ValueError('未知行为选项')
            values = store.get('pet.behavior', {})
            values[key] = self.boolean(p.get('enabled'))
            store.set('pet.behavior', values)
        elif command == 'settings.visible':
            app.set_pet_hidden(not self.boolean(p.get('visible')))
        elif command == 'settings.scale':
            if not app.live2d_mode:
                raise ValueError('此大小设置仅适用于 Live2D 角色')
            value = self.number(p.get('scale'), .5, 1.25)
            old_w, old_h = app.pet_width, app.pet_height
            previous_scale = app.live2d_scale
            try:
                app.live2d_scale = value
                new_w, new_h = app.live2d_size()
            finally:
                app.live2d_scale = previous_scale
            new_x = max(0, min(app.pet_x + (old_w - new_w) // 2, app.root.winfo_screenwidth() - new_w))
            new_y = max(0, min(app.pet_y + old_h - new_h, app.root.winfo_screenheight() - new_h))
            store.write_batch({'live2d.scale': value, 'pet_position': [new_x, new_y]})
            app.live2d_scale = value
            app.pet_width, app.pet_height = new_w, new_h
            app.pet_x, app.pet_y = new_x, new_y
            app.pet.geometry(f'{new_w}x{new_h}+{new_x}+{new_y}')
            if app.live2d:
                app.live2d.resize((new_w, new_h), (new_x, new_y))
        elif command == 'settings.favorites':
            ids = p.get('ids')
            if not isinstance(ids, list) or len(ids) > 4 or any(not isinstance(key, str) or key not in app.registry.items for key in ids) or len(set(ids)) != len(ids):
                raise ValueError('请选择最多四项不同的已有操作')
            store.set('navigation.favorites', ids)
        elif command == 'settings.double_click':
            key = p.get('id')
            if key not in {a.id for a in app.registry.category('companion')}:
                raise ValueError('双击操作须为已有互动动作')
            store.set('navigation.double_click', key)
        elif command == 'settings.favorite_hotkeys':
            store.set('navigation.favorite_hotkeys', self.boolean(p.get('enabled')))
            return '已保存，快捷键设置重启后生效'
        elif command == 'settings.startup':
            if not app.set_startup_enabled(self.boolean(p.get('enabled'))):
                raise ValueError('开机启动设置失败')
        else:
            raise ValueError('未知设置操作')
        return '设置已更新'
