from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from desktop_pet.storage import Store
from desktop_pet.plugin_api import PluginContext, PluginManager
from desktop_pet.platform_win import ProcessInfo

BASE = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / 'plugins' / name / 'plugin.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoreTests(unittest.TestCase):
    def setUp(self):
        test_root = BASE / 'data-tests'
        test_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.store = Store(self.temp.name)
        self.notifications = []
        self.app = SimpleNamespace(store=self.store, actions=[], focused=False, notify=lambda *args:self.notifications.append(args))
        self.productivity = load('productivity').Plugin(PluginContext(self.app, 'productivity'))
        self.shortcuts = load('shortcuts').Plugin(PluginContext(self.app, 'shortcuts'))
        self.app.plugins = SimpleNamespace(plugins={'productivity':self.productivity})

    def tearDown(self):
        self.store.close()
        assert Path(self.temp.name).resolve().is_relative_to((BASE/'data-tests').resolve())
        self.temp.cleanup()

    def test_usage_identity_uses_java_title_without_storing_title(self):
        module = load('usage')
        usage = module.Plugin(PluginContext(self.app, 'usage'))
        info = ProcessInfo(12345, 'C:/Java/bin/java.exe', 'java.exe',
                           'Minecraft 1.20.1 - Singleplayer')
        now = datetime.now()
        usage.last_app = None
        usage.last_mono = 100
        usage.last_wall = now - timedelta(seconds=1)
        with patch.object(module.time, 'monotonic', return_value=101), \
             patch.object(module.platform_win, 'unlocked', return_value=True), \
             patch.object(module.platform_win, 'idle_seconds', return_value=0), \
             patch.object(module.platform_win, 'foreground_app_info', return_value=info):
            usage.tick(now)
        with patch.object(module.time, 'monotonic', return_value=102), \
             patch.object(module.platform_win, 'unlocked', return_value=True), \
             patch.object(module.platform_win, 'idle_seconds', return_value=0), \
             patch.object(module.platform_win, 'foreground_app_info', return_value=info):
            usage.tick(now + timedelta(seconds=1))
        day = (now + timedelta(seconds=1)).date().isoformat()
        rows = self.store.usage(day)
        self.assertEqual(rows[0][0], 'minecraft')
        self.assertNotIn('Minecraft 1.20.1', str(self.store.get('plugin.usage.categories', {})))

    def test_usage_aggregates_and_survives_reopen(self):
        self.store.add_usage('2026-10-19', 'editor.exe', 4)
        self.store.add_usage('2026-10-19', 'editor.exe', 3)
        second = Store(self.temp.name)
        self.assertEqual(second.usage('2026-10-19'), [('editor.exe',7)])
        second.close()

    def test_midnight_split(self):
        usage = load('usage')
        self.assertEqual(list(usage.split_interval(datetime(2026,10,19,23,59,59),datetime(2026,10,20,0,0,1))), [('2026-10-19',1),('2026-10-20',1)])

    def test_idle_and_suspend_not_counted(self):
        module = load('usage')
        usage = module.Plugin(PluginContext(self.app,'usage'))
        now = datetime.now()
        usage.last_app = 'editor.exe'
        usage.last_wall = now-timedelta(seconds=1)
        usage.last_mono = 100
        with patch.object(module.time,'monotonic',return_value=101), patch.object(module.platform_win,'unlocked',return_value=True), patch.object(module.platform_win,'idle_seconds',return_value=500):
            usage.tick(now)
        self.assertEqual(self.store.usage(now.date().isoformat()),[])
        usage.last_app = 'editor.exe'
        usage.last_mono = 100
        usage.last_wall = now-timedelta(hours=1)
        with patch.object(module.time,'monotonic',return_value=3700), patch.object(module.platform_win,'unlocked',return_value=True), patch.object(module.platform_win,'idle_seconds',return_value=0), patch.object(module.platform_win,'foreground_app',return_value='editor.exe'):
            usage.tick(now)
        self.assertEqual(self.store.usage(now.date().isoformat()),[])

    def test_hourly_and_chinese_duration(self):
        self.assertIn('已设置',self.productivity.command('每小时提醒我休息'))
        self.productivity.command('半小时后提醒我喝水')
        reminders = self.store.get('plugin.productivity.reminders')
        self.assertEqual(reminders[0]['interval'],60)
        self.assertAlmostEqual((datetime.fromisoformat(reminders[1]['due'])-datetime.now()).total_seconds(),1800,delta=2)

    def test_overdue_recurring_reminder_does_not_flood(self):
        self.productivity.add_reminder('水',1,1)
        now = datetime.now()+timedelta(days=2)
        self.productivity.tick(now)
        self.productivity.tick(now)
        self.assertEqual(len(self.notifications),1)
        rows = self.store.get('plugin.productivity.reminders')
        self.assertGreater(datetime.fromisoformat(rows[0]['due']),now)

    def test_one_shot_stays_done_after_restart(self):
        self.productivity.add_reminder('会议',1)
        now = datetime.now()+timedelta(minutes=2)
        self.productivity.tick(now)
        restarted = load('productivity').Plugin(PluginContext(self.app,'productivity'))
        restarted.tick(now)
        self.assertEqual(len(self.notifications),1)

    def test_duplicate_focus_rejected(self):
        self.productivity.start_focus(25)
        with self.assertRaises(ValueError):
            self.productivity.start_focus(25)

    def test_shortcut_creation_does_not_execute(self):
        with patch('desktop_pet.platform_win.open_target') as opener:
            self.shortcuts.command('添加快捷入口 工作文件夹 | C:\\Work')
            self.assertEqual(self.shortcuts.items()[0]['target'],'C:\\Work')
            opener.assert_not_called()

    def test_missing_scene_target_validated_before_launch(self):
        self.shortcuts.add_item('文档','C:\\Docs')
        with patch('desktop_pet.platform_win.open_target') as opener:
            with self.assertRaises(ValueError):
                self.shortcuts.launch({'kind':'场景','target':'文档, 已删除'})
            opener.assert_not_called()

    def test_plugin_failure_isolated(self):
        directory = Path(self.temp.name)/'plugins'
        for name, code in [('bad','raise RuntimeError("broken")'),('good','self.called=True')]:
            folder = directory/name
            folder.mkdir(parents=True)
            (folder/'plugin.json').write_text('{"id":"'+name+'","api_version":1}',encoding='utf-8')
            (folder/'plugin.py').write_text('class Plugin:\n def __init__(self,ctx): self.called=False\n def tick(self,now): '+code+'\n',encoding='utf-8')
        manager = PluginManager(self.app,directory)
        manager.load()
        manager.call('tick',datetime.now())
        self.assertNotIn('bad',manager.plugins)
        self.assertTrue(manager.plugins['good'].called)

    def test_disabled_plugin_never_imports(self):
        self.store.set('disabled_plugins',['shortcuts'])
        manager = PluginManager(self.app,BASE/'plugins')
        manager.load()
        self.assertNotIn('shortcuts',manager.plugins)
        self.assertIn('usage',manager.plugins)


if __name__ == '__main__':
    unittest.main()
