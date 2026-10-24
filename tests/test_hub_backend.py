from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import test_core
from desktop_pet.actions import ActionRegistry, Action
from desktop_pet.hub_backend import HubBackend
from desktop_pet.plugin_api import PluginContext
from desktop_pet.qt_hub_host import QtHubHost


class BackendTests(unittest.TestCase):
    tearDown = test_core.CoreTests.tearDown

    def setUp(self):
        test_core.CoreTests.setUp(self)
        self.app.registry = ActionRegistry()
        self.usage = test_core.load('usage').Plugin(PluginContext(self.app, 'usage'))
        self.app.plugins.plugins.update(shortcuts=self.shortcuts, usage=self.usage)
        self.backend = HubBackend(self.app)

    def test_snapshot_plain_json_and_failed_stats_not_zero(self):
        import json
        self.app.plugins.records = [{'id': 'usage', 'status': 'running'}]
        self.app.favorite_ids = lambda: []
        self.app.pet_hidden = False
        self.app.history = [{'at': '10:00', 'title': 'test', 'body': 'hello'}]
        with patch('desktop_pet.platform_win.startup_enabled', return_value=False):
            data = self.backend.snapshot()
            self.assertEqual(json.loads(json.dumps(data)), data)
            self.assertIn('category_choices', data['usage'])
            with patch.object(self.store, 'usage_records', side_effect=OSError('disk')):
                failed = self.backend.snapshot()
            self.assertIsNone(failed['usage']['total'])
            self.assertIn('disk', failed['usage']['error'])

    def test_todo_crud_completion_and_undo(self):
        self.backend.execute('todo.save', {'title': '喝水'})
        row = self.store.get('plugin.productivity.todos')[0]
        self.backend.execute('todo.toggle', {'id': row['id'], 'done': True})
        done = self.store.get('plugin.productivity.todos')[0]
        self.assertTrue(done['completed'])
        self.backend.execute('todo.toggle', {'id': row['id'], 'done': True})
        self.assertEqual(done['completed'], self.store.get('plugin.productivity.todos')[0]['completed'])
        self.backend.execute('todo.toggle', {'id': row['id'], 'done': False})
        self.assertIsNone(self.store.get('plugin.productivity.todos')[0]['completed'])
        self.backend.execute('todo.save', {'id': row['id'], 'title': '伸展'})
        self.backend.execute('todo.delete', {'id': row['id']})
        self.assertEqual(self.store.get('plugin.productivity.todos'), [])

    def test_repeat_snooze_preserves_schedule(self):
        self.backend.execute('reminder.save', {'title': '休息', 'minutes': 1, 'interval': 60})
        row = self.store.get('plugin.productivity.reminders')[0]
        self.backend.execute('reminder.snooze', {'id': row['id']})
        rows = self.store.get('plugin.productivity.reminders')
        self.assertEqual(rows[0], row)
        self.assertEqual(rows[1]['interval'], 0)
        self.assertAlmostEqual((datetime.fromisoformat(rows[1]['due']) - datetime.now()).total_seconds(), 300, delta=2)

    def test_timer_intents_do_not_toggle_twice(self):
        self.backend.execute('timer.start', {'minutes': 25})
        for _ in range(2):
            self.backend.execute('timer.pause')
        self.assertTrue(self.productivity.timer.current['paused'])
        for _ in range(2):
            self.backend.execute('timer.resume')
        self.assertFalse(self.productivity.timer.current['paused'])
        self.backend.execute('timer.stop')
        self.assertIsNone(self.productivity.timer.current)

    def test_shortcut_save_does_not_launch_and_scene_is_validated(self):
        with patch('desktop_pet.platform_win.open_target') as opened:
            self.backend.execute('shortcut.save', {'name': '文档', 'target': self.temp.name})
            with self.assertRaises(ValueError):
                self.backend.execute('shortcut.save', {'name': '工作', 'target': '未知', 'kind': '场景'})
            self.backend.execute('shortcut.save', {'name': '工作', 'target': '文档', 'kind': '场景'})
            opened.assert_not_called()
            self.backend.execute('shortcut.launch', {'id': self.shortcuts.items()[1]['id']})
            opened.assert_called_once()

    def test_usage_category_limit_and_break(self):
        day = datetime.now().date().isoformat()
        self.store.add_usage(day, 'chrome.exe', 12)
        self.backend.execute('usage.category', {'id': 'chrome', 'category': '开发与工作'})
        self.assertEqual(self.store.get('plugin.usage.categories')['chrome'], 'dev')
        self.usage.alerted.add((day, 'chrome'))
        self.backend.execute('usage.limit', {'id': 'chrome', 'minutes': 20})
        self.assertNotIn((day, 'chrome'), self.usage.alerted)
        self.usage.continuous = 50
        self.backend.execute('usage.break', {'minutes': 0})
        self.assertEqual(self.usage.continuous, 0)
        with self.assertRaises(ValueError):
            self.backend.execute('usage.category', {'id': 'chrome', 'category': 'unknown'})

    def test_validation_no_arbitrary_mutation(self):
        for command, payload in [('store.set', {'key': 'x'}), ('timer.start', {'minutes': float('nan')}), ('timer.start', {'minutes': True}), ('todo.toggle', {'id': 'missing', 'done': True}), ('settings.favorites', {'ids': [{}]}), ('settings.behavior', {'key': '__dict__', 'enabled': True}), ('usage.range', {'days': True})]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.backend.execute(command, payload)
        self.assertIsNone(self.store.get('x'))

    def test_failed_scale_save_preserves_memory(self):
        self.app.live2d_mode = True
        self.app.live2d_scale = .8
        self.app.pet_width, self.app.pet_height = 180, 250
        self.app.pet_x, self.app.pet_y = 100, 100
        self.app.live2d_size = lambda: (200, 300)
        self.app.root = SimpleNamespace(winfo_screenwidth=lambda: 1920, winfo_screenheight=lambda: 1080)
        with patch.object(self.store, 'write_batch', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.backend.execute('settings.scale', {'scale': 1.0})
        self.assertEqual(self.app.live2d_scale, .8)
        self.assertEqual((self.app.pet_width, self.app.pet_height), (180, 250))

    def test_system_errors_propagate_without_touching_os(self):
        self.app.registry.add(Action('shortcuts.lock', 'shortcuts', '锁定', Mock()))
        with patch('desktop_pet.platform_win.system_action', side_effect=OSError('unsupported')) as action:
            with self.assertRaises(OSError):
                self.backend.execute('action.invoke', {'id': 'shortcuts.lock'})
            action.assert_called_once_with('lock')

    def test_self_pids_include_hub_not_external_apps(self):
        self.app.live2d = SimpleNamespace(process=SimpleNamespace(pid=1111))
        self.app.qt_hub_host = SimpleNamespace(process=SimpleNamespace(pid=2222))
        self.assertTrue({1111, 2222}.issubset(self.usage._self_pids()))
        self.assertNotIn(3333, self.usage._self_pids())


class HostTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(root=Mock(), qt_hub_editing=True)
        self.fallback = Mock()
        self.host = QtHubHost(self.app, self.fallback)
        self.host.backend = Mock()
        self.host.backend.execute.return_value = 'saved'

    def test_request_id_deduplicates_mutation(self):
        message = {'id': 'one', 'action': 'todo.save', 'payload': {'title': 'a'}}
        self.host.handle(message)
        self.host.handle(message)
        self.host.backend.execute.assert_called_once()
        self.assertEqual(self.host.outgoing.get(), self.host.outgoing.get())

    def test_errors_are_acknowledged_not_silent(self):
        self.host.backend.execute.side_effect = ValueError('invalid')
        self.host.handle({'id': 'x', 'action': 'bad'})
        response = self.host.outgoing.get()
        self.assertFalse(response['ok'])
        self.assertEqual(response['error'], 'invalid')

    def test_crash_recovers_legacy_once(self):
        self.host.process = Mock()
        self.host.process.is_alive.return_value = False
        self.host.visible = True
        self.host.poll()
        self.fallback.assert_called_once()
        self.assertTrue(self.fallback.call_args.args[1])
        self.assertTrue(self.host.closed)
        self.assertFalse(self.app.qt_hub_editing)
        self.host.poll()
        self.fallback.assert_called_once()

    def test_repeated_show_reuses_child_and_refresh_throttles(self):
        self.host.process = Mock()
        self.assertTrue(self.host.start())
        self.host.ready = self.host.visible = True
        self.host.refresh()
        self.host.refresh()
        self.host.backend.snapshot.assert_called_once()
        self.host.hide()
        self.host.refresh(force=True)
        self.host.backend.snapshot.assert_called_once()
        self.assertFalse(self.app.qt_hub_editing)

    def test_oversized_or_nonfinite_requests_rejected(self):
        for request in [{'id': 'x', 'payload': {'x': 'a'*65537}}, {'id': 'x', 'payload': {'x': float('nan')}}, {'id': None}]:
            with self.assertRaises(ValueError):
                self.host.handle(request)
        self.host.backend.execute.assert_not_called()
