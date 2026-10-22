import tempfile
import unittest
from pathlib import Path

from desktop_pet import apps
from desktop_pet.platform_win import ProcessInfo
from desktop_pet.storage import Store


class AppIdentityTests(unittest.TestCase):
    def test_aliases_resolve_to_product_names(self):
        self.assertEqual(apps.resolve_key('chrome.exe').display, 'Google Chrome')
        self.assertEqual(apps.resolve_key('msedge.exe').display, 'Microsoft Edge')
        self.assertEqual(apps.resolve_key('Hades2.exe').display, 'Hades II')
        self.assertEqual(apps.resolve_key('steamwebhelper.exe').id, 'steam')
        self.assertEqual(apps.resolve_key('TRAE_CN-Setup-x64.tmp').id, 'trae-installer')

    def test_installer_and_shell_are_hidden(self):
        self.assertTrue(apps.resolve_key('TRAE_CN-Setup-x64.tmp').hidden)
        self.assertTrue(apps.resolve_key('PickerHost.exe').hidden)
        self.assertTrue(apps.resolve_key('ShellExperienceHost.exe').hidden)

    def test_java_title_is_used_only_transiently(self):
        info = ProcessInfo(10, 'C:/Java/bin/java.exe', 'java.exe',
                           'Minecraft 1.20.1 - Singleplayer')
        entry = apps.resolve_info(info)
        self.assertEqual(entry.id, 'minecraft')
        self.assertEqual(entry.display, 'Minecraft')
        unknown = apps.resolve_info(
            ProcessInfo(11, 'C:/Java/bin/java.exe', 'java.exe', 'Some Build Tool'))
        self.assertEqual(unknown.id, 'java')

    def test_self_process_is_excluded(self):
        info = ProcessInfo(99, 'C:/app/pythonw.exe', 'pythonw.exe', '小汐')
        entry = apps.resolve_info(info, self_pids={99})
        self.assertTrue(entry.self_process)
        self.assertTrue(entry.hidden)


class UsageGroupingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent / 'data-tests')
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_variants_and_canonical_rows_are_merged(self):
        day = '2026-10-22'
        self.store.add_usage(day, 'chrome.exe', 30)
        self.store.add_usage(day, 'chrome_proxy.exe', 20)
        self.store.add_usage(day, 'chrome', 10)
        rows = self.store.usage_records(day)
        chrome = next(row for row in rows if row.id == 'chrome')
        self.assertEqual(chrome.seconds, 60)
        self.assertEqual(chrome.variants, 3)
        self.assertEqual(chrome.display, 'Google Chrome')

    def test_hidden_rows_are_excluded_from_total(self):
        day = '2026-10-22'
        self.store.add_usage(day, 'chrome.exe', 60)
        self.store.add_usage(day, 'TRAE_CN-Setup-x64.tmp', 120)
        self.store.add_usage(day, 'PickerHost.exe', 60)
        visible = self.store.usage_records(day)
        self.assertEqual([row.id for row in visible], ['chrome'])
        self.assertEqual(self.store.usage_total(day), 60)
        all_rows = self.store.usage_records(day, include_hidden=True)
        self.assertEqual(len(all_rows), 3)

    def test_category_override_uses_stable_app_id(self):
        day = '2026-10-22'
        self.store.set('plugin.usage.categories', {'chrome': '娱乐'})
        self.store.add_usage(day, 'chrome.exe', 60)
        row = self.store.usage_records(day)[0]
        self.assertEqual(row.category, 'fun')
        self.assertEqual(row.label, '娱乐与游戏')


if __name__ == '__main__':
    unittest.main()
