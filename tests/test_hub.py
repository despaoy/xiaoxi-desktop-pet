"""Dependency-free dashboard helpers and optional real-Tk control checks.

The helper tests run without a display. The widget tests are deliberately
skipped on headless machines rather than hiding failures in the pure logic.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from desktop_pet import hub, ui
from desktop_pet.actions import Action, ActionRegistry
from desktop_pet.apps import UsageRecord


class FitTextTests(unittest.TestCase):
    def test_short_and_exact_width_text_are_preserved(self):
        self.assertEqual(ui.fit_text('小汐', len, 2), '小汐')
        self.assertEqual(ui.fit_text('hello', len, 20), 'hello')
        self.assertEqual(ui.fit_text('', len, 20), '')

    def test_newlines_are_normalized_for_single_line_labels(self):
        result = ui.fit_text('第一行\n第二行\r\n第三行', len, 40)
        self.assertEqual(result, '第一行 第二行 第三行')

    def test_truncation_measures_ellipsis_instead_of_character_count(self):
        def measure(text):
            return sum(2 if char == '…' else 1 for char in text)

        self.assertEqual(ui.fit_text('abcdef', measure, 4), 'ab…')
        self.assertEqual(ui.fit_text('abcdef', measure, 2), '…')
        self.assertEqual(ui.fit_text('abcdef', measure, 1), '')

    def test_wide_characters_fit_the_pixel_budget(self):
        def measure(text):
            return sum(1 if char == '…' else 2 for char in text)

        result = ui.fit_text('小汐桌面助手', measure, 5)
        self.assertEqual(result, '小汐…')
        self.assertLessEqual(measure(result), 5)

    def test_nonpositive_width_has_no_visible_text(self):
        for width in (0, -1):
            with self.subTest(width=width):
                self.assertEqual(ui.fit_text('hello', len, width), '')


class DrawIconTests(unittest.TestCase):
    def test_vector_icons_use_primitives_inside_the_requested_bounds(self):
        names = ('home', 'heart', 'clock', 'bolt', 'chart', 'settings', 'bell',
                 'check', 'circle', 'chevron', 'sparkle', 'unknown')
        for name in names:
            for size in (12, 20, 32):
                with self.subTest(icon=name, size=size):
                    canvas = Mock()
                    ui.draw_icon(canvas, 30, 50, name, size=size, color='#123456')
                    self.assertTrue(canvas.method_calls)
                    for call in canvas.method_calls:
                        method, coordinates, options = call
                        self.assertIn(method, ('create_line', 'create_oval'))
                        self.assertEqual(len(coordinates) % 2, 0)
                        self.assertEqual(options.get('fill', options.get('outline')), '#123456')
                        for x, y in zip(coordinates[::2], coordinates[1::2]):
                            self.assertGreaterEqual(x, 30)
                            self.assertLessEqual(x, 30 + size)
                            self.assertGreaterEqual(y, 50)
                            self.assertLessEqual(y, 50 + size)


class RoundedButtonStateTests(unittest.TestCase):
    """Test the Canvas button's Python state adapter without a Tcl display."""

    def setUp(self):
        self.button = object.__new__(ui.RoundedButton)
        self.button.text = '开始'
        self.button.state = 'normal'
        self.button.foreground = ui.ACCENT
        self.button.command = Mock(return_value='invoked')
        self.button._button_font = SimpleNamespace(measure=len)
        self.button._draw = Mock()
        self.button.focus_set = Mock()

    def test_configure_consumes_button_options_and_forwards_canvas_options(self):
        with patch.object(tk.Canvas, 'configure') as configure:
            self.button.configure(text='继续专注', state='disabled', fg='#123456')
        self.assertEqual(self.button.cget('text'), '继续专注')
        self.assertEqual(self.button.cget('state'), 'disabled')
        self.assertEqual(self.button.cget('fg'), '#123456')
        configure.assert_called_once_with(width=32, takefocus=False, cursor='arrow')
        self.button._draw.assert_called_once_with()

    def test_config_alias_accepts_dictionary_and_can_reenable(self):
        self.button.state = 'disabled'
        with patch.object(tk.Canvas, 'configure') as configure:
            self.button.config({'text': '暂停', 'state': 'normal'}, width=90)
        self.assertEqual(self.button.text, '暂停')
        self.assertEqual(self.button.state, 'normal')
        configure.assert_called_once_with(width=90, takefocus=True, cursor='hand2')

    def test_invoke_and_activation_respect_disabled_state(self):
        self.assertEqual(self.button.invoke(), 'invoked')
        self.assertEqual(self.button._activate(), 'break')
        self.assertEqual(self.button.command.call_count, 2)
        self.button.focus_set.assert_called_once_with()
        self.button.state = 'disabled'
        self.assertIsNone(self.button.invoke())
        self.assertEqual(self.button._activate(), 'break')
        self.assertEqual(self.button.command.call_count, 2)
        self.button.focus_set.assert_called_once_with()

    def test_custom_option_queries_do_not_redraw(self):
        self.assertEqual(self.button['text'], '开始')
        self.assertEqual(self.button.configure('state')[-1], 'normal')
        with patch.object(tk.Canvas, 'configure', return_value={'bg': ('bg',)}) as configure:
            options = self.button.configure()
        self.assertEqual(options['bg'], ('bg',))
        self.assertEqual(options['text'][-1], '开始')
        self.assertEqual(options['fg'][-1], ui.ACCENT)
        configure.assert_called_once_with()
        self.button._draw.assert_not_called()


class CompactCategoriesTests(unittest.TestCase):
    @staticmethod
    def record(category, seconds, index=0):
        return UsageRecord(str(index), '应用 ' + str(index), category, seconds)

    def test_empty_records_have_no_segments(self):
        self.assertEqual(hub.compact_categories([]), [])

    def test_categories_are_aggregated_and_sorted(self):
        records = [self.record('browse', 20), self.record('dev', 30),
                   self.record('browse', 25)]
        self.assertEqual(hub.compact_categories(records),
                         [('browse', 45), ('dev', 30)])

    def test_top_three_named_categories_plus_other_preserve_total(self):
        records = [self.record(key, seconds, index) for index, (key, seconds)
                   in enumerate([('dev', 100), ('browse', 80), ('ai', 60),
                                 ('fun', 40), ('system', 20), ('other', 10)])]
        result = hub.compact_categories(records)
        self.assertEqual(result,
                         [('dev', 100), ('browse', 80), ('ai', 60), ('other', 70)])
        self.assertEqual(sum(seconds for _, seconds in result),
                         sum(record.seconds for record in records))
        self.assertEqual([record.seconds for record in records],
                         [100, 80, 60, 40, 20, 10])

    def test_existing_other_is_not_duplicated_when_it_is_largest(self):
        records = [self.record('other', 400), self.record('dev', 30),
                   self.record('browse', 20), self.record('ai', 10),
                   self.record('system', 5)]
        result = hub.compact_categories(records)
        self.assertEqual(result,
                         [('dev', 30), ('browse', 20), ('ai', 10), ('other', 405)])
        self.assertEqual(sum(seconds for _, seconds in result), 465)
        self.assertEqual(sum(key == 'other' for key, _ in result), 1)

    def test_custom_limit_controls_named_categories(self):
        records = [self.record('dev', 100), self.record('browse', 80),
                   self.record('ai', 20), self.record('other', 10)]
        self.assertEqual(hub.compact_categories(records, limit=1),
                         [('dev', 100), ('other', 110)])

    def test_only_other_remains_a_single_segment(self):
        records = [self.record('other', 25), self.record('other', 15)]
        self.assertEqual(hub.compact_categories(records), [('other', 40)])


class ReminderPairTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 22, 10, 0, 0)

    def reminder(self, title, seconds, done=False):
        return {'title': title, 'due': (self.now + timedelta(seconds=seconds)).isoformat(),
                'done': done}

    def test_empty_or_finished_reminders_have_empty_state(self):
        expected = ('暂无提醒', '在专注页添加')
        self.assertEqual(hub.reminder_pair([], self.now), expected)
        self.assertEqual(hub.reminder_pair([self.reminder('已完成', -60, True)],
                                           self.now), expected)

    def test_next_unfinished_reminder_is_chosen_independent_of_input_order(self):
        rows = [self.reminder('较晚', 900), self.reminder('已完成', 60, True),
                self.reminder('下一项', 300)]
        title, right = hub.reminder_pair(rows, self.now)
        self.assertIn('下一项', title)
        self.assertIn('10:05', title)
        self.assertEqual(right, '还有 5 分钟')

    def test_future_under_one_minute_is_not_marked_overdue(self):
        for seconds in (0.5, 1, 59, 59.9):
            with self.subTest(seconds=seconds):
                _, right = hub.reminder_pair([self.reminder('喝水', seconds)],
                                             self.now)
                self.assertEqual(right, '即将到期')

    def test_one_minute_uses_minute_count(self):
        _, right = hub.reminder_pair([self.reminder('喝水', 60)], self.now)
        self.assertEqual(right, '还有 1 分钟')

    def test_due_and_past_reminders_are_overdue(self):
        for seconds in (0, -1, -3600):
            with self.subTest(seconds=seconds):
                _, right = hub.reminder_pair([self.reminder('喝水', seconds)],
                                             self.now)
                self.assertEqual(right, '已到期')

    def test_malformed_rows_are_skipped_without_hiding_valid_reminders(self):
        rows = [None, 'bad row', {}, {'due': 'not a date'}, {'due': None},
                {'due': 123}, self.reminder('有效提醒', 120)]
        title, right = hub.reminder_pair(rows, self.now)
        self.assertIn('有效提醒', title)
        self.assertEqual(right, '还有 2 分钟')

    def test_all_malformed_rows_use_empty_state(self):
        self.assertEqual(hub.reminder_pair([None, {}, {'due': 'invalid'}], self.now),
                         ('暂无提醒', '在专注页添加'))


class HubStateTests(unittest.TestCase):
    """Exercise live refresh and navigation without constructing a Tk window."""

    class Host:
        def __init__(self):
            self.children = []

        def winfo_children(self):
            return list(self.children)

    class Row:
        def __init__(self, parent, icon='', label='', command=None, enabled=True,
                     **kwargs):
            self.parent = parent
            self.label, self.enabled = label, enabled
            self.command = command
            self.destroyed = False
            parent.children.append(self)

        def set_content(self, label, enabled):
            self.label, self.enabled = label, enabled

        def pack(self, **kwargs):
            pass

        def destroy(self):
            self.destroyed = True
            self.parent.children.remove(self)

    def make_category(self):
        return SimpleNamespace(
            app=SimpleNamespace(registry=ActionRegistry()), current='productivity',
            action_host=self.Host(), _category_ids=(), _category_rows={},
            context_label=None, _refresh_stats=Mock(), _refresh_reminder=Mock(),
            _invoke=Mock())

    def test_live_action_labels_and_availability_update_without_replacing_rows(self):
        view = self.make_category()
        state = {'label': '开始专注', 'enabled': True}
        view.app.registry.add(Action('focus', 'productivity', lambda: state['label'],
                                     lambda: None, enabled=lambda: state['enabled']))
        with patch.object(hub, 'ActionRow', self.Row):
            hub.Hub._refresh_category(view)
            original_row = view._category_rows['focus']
            state.update(label='暂停专注', enabled=False)
            hub.Hub._refresh_category(view)
        self.assertIs(view._category_rows['focus'], original_row)
        self.assertEqual((original_row.label, original_row.enabled), ('暂停专注', False))
        self.assertFalse(original_row.destroyed)
        self.assertEqual(view._refresh_stats.call_count, 2)
        self.assertEqual(view._refresh_reminder.call_count, 2)

    def test_registry_membership_changes_remove_stale_rows_and_keep_correct_callbacks(self):
        view = self.make_category()
        view.app.registry.add(Action('old', 'productivity', '旧操作', lambda: None))
        with patch.object(hub, 'ActionRow', self.Row):
            hub.Hub._refresh_category(view)
            old_row = view._category_rows['old']
            view.app.registry.remove_prefix('old')
            for name in ('new-one', 'new-two'):
                view.app.registry.add(Action(name, 'productivity', name, lambda: None))
            hub.Hub._refresh_category(view)
        self.assertTrue(old_row.destroyed)
        self.assertEqual(set(view._category_rows), {'new-one', 'new-two'})
        view._category_rows['new-one'].command()
        view._category_rows['new-two'].command()
        self.assertEqual([call.args for call in view._invoke.call_args_list],
                         [('new-one',), ('new-two',)])

    def test_empty_category_placeholder_is_not_recreated_on_every_tick(self):
        view = self.make_category()
        with patch.object(hub.tk, 'Label', self.Row):
            hub.Hub._refresh_category(view)
            placeholder = view.action_host.children[0]
            hub.Hub._refresh_category(view)
        self.assertEqual(view.action_host.children, [placeholder])
        self.assertFalse(placeholder.destroyed)

    def test_periodic_refresh_reaches_categories_and_usage_data(self):
        view = SimpleNamespace(
            winfo_exists=lambda: True, rail_status=Mock(), hide_label=Mock(),
            _status_line=lambda: '在这里陪你', app=SimpleNamespace(pet_hidden=True),
            current='productivity', _refresh_category=Mock(), _refresh_data=Mock(),
            _last_data=0)
        with patch.object(hub.time, 'monotonic', return_value=10):
            hub.Hub.refresh(view)
        view._refresh_category.assert_called_once_with()
        view._refresh_data.assert_called_once_with()
        view.hide_label.configure.assert_called_once_with(text='显示角色')
        self.assertEqual(view._last_data, 10)

    def test_closed_view_does_not_refresh_widgets(self):
        view = SimpleNamespace(winfo_exists=lambda: False)
        hub.Hub.refresh(view)

    def test_reselecting_current_category_preserves_content_and_scroll(self):
        view = SimpleNamespace(current='productivity', nav_items={'productivity': Mock()},
                               _show_today=Mock(), _show_category=Mock(),
                               viewport=Mock(), refresh=Mock())
        hub.Hub.select(view, 'productivity')
        view._show_today.assert_not_called()
        view._show_category.assert_not_called()
        view.viewport.yview_moveto.assert_not_called()
        view.refresh.assert_called_once_with()
        view.nav_items['productivity'].set_selected.assert_called_once_with(True)

    def test_unknown_category_is_ignored_without_mutating_navigation(self):
        view = SimpleNamespace(current='today', refresh=Mock())
        hub.Hub.select(view, 'not-a-category')
        self.assertEqual(view.current, 'today')
        view.refresh.assert_not_called()


class KeyboardControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest('Tk display unavailable: ' + str(exc))
        cls.root.geometry('600x300+0+0')
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.host = tk.Frame(self.root)
        self.host.pack(fill='both', expand=True)
        self.calls = []

    def tearDown(self):
        self.host.destroy()
        self.root.update_idletasks()

    def make_control(self, control_type, **kwargs):
        control = control_type(self.host, '\ue916', '测试操作',
                               lambda: self.calls.append('called'), **kwargs)
        control.pack()
        self.root.update()
        return control

    def press_key(self, control, key):
        control.focus_force()
        self.root.update()
        self.assertEqual(self.root.focus_get(), control)
        control.event_generate('<KeyPress-' + key + '>')
        self.root.update()

    def test_navigation_supports_focus_return_and_space(self):
        control = self.make_control(hub.NavItem)
        self.assertEqual(str(control.cget('takefocus')), '1')
        self.press_key(control, 'Return')
        self.press_key(control, 'space')
        self.assertEqual(self.calls, ['called', 'called'])

    def test_action_controls_support_mouse_return_and_space(self):
        for control_type in (hub.Chip, hub.ActionRow):
            with self.subTest(control=control_type.__name__):
                self.calls.clear()
                control = self.make_control(control_type)
                self.assertEqual(str(control.cget('takefocus')), '1')
                control._click()
                self.press_key(control, 'Return')
                self.press_key(control, 'space')
                self.assertEqual(self.calls, ['called', 'called', 'called'])
                control.destroy()

    def test_disabled_action_controls_cannot_invoke(self):
        for control_type in (hub.Chip, hub.ActionRow):
            with self.subTest(control=control_type.__name__):
                self.calls.clear()
                control = self.make_control(control_type, enabled=False)
                self.assertEqual(str(control.cget('takefocus')), '0')
                control._click()
                self.press_key(control, 'Return')
                self.press_key(control, 'space')
                self.assertEqual(self.calls, [])
                control.destroy()

    def test_content_updates_can_enable_then_disable_controls(self):
        for control_type in (hub.Chip, hub.ActionRow):
            with self.subTest(control=control_type.__name__):
                self.calls.clear()
                control = self.make_control(control_type, enabled=False)
                control.set_content('暂停专注', True)
                self.assertEqual(control.label, '暂停专注')
                self.assertEqual(str(control.cget('takefocus')), '1')
                control._click()
                control.set_content('插件已停用', False)
                self.assertEqual(control.label, '插件已停用')
                self.assertEqual(str(control.cget('takefocus')), '0')
                control._click()
                self.assertEqual(self.calls, ['called'])
                control.destroy()

    def test_rounded_button_configuration_and_canvas_text(self):
        button = ui.text_button(self.host, '开始', lambda: self.calls.append('called'))
        button.pack()
        self.root.update()
        button.configure(text='暂停专注', state='disabled', fg='#123456')
        self.root.update()
        self.assertEqual(button.cget('text'), '暂停专注')
        self.assertEqual(button.cget('state'), 'disabled')
        self.assertEqual(button.cget('fg'), '#123456')
        self.assertEqual(str(button.cget('takefocus')), '0')
        self.assertEqual(button.cget('cursor'), 'arrow')
        text_item = next(item for item in button.find_all() if button.type(item) == 'text')
        self.assertEqual(button.itemcget(text_item, 'text'), '暂停专注')
        self.assertEqual(button.itemcget(text_item, 'fill'), ui.MUTED)
        button.config({'text': '继续专注', 'state': 'normal'})
        self.root.update()
        self.assertEqual(str(button.cget('takefocus')), '1')
        self.assertEqual(button.cget('cursor'), 'hand2')
        text_item = next(item for item in button.find_all() if button.type(item) == 'text')
        self.assertEqual(button.itemcget(text_item, 'text'), '继续专注')
        self.assertEqual(button.itemcget(text_item, 'fill'), '#123456')

    def test_rounded_button_keyboard_mouse_and_programmatic_invoke(self):
        def command():
            self.calls.append('called')
            return 'result'

        button = ui.text_button(self.host, '开始', command, primary=True)
        button.pack()
        self.root.update()
        self.press_key(button, 'Return')
        self.press_key(button, 'space')
        button._activate()
        self.assertEqual(button.invoke(), 'result')
        self.assertEqual(self.calls, ['called'] * 4)
        button.configure(state='disabled')
        self.press_key(button, 'Return')
        self.press_key(button, 'space')
        button._activate()
        self.assertIsNone(button.invoke())
        self.assertEqual(self.calls, ['called'] * 4)
        button.configure(state='normal')
        self.press_key(button, 'Return')
        self.assertEqual(self.calls, ['called'] * 5)

    def test_rounded_button_long_label_remains_inside_a_narrow_width(self):
        button = ui.text_button(self.host, '很长的操作名称需要安全地省略而不是越界',
                                lambda: None, quiet=True)
        button.configure(width=100)
        button.pack()
        self.root.update()
        text_item = next(item for item in button.find_all() if button.type(item) == 'text')
        self.assertTrue(button.itemcget(text_item, 'text').endswith('…'))
        x1, _, x2, _ = button.bbox(text_item)
        self.assertGreaterEqual(x1, 0)
        self.assertLessEqual(x2, button.winfo_width())


if __name__ == '__main__':
    unittest.main()
