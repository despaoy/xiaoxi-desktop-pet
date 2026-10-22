from datetime import datetime, timedelta
from desktop_pet.actions import ActionRegistry, Action
import unittest
import test_core


class NavigationTests(unittest.TestCase):
    setUp = test_core.CoreTests.setUp
    tearDown = test_core.CoreTests.tearDown
    def test_paused_timer_survives_tick_and_resumes_once(self):
        self.productivity.start_focus(25)
        self.productivity.focus_action()
        timer = self.store.get('plugin.productivity.timer')
        self.assertTrue(timer['paused'])
        self.assertEqual(self.productivity.focus_label(), '继续专注')
        self.productivity.tick(datetime.now()+timedelta(days=1))
        self.assertTrue(self.store.get('plugin.productivity.timer')['paused'])
        self.productivity.command('继续专注')
        self.assertFalse(self.store.get('plugin.productivity.timer')['paused'])
        self.assertEqual(self.productivity.focus_label(), '暂停专注')
        self.assertGreater(datetime.fromisoformat(self.store.get('plugin.productivity.timer')['due']), datetime.now())

    def test_action_state_shared_and_disabled_owner_blocked(self):
        active = {'productivity'}
        registry = ActionRegistry(lambda owner: owner in active)
        registry.add(Action('focus','productivity',self.productivity.focus_label,self.productivity.focus_action,'productivity'))
        registry.invoke('focus')
        self.assertEqual(registry.items['focus'].title,'暂停专注')
        registry.invoke('focus')
        self.assertEqual(registry.items['focus'].title,'继续专注')
        active.clear()
        with self.assertRaises(ValueError): registry.invoke('focus')

    def test_shortcut_removal_invalidates_saved_action(self):
        self.app.registry = ActionRegistry()
        self.shortcuts.add_item('测试文件夹', str(self.temp.name))
        key = 'shortcuts.item.'+self.shortcuts.items()[0]['id']
        self.assertIn(key,self.app.registry.items)
        self.shortcuts.save([])
        with self.assertRaises(ValueError): self.app.registry.invoke(key)
