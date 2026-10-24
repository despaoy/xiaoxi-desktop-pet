"""Headless regressions for service boundaries and delayed user actions."""
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import tempfile
import sqlite3
from unittest.mock import Mock, patch
from types import SimpleNamespace
import unittest

from desktop_pet.services import AppState, NotificationService, TimerService
from desktop_pet.storage import Store
from desktop_pet.plugin_api import PluginContext


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.state = AppState(self.store)
        self.now = datetime(2026, 10, 24, 10)
        self.timer = TimerService(self.store, self.state.set_focused, lambda: self.now)
        self.notifications = NotificationService(self.store, self.state, lambda: self.now)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_start_and_stop_share_persisted_state(self):
        self.timer.start(25)
        self.assertTrue(self.state.focused)
        self.assertEqual(self.timer.current['minutes'], 25)
        self.timer.stop()
        self.assertFalse(self.state.focused)
        self.assertIsNone(self.timer.current)

    def test_duplicate_start_and_break_preserve_active_timer(self):
        self.timer.start(25)
        before = self.timer.current
        for kind in ('专注', '休息'):
            with self.assertRaises(ValueError):
                self.timer.start(5, kind)
            self.assertEqual(self.timer.current, before)

    def test_pause_resume_preserves_remaining_across_sleep(self):
        self.timer.start(25)
        self.now += timedelta(minutes=10)
        self.timer.toggle_pause()
        self.assertEqual(self.timer.current['remaining'], 15 * 60)
        self.assertFalse(self.state.focused)
        self.now += timedelta(days=1)
        self.assertIsNone(self.timer.complete_due())
        self.timer.toggle_pause()
        self.assertEqual(datetime.fromisoformat(self.timer.current['due']), self.now + timedelta(minutes=15))
        self.assertTrue(self.state.focused)

    def test_completion_reports_once_after_restart(self):
        self.timer.start(25)
        self.now += timedelta(days=2)
        restarted = TimerService(self.store, self.state.set_focused, lambda: self.now)
        completed = restarted.complete_due()
        self.assertEqual(completed[0]['kind'], '专注')
        self.assertIsNone(restarted.complete_due())
        self.assertEqual(self.store.event_sum('2026-10-24', 'focus_planned_minutes'), 25)
        self.assertEqual(self.store.event_sum('2026-10-26', 'focus_planned_minutes'), 0)

    def test_stale_completion_action_cannot_replace_new_timer(self):
        self.timer.start(1)
        self.now += timedelta(minutes=2)
        _, revision = self.timer.complete_due()
        self.timer.start(25)
        before = self.timer.current
        with self.assertRaises(ValueError):
            self.timer.start(5, '休息', expected_revision=revision)
        self.assertEqual(self.timer.current, before)
        self.assertTrue(self.state.focused)

    def test_stale_action_still_invalid_after_new_timer_stopped_and_restart(self):
        self.timer.start(1)
        self.now += timedelta(minutes=2)
        _, revision = self.timer.complete_due()
        self.timer.start(25)
        self.timer.stop()
        restarted = TimerService(self.store, self.state.set_focused, lambda: self.now)
        with self.assertRaisesRegex(ValueError, '已过期'):
            restarted.start(5, '休息', expected_revision=revision)
        self.assertIsNone(restarted.current)

    def test_current_completion_action_succeeds_only_once(self):
        self.timer.start(1)
        self.now += timedelta(minutes=2)
        _, revision = self.timer.complete_due()
        self.timer.start(5, '休息', expected_revision=revision)
        self.assertFalse(self.state.focused)
        with self.assertRaises(ValueError):
            self.timer.start(5, '休息', expected_revision=revision)
        self.now += timedelta(minutes=6)
        self.timer.complete_due()
        with self.assertRaisesRegex(ValueError, '已过期'):
            self.timer.start(5, '休息', expected_revision=revision)

    def test_legacy_timer_without_revision_still_completes(self):
        self.store.set(TimerService.KEY, {'kind': '专注', 'due': self.now.isoformat(), 'minutes': 25})
        self.assertEqual(self.timer.complete_due()[0]['minutes'], 25)
        self.assertIsNone(self.timer.complete_due())

    def test_invalid_duration_does_not_mutate_state(self):
        for value in (0, 241, float('nan'), float('inf'), '25', True):
            with self.assertRaises(ValueError):
                self.timer.start(value)
        self.assertIsNone(self.timer.current)
        self.assertEqual(self.timer.revision, 0)

    def test_failed_completion_rolls_back_timer_revision_focus_and_event(self):
        focused = []
        timer = TimerService(self.store, focused.append, lambda: self.now)
        timer.start(1)
        before, revision = timer.current, timer.revision
        self.now += timedelta(minutes=2)
        self.store.db.execute("CREATE TRIGGER reject_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            timer.complete_due()
        self.assertEqual(timer.current, before)
        self.assertEqual(timer.revision, revision)
        self.assertTrue(self.state.focused)
        self.assertEqual(focused, [True])
        self.assertEqual(self.store.event_sum('2026-10-24', 'focus_planned_minutes'), 0)
        self.store.db.execute('DROP TRIGGER reject_event')
        self.assertIsNotNone(timer.complete_due())
        self.assertEqual(focused, [True, False])
        self.assertEqual(self.store.event_sum('2026-10-24', 'focus_planned_minutes'), 1)

    def test_failed_notification_does_not_advance_memory_or_queue(self):
        with patch.object(self.store, 'set', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.notifications.publish('提醒', '一')
        self.assertEqual(self.notifications.history, [])
        self.assertEqual(len(self.notifications.queue), 0)

    def test_dnd_records_without_delivering(self):
        self.notifications.set_dnd(True)
        self.assertFalse(self.notifications.publish('提醒', '喝水'))
        self.assertEqual(len(self.notifications.history), 1)
        self.assertIsNone(self.notifications.next())
        self.notifications.set_dnd(False)
        self.assertIsNone(self.notifications.next())

    def test_dnd_clears_already_queued_notifications_not_history(self):
        self.notifications.publish('提醒', '一')
        self.notifications.publish('提醒', '二')
        self.notifications.set_dnd(True)
        self.notifications.set_dnd(False)
        self.assertIsNone(self.notifications.next())
        self.assertEqual(len(self.notifications.history), 2)

    def test_delivery_rechecks_dnd_changed_by_legacy_caller(self):
        self.notifications.publish('提醒', '一')
        self.store.set('dnd', True)
        self.assertIsNone(self.notifications.next())
        self.assertEqual(len(self.notifications.queue), 0)

    def test_notification_history_bounded_and_alias_kept(self):
        alias = self.notifications.history
        for index in range(105):
            self.notifications.publish('提醒', str(index))
        self.assertIs(alias, self.notifications.history)
        self.assertEqual(len(alias), 100)
        self.assertEqual(alias[0]['body'], '5')
        self.assertEqual(self.store.get('notification_history'), alias)

    def test_notification_actions_fifo_without_execution(self):
        called = []
        callback = lambda: called.append(True)
        self.notifications.publish('一', '内容', [('按钮', callback)])
        self.notifications.publish('二', '内容')
        self.assertEqual(self.notifications.next()[0], '一')
        self.assertEqual(self.notifications.next()[0], '二')
        self.assertEqual(called, [])

    def test_app_focus_compatibility_attribute_uses_persisted_state(self):
        from desktop_pet.app import App
        app = App.__new__(App)
        app.state = self.state
        app.focused = True
        self.assertTrue(self.store.get('focused'))
        self.store.set('focused', False)
        self.assertFalse(app.focused)

    def test_app_dnd_dismisses_visible_bubble_and_clears_busy_flag(self):
        from desktop_pet.app import App
        app = App.__new__(App)
        app.state, app.notifications = self.state, self.notifications
        app.panel, app.pet = None, object()
        app.bubble = bubble = Mock()
        app.live2d = SimpleNamespace(ready=True, state=Mock())
        self.notifications.publish('提醒', '一')
        with patch('desktop_pet.app.messagebox.showinfo'):
            app.toggle_dnd()
        bubble.destroy.assert_called_once()
        self.assertIsNone(app.bubble)
        self.assertEqual(len(self.notifications.queue), 0)
        self.assertEqual(len(self.notifications.history), 1)
        app.live2d.state.assert_called_once_with(notificationBusy=False, speechMs=0)

    def test_failed_app_focus_write_preserves_visible_state(self):
        from desktop_pet.app import App
        app = App.__new__(App)
        app.state = self.state
        with patch.object(self.store, 'set', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                app.focused = True
        self.assertFalse(app.focused)

    def test_plugin_completion_callback_uses_guarded_service(self):
        path = Path(__file__).resolve().parents[1] / 'plugins/productivity/plugin.py'
        spec = importlib.util.spec_from_file_location('productivity_services_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        notifications = []
        app = SimpleNamespace(store=self.store, actions=[], focused=False,
                              notify=lambda *args: notifications.append(args))
        plugin = module.Plugin(PluginContext(app, 'productivity'))
        plugin.start_focus(1)
        plugin.tick(datetime.now() + timedelta(minutes=2))
        callback = notifications[-1][2][0][1]
        plugin.start_focus(25)
        before = plugin.timer.current
        with self.assertRaises(ValueError):
            callback()
        self.assertEqual(plugin.timer.current, before)
        self.assertTrue(app.focused)


if __name__ == '__main__':
    unittest.main()
