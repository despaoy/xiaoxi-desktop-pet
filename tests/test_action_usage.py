import logging
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_pet.actions import Action, ActionRegistry
from desktop_pet.action_usage import (
    DEFAULT_IDS, ELIGIBLE_IDS, HALF_LIFE_SECONDS, KEY,
    record_usage, recommended_actions,
)
from desktop_pet.hub_backend import HubBackend
from desktop_pet.navigation import Navigation
from desktop_pet.storage import Store


class ActionUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.registry = ActionRegistry()
        for key in ELIGIBLE_IDS:
            category = key.split('.')[0]
            self.registry.add(Action(key, category, key, Mock(return_value='ok')))
        self.registry.on_invoked = lambda key: record_usage(self.store, key, now=1000)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ids(self, **kwargs):
        return [a.id for a in recommended_actions(self.registry, self.store, **kwargs)]

    def test_cold_start_is_stable_without_writing_or_mutating_favorites(self):
        self.store.set('navigation.favorites', ['usage.today'])
        self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
        self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
        self.assertIsNone(self.store.get(KEY))
        self.assertEqual(self.store.get('navigation.favorites'), ['usage.today'])

    def test_usage_persists_across_store_restart_and_counts_once(self):
        self.assertEqual(self.registry.invoke('usage.today'), 'ok')
        self.registry.items['usage.today'].callback.assert_called_once_with()
        self.assertEqual(self.store.get(KEY)['usage.today']['count'], 1)
        self.store.close()
        self.store = Store(self.temp.name)
        self.assertEqual(self.ids(now=1000)[0], 'usage.today')

    def test_recent_frequency_can_overtake_old_lifetime_volume(self):
        for _ in range(20):
            record_usage(self.store, 'usage.today', now=1000)
        later = 1000 + 8 * HALF_LIFE_SECONDS
        record_usage(self.store, 'companion.look', now=later)
        self.assertEqual(self.ids(now=later)[0], 'companion.look')
        self.assertEqual(self.store.get(KEY)['usage.today']['count'], 20)

    def test_recent_repeated_use_outweighs_single_activation(self):
        record_usage(self.store, 'usage.today', now=1000)
        record_usage(self.store, 'companion.look', now=1000)
        record_usage(self.store, 'companion.look', now=1000)
        self.assertEqual(self.ids(now=1000)[0], 'companion.look')

    def test_disabled_owner_stale_and_unsafe_ids_never_recommended(self):
        self.registry.items['companion.greeting'].enabled = lambda: False
        self.registry.items['productivity.focus'].owner = 'disabled'
        self.registry.owner_available = lambda owner: owner != 'disabled'
        del self.registry.items['shortcuts.mute']
        self.registry.add(Action('shortcuts.lock', 'shortcuts', 'lock', Mock()))
        self.registry.add(Action('thirdparty.delete', 'settings', 'delete', Mock()))
        for key in ('shortcuts.lock', 'thirdparty.delete', 'missing.old'):
            record_usage(self.store, key, now=1000)
        result = self.ids(now=1000)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)
        self.assertTrue(set(result).isdisjoint(set(DEFAULT_IDS) | {'shortcuts.lock', 'thirdparty.delete'}))
        self.assertIsNone(self.store.get(KEY))

    def test_failed_or_disabled_actions_are_not_counted(self):
        self.registry.items['usage.today'].callback.side_effect = RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            self.registry.invoke('usage.today')
        self.registry.items['companion.look'].enabled = lambda: False
        with self.assertRaises(ValueError):
            self.registry.invoke('companion.look')
        with self.assertRaises(ValueError):
            self.registry.invoke('missing')
        self.assertIsNone(self.store.get(KEY))

    def test_storage_failure_does_not_hide_success_or_retry_callback(self):
        self.store.set = Mock(side_effect=OSError('disk'))
        with self.assertLogs(level=logging.ERROR):
            self.assertEqual(self.registry.invoke('usage.today'), 'ok')
        self.registry.items['usage.today'].callback.assert_called_once_with()

    def test_dynamic_titles_resolve_from_live_action_and_snapshot_order_is_stable(self):
        mode = {'title': '开始专注'}
        self.registry.items['productivity.focus'].label = lambda: mode['title']
        snapshot = recommended_actions(self.registry, self.store, now=1000)
        record_usage(self.store, 'usage.today', now=1000)
        mode['title'] = '暂停专注'
        self.assertEqual([a.id for a in snapshot], list(DEFAULT_IDS))
        self.assertEqual(snapshot[1].title, '暂停专注')
        self.assertEqual(self.ids(now=1000)[0], 'usage.today')

    def test_malformed_history_and_clock_rollback_do_not_inflate_frequency(self):
        self.store.set(KEY, {'usage.today': {'count': -1, 'recent': float('inf'), 'updated': 1000}})
        self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
        record_usage(self.store, 'usage.today', now=1000)
        record_usage(self.store, 'usage.today', now=900)
        self.assertEqual(self.store.get(KEY)['usage.today']['recent'], 2)
        self.assertEqual(self.store.get(KEY)['usage.today']['count'], 2)
        self.store.set(KEY, ['bad'])
        self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
        for value in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                record_usage(self.store, 'usage.today', now=value)

    def test_oversized_persisted_numbers_are_ignored_and_repaired(self):
        for field in ('count', 'recent', 'updated'):
            with self.subTest(field=field):
                value = {'count': 1, 'recent': 1, 'updated': 1000}
                value[field] = 10 ** 400
                self.store.set(KEY, {'usage.today': value})
                self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
                record_usage(self.store, 'usage.today', now=1000)
                self.assertEqual(self.store.get(KEY)['usage.today'],
                                 {'count': 1, 'recent': 1.0, 'updated': 1000.0})
        with self.assertRaises(ValueError):
            record_usage(self.store, 'usage.today', now=10 ** 400)

    def test_read_failure_falls_back_without_writing(self):
        self.store.get = Mock(side_effect=OSError('disk'))
        self.store.set = Mock()
        with self.assertLogs(level=logging.ERROR):
            self.assertEqual(self.ids(now=1000), list(DEFAULT_IDS))
        self.store.set.assert_not_called()

    def test_navigation_installs_central_hook_and_ui_invokes_once(self):
        app = SimpleNamespace(registry=ActionRegistry(), store=self.store,
                              toggle_dnd=Mock(), show_history=Mock())
        Navigation.init_navigation(app)
        app.registry.add(Action('usage.today', 'usage', '统计', Mock()))
        app.root = object()
        app.close_context_popup = Mock()
        app.refresh_navigation = Mock()
        with patch('desktop_pet.navigation.safe', side_effect=lambda root, fn: fn()):
            Navigation.invoke_action(app, 'usage.today')
        self.assertEqual(self.store.get(KEY)['usage.today']['count'], 1)
        app.registry.items['usage.today'].callback.assert_called_once_with()
        app.refresh_navigation.assert_called_once_with()

    def test_qt_system_override_success_and_failure_are_accounted_once(self):
        backend = HubBackend(SimpleNamespace(registry=self.registry, store=self.store))
        with patch('desktop_pet.hub_backend.platform_win.system_action', return_value='done') as system:
            self.assertEqual(backend.execute('action.invoke', {'id': 'shortcuts.mute'}), 'done')
            system.assert_called_once_with('mute')
        self.registry.items['shortcuts.mute'].callback.assert_not_called()
        self.assertEqual(self.store.get(KEY)['shortcuts.mute']['count'], 1)
        with patch('desktop_pet.hub_backend.platform_win.system_action', side_effect=OSError('failed')):
            with self.assertRaises(OSError):
                backend.execute('action.invoke', {'id': 'shortcuts.mute'})
        self.assertEqual(self.store.get(KEY)['shortcuts.mute']['count'], 1)

    def test_qt_editing_preview_does_not_influence_action_usage(self):
        plugin = SimpleNamespace(perform=Mock())
        app = SimpleNamespace(registry=self.registry, store=self.store,
                              dialogue=SimpleNamespace(data={'actions': {'blink': []}}),
                              plugins=SimpleNamespace(plugins={'companion': plugin}))
        backend = HubBackend(app)
        backend.execute('language.preview', {'kind': 'actions', 'key': 'blink'})
        self.registry.items['companion.blink'].callback.assert_not_called()
        plugin.perform.assert_called_once_with('blink')
        self.assertIsNone(self.store.get(KEY))

    def test_qt_dnd_same_intent_not_counted_twice(self):
        app = SimpleNamespace(registry=self.registry, store=self.store, bubble=None,
                              notifications=SimpleNamespace(set_dnd=lambda value: self.store.set('dnd', value)))
        backend = HubBackend(app)
        backend.execute('settings.dnd', {'enabled': True})
        backend.execute('settings.dnd', {'enabled': True})
        backend.execute('settings.dnd', {'enabled': False})
        self.assertEqual(self.store.get(KEY)['settings.dnd']['count'], 2)
        app.notifications.set_dnd = Mock(side_effect=OSError('failed'))
        with self.assertRaises(OSError):
            backend.execute('settings.dnd', {'enabled': True})
        self.assertEqual(self.store.get(KEY)['settings.dnd']['count'], 2)

    def test_registered_system_action_propagates_failure_before_usage(self):
        # The registry callback must not use the UI safe() wrapper, which swallows
        # exceptions. Direct settings-page buttons retain that wrapper.
        import importlib.util
        from desktop_pet.plugin_api import PluginContext
        path = Path(__file__).resolve().parents[1] / 'plugins/shortcuts/plugin.py'
        spec = importlib.util.spec_from_file_location('shortcuts_usage_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = ActionRegistry()
        registry.on_invoked = lambda key: record_usage(self.store, key, now=1000)
        app = SimpleNamespace(registry=registry, actions=[], store=self.store)
        module.Plugin(PluginContext(app, 'shortcuts'))
        with patch.object(module.platform_win, 'system_action', side_effect=OSError('failed')):
            with self.assertRaises(OSError):
                registry.invoke('shortcuts.mute')
        self.assertIsNone(self.store.get(KEY))
        with patch.object(module.platform_win, 'system_action', return_value=None):
            registry.invoke('shortcuts.mute')
        self.assertEqual(self.store.get(KEY)['shortcuts.mute']['count'], 1)


class DirectHubUsageTests(unittest.TestCase):
    def setUp(self):
        import test_core
        test_core.CoreTests.setUp(self)
        self.app.registry = ActionRegistry()
        for key, callback in (
            ('productivity.focus', self.productivity.focus_action),
            ('productivity.todo', self.productivity.todo_dialog),
            ('productivity.reminder', self.productivity.reminder_dialog),
        ):
            self.app.registry.add(Action(key, 'productivity', key, callback))
        self.app.registry.on_invoked = lambda key: record_usage(self.store, key, now=1000)
        self.backend = HubBackend(self.app)

    def tearDown(self):
        import test_core
        test_core.CoreTests.tearDown(self)

    def count(self, key):
        return self.store.get(KEY, {}).get(key, {}).get('count', 0)

    def test_timer_start_pause_resume_count_effectful_commands_only(self):
        self.backend.execute('timer.start', {'minutes': 25})
        self.backend.execute('timer.pause')
        self.backend.execute('timer.pause')  # duplicate intent, no change
        self.backend.execute('timer.resume')
        self.backend.execute('timer.resume')
        self.backend.execute('timer.stop')  # deliberately not recommended
        self.assertEqual(self.count('productivity.focus'), 3)
        with self.assertRaises(ValueError):
            self.backend.execute('timer.pause')
        with self.assertRaises(ValueError):
            self.backend.execute('timer.start', {'minutes': -1})
        self.assertEqual(self.count('productivity.focus'), 3)

    def test_completed_adds_count_but_edit_delete_and_invalid_input_do_not(self):
        self.backend.execute('todo.save', {'title': 'read'})
        row = self.store.get('plugin.productivity.todos')[0]
        self.backend.execute('todo.save', {'id': row['id'], 'title': 'read more'})
        self.backend.execute('todo.toggle', {'id': row['id'], 'done': True})
        self.backend.execute('todo.delete', {'id': row['id']})
        self.assertEqual(self.count('productivity.todo'), 1)
        self.backend.execute('reminder.save', {'title': 'rest', 'minutes': 5})
        row = self.store.get('plugin.productivity.reminders')[0]
        self.backend.execute('reminder.save', {'id': row['id'], 'title': 'rest now', 'minutes': 5})
        self.backend.execute('reminder.delete', {'id': row['id']})
        with self.assertRaises(ValueError):
            self.backend.execute('reminder.save', {'title': 'rest', 'minutes': -1})
        self.assertEqual(self.count('productivity.reminder'), 1)

    def test_custom_duration_dialog_counts_only_success_not_cancel_or_failure(self):
        # Tests load plugins through importlib without registering sys.modules;
        # patch their function's globals instead of depending on module names.
        globals_ = self.productivity.start_dialog.__func__.__globals__
        with patch.object(globals_['simpledialog'], 'askinteger', return_value=None):
            self.productivity.start_dialog()
        self.assertEqual(self.count('productivity.focus'), 0)
        with patch.object(globals_['simpledialog'], 'askinteger', return_value=30):
            self.productivity.start_dialog()
        self.assertEqual(self.count('productivity.focus'), 1)
        with patch.object(globals_['simpledialog'], 'askinteger', return_value=30), \
             patch.object(self.productivity, 'start_focus', side_effect=ValueError('failed')), \
             patch.object(globals_['messagebox'], 'showinfo'):
            self.productivity.start_dialog()
        self.assertEqual(self.count('productivity.focus'), 1)


if __name__ == '__main__':
    unittest.main()
