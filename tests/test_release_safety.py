import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import io

from desktop_pet.storage import Store

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_safety', BASE / 'tools/release_safety.py')
release_safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_safety)


class ReleaseSafetyTests(unittest.TestCase):
    def test_missing_output_is_valid_for_first_build(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(release_safety.audit_distribution(Path(folder) / 'new'), [])

    def test_known_data_and_database_sidecars_rejected_without_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = ['data/companion.sqlite3', '_internal/data/app.log',
                     'cache/old.sqlite3-wal', 'history.DB', 'data-tests/example.json']
            for name in paths:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('private sentinel', encoding='utf-8')
            findings = release_safety.audit_distribution(root)
            self.assertTrue(set(paths[:-1]).issubset(findings))
            self.assertIn('data-tests', findings)
            for name in paths:
                self.assertEqual((root / name).read_text(), 'private sentinel')

    def test_command_requires_output_after_build_and_reports_blocked_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            command = [sys.executable, str(BASE / 'tools/release_safety.py')]
            missing = subprocess.run(command + [str(root / 'missing'), '--require-output'],
                                     capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('output is missing', missing.stderr)
            (root / 'data').mkdir()
            blocked = subprocess.run(command + [str(root)], capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn('nothing was deleted', blocked.stderr)
            self.assertTrue((root / 'data').is_dir())

    def test_normal_assets_not_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['XiaoXi.exe', '_internal/assets/language/zh-CN.json',
                         '_internal/review/live2d/model.model3.json']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            self.assertEqual(release_safety.audit_distribution(root), [])

    def test_empty_data_directory_is_also_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'data').mkdir()
            self.assertEqual(release_safety.audit_distribution(folder), ['data'])

    def test_symlink_is_rejected_without_following_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'output'
            output.mkdir()
            private = root / 'private'
            private.mkdir()
            (private / 'secret.txt').write_text('sentinel')
            try:
                (output / 'asset-link').symlink_to(private, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink creation not permitted on this host')
            self.assertEqual(release_safety.audit_distribution(output), ['asset-link'])
            self.assertTrue((private / 'secret.txt').exists())

    def test_unreadable_subtree_fails_audit_and_command(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            hidden = root / 'unreadable'
            hidden.mkdir()
            (hidden / 'companion.sqlite3').write_text('private sentinel')
            real_scandir = release_safety.os.scandir

            def denied_scandir(path):
                if Path(path) == hidden:
                    raise PermissionError('cannot inspect subtree')
                return real_scandir(path)

            with patch.object(release_safety.os, 'scandir', side_effect=denied_scandir):
                with self.assertRaises(PermissionError):
                    release_safety.audit_distribution(root)
                with patch('sys.stderr', new_callable=io.StringIO) as stderr:
                    with self.assertRaises(SystemExit) as stopped:
                        release_safety.main([str(root)])
                    self.assertEqual(stopped.exception.code, 1)
                    self.assertIn('cannot inspect subtree', stderr.getvalue())
            self.assertEqual((hidden / 'companion.sqlite3').read_text(), 'private sentinel')

    def test_store_initializes_from_no_bundled_data_and_stays_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'data'
            self.assertFalse(destination.exists())
            store = Store(destination)
            try:
                self.assertEqual(store.usage('2026-10-24'), [])
                self.assertIsNone(store.get('plugin.productivity.todos'))
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)
            finally:
                store.close()

    def test_build_audits_before_and_after_pyinstaller_without_data_copy(self):
        script = (BASE / 'build-desktop.ps1').read_text(encoding='utf-8-sig')
        build = script.index('PyInstaller --noconfirm')
        self.assertLess(script.index('tools/release_safety.py'), build)
        self.assertGreater(script.rindex('tools/release_safety.py'), build)
        self.assertNotIn('Copy-Item', script)


if __name__ == '__main__':
    unittest.main()
