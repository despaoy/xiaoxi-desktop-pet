"""Menu logic plus real Tk integration (explicitly skipped without a display)."""
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_pet.actions import Action, ActionRegistry, CATEGORIES
from desktop_pet.action_usage import record_usage
from desktop_pet.menu import Card, ContextMenu, QuickButton, Row, clamp_position
from desktop_pet.navigation import Navigation
from desktop_pet.storage import Store


class GeometryTests(unittest.TestCase):
    def test_edges_and_negative_positions_remain_inside_screen(self):
        for x, y in ((-300, -20), (1279, 899), (1200, 880), (0, 0), (300, 200)):
            px, py = clamp_position(x, y, 230, 340, 1280, 900)
            self.assertGreaterEqual(px, 0)
            self.assertGreaterEqual(py, 0)
            self.assertLessEqual(px + 230, 1280)
            self.assertLessEqual(py + 340, 900)

    def test_normal_position_preserved(self):
        self.assertEqual(clamp_position(100, 200, 230, 340, 1280, 900), (100, 200))

    def test_replacing_pending_hover_cancels_old_job(self):
        menu = object.__new__(ContextMenu)
        menu.submenu_job, menu.flyout, menu.active_anchor = 'old', None, None
        menu.after_cancel, menu.after = Mock(), Mock(return_value='new')
        anchor = Mock()
        menu.schedule_submenu(anchor)
        menu.after_cancel.assert_called_once_with('old')
        self.assertEqual(menu.submenu_job, 'new')

    def test_close_submenu_clears_anchor_and_pending_job(self):
        menu = object.__new__(ContextMenu)
        flyout = Mock()
        menu.submenu_job, menu.flyout, menu.active_anchor = 'pending', flyout, Mock()
        menu.after_cancel = Mock()
        menu.close_submenu()
        self.assertIsNone(menu.flyout)
        self.assertIsNone(menu.active_anchor)
        self.assertIsNone(menu.submenu_job)
        flyout.destroy.assert_called_once_with()

    def test_disabled_row_does_not_execute_or_close(self):
        row = object.__new__(Row)
        row.enabled = False
        row.menu, row.command = Mock(), Mock()
        self.assertIsNone(row._click())
        row.command.assert_not_called()
        row.menu.close.assert_not_called()

    def test_quick_button_uses_shared_invocation_once(self):
        button = object.__new__(QuickButton)
        app = Mock()
        button.menu, button.action = SimpleNamespace(app=app), SimpleNamespace(id='companion.greeting')
        self.assertEqual(button._activate(), 'break')
        app.invoke_action.assert_called_once_with('companion.greeting')

    def test_card_destroy_cancels_animation_jobs_once(self):
        card = object.__new__(Card)
        card._card_destroyed = False
        card.animation_jobs = ['fade1', 'fade2']
        card.after_cancel = Mock()
        with patch.object(tk.Toplevel, 'destroy') as destroy:
            card.destroy()
            card.destroy()
        self.assertEqual(card.after_cancel.call_count, 2)
        self.assertEqual(card.animation_jobs, [])
        destroy.assert_called_once_with()

    def test_keyboard_category_enters_first_enabled_submenu_row(self):
        row = object.__new__(Row)
        first, disabled = Mock(enabled=True), Mock(enabled=False)
        row.enabled, row.category = True, 'companion'
        row.menu = Mock(flyout=SimpleNamespace(action_rows=[disabled, first]))
        row._click(SimpleNamespace(keysym='Right'))
        first.focus_set.assert_called_once_with()
        disabled.focus_set.assert_not_called()

    def test_focus_inside_flyout_keeps_menu_open(self):
        menu = object.__new__(ContextMenu)
        menu.focus_job = 'pending'
        menu.winfo_exists = lambda: True
        menu.flyout = SimpleNamespace(master=None)
        menu.focus_get = lambda: SimpleNamespace(master=menu.flyout)
        menu.close = Mock()
        menu._check_focus()
        menu.close.assert_not_called()

    def test_focus_outside_menu_closes_it(self):
        menu = object.__new__(ContextMenu)
        menu.focus_job, menu.flyout = 'pending', None
        menu.winfo_exists, menu.focus_get, menu.close = lambda: True, lambda: None, Mock()
        menu._check_focus()
        menu.close.assert_called_once_with()


class MenuTkTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'Real Tk menu needs a display: {exc}')
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.app = SimpleNamespace(root=self.root, store=self.store,
            registry=ActionRegistry(), pet_hidden=False, focused=False,
            show_hub=Mock(), close=Mock(), toggle_pet_visibility=Mock(), context_popup=None)
        for key, category, label in (
            ('companion.greeting', 'companion', '打招呼'),
            ('productivity.focus', 'productivity', '开始 25 分钟专注'),
            ('shortcuts.mute', 'shortcuts', '静音 / 恢复'),
            ('companion.blink', 'companion', '眨眨眼')):
            self.app.registry.add(Action(key, category, label, Mock()))
        for index in range(12):
            self.app.registry.add(Action(f'companion.extra.{index}', 'companion', f'其他动作 {index}', Mock()))
        def invoke(key):
            if self.app.context_popup:
                self.app.context_popup.close()
            self.app.registry.invoke(key)
            record_usage(self.store, key)
        self.app.invoke_action = invoke

    def tearDown(self):
        if hasattr(self, 'store'):
            self.store.close()
            self.temp.cleanup()
            self.root.destroy()

    def open(self, x=100, y=100):
        menu = ContextMenu(self.app, x, y)
        self.app.context_popup = menu
        self.root.update()
        return menu

    def test_layout_and_all_submenu_actions_are_reachable(self):
        menu = self.open()
        self.assertEqual(set(menu.category_rows), set(CATEGORIES))
        self.assertEqual(len(menu.quick_buttons), 3)
        menu.open_submenu(menu.category_rows['companion'])
        self.root.update()
        self.assertEqual(len(menu.flyout.action_rows), 14)
        self.assertEqual(menu.flyout.action_rows[-1].text.cget('text'), '其他动作 11')
        def texts(widget):
            result = []
            if isinstance(widget, (tk.Label, tk.Button)):
                result.append(widget.cget('text'))
            for child in widget.winfo_children():
                result += texts(child)
            return result
        self.assertFalse(any('完整页面' in text for text in texts(menu.flyout)))

    def test_ranking_snapshot_stable_until_next_open(self):
        menu = self.open()
        ids = [a.id for a in menu.quick_actions]
        for _ in range(10):
            record_usage(self.store, 'companion.blink')
        self.assertEqual([a.id for a in menu.quick_actions], ids)
        menu.close()
        menu = self.open()
        self.assertEqual(menu.quick_actions[0].id, 'companion.blink')
        menu.quick_buttons[0]._activate()
        self.app.registry.items['companion.blink'].callback.assert_called_once_with()
        self.assertIsNone(self.app.context_popup)

    def test_bottom_right_bounds_and_repeated_close_escape(self):
        for _ in range(3):
            menu = self.open(self.root.winfo_screenwidth()-2, self.root.winfo_screenheight()-2)
            self.assertLessEqual(menu.winfo_rootx() + menu.winfo_width(), self.root.winfo_screenwidth())
            self.assertLessEqual(menu.winfo_rooty() + menu.winfo_height(), self.root.winfo_screenheight())
            menu.open_submenu(menu.category_rows['companion'])
            self.root.update()
            self.assertGreaterEqual(menu.flyout.winfo_rootx(), 0)
            self.assertLessEqual(menu.flyout.winfo_rooty()+menu.flyout.winfo_height(), self.root.winfo_screenheight())
            menu.focus_force()
            menu.event_generate('<Escape>')
            self.root.update()
            self.assertIsNone(self.app.context_popup)

    def test_focus_leaving_flyout_closes_entire_menu(self):
        menu = self.open()
        menu.open_submenu(menu.category_rows['companion'])
        menu.flyout.action_rows[0].focus_force()
        self.root.update()
        other = tk.Toplevel(self.root)
        other.focus_force()
        self.root.after(180, self.root.quit)
        self.root.mainloop()
        self.assertIsNone(self.app.context_popup)
        other.destroy()

    def test_immediate_close_cancels_pending_fade_callbacks(self):
        errors = []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        for _ in range(3):
            menu = ContextMenu(self.app, 10, 10)
            self.app.context_popup = menu
            menu.close()
        self.root.after(40, self.root.quit)
        self.root.mainloop()
        self.assertEqual(errors, [])

    def test_home_callback_closes_then_opens_existing_home(self):
        menu = self.open()
        menu._open_home()
        self.app.show_hub.assert_called_once_with()
        self.assertIsNone(self.app.context_popup)


if __name__ == '__main__':
    unittest.main()
