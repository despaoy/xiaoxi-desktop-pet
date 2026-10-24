"""Headless regressions for renderer policy and Python-to-renderer state."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from desktop_pet.app import App
from desktop_pet.companion import Dialogue
from plugins.companion.plugin import Plugin

BASE = Path(__file__).resolve().parent.parent


class BehaviorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for pure renderer tests')
    def test_javascript_behavior_suite(self):
        result = subprocess.run(['node', '--test', str(BASE/'tests/js/behavior-controller.test.js')],
                                cwd=BASE, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def app(self):
        app = App.__new__(App)
        data = {'dnd': True, 'companion.speech': False, 'pet.behavior': {'actions': False}}
        app.store = SimpleNamespace(get=lambda k, default=None: data.get(k, default))
        app.root = SimpleNamespace(focus_get=lambda: SimpleNamespace(winfo_class=lambda: 'TEntry'))
        app.focused = False
        app.pet_hidden = True
        app.live2d_scale = .8
        app.bubble = object()
        app.queue = []
        app.dialogue = SimpleNamespace(data={'actions': {'greeting': ['你好呀。']}})
        return app

    def test_context_includes_quiet_flags_but_no_input_text(self):
        app = self.app()
        state = app.live2d_context()
        self.assertTrue(state['editing'])
        self.assertTrue(state['dnd'])
        self.assertTrue(state['notificationBusy'])
        self.assertFalse(state['speechEnabled'])
        self.assertFalse(state['visible'])
        self.assertEqual(state['actionLines']['greeting'], ['你好呀。'])
        self.assertEqual(set(state), {'focused', 'preferences', 'scale', 'visible', 'dnd',
                                    'speechEnabled', 'notificationBusy', 'editing', 'actionLines'})
        app.root = SimpleNamespace(focus_get=lambda: None)
        app.bubble = None
        self.assertFalse(app.live2d_context()['editing'])
        self.assertFalse(app.live2d_context()['notificationBusy'])
        app.queue.append(('到时间了', '测试', None))
        self.assertTrue(app.live2d_context()['notificationBusy'])

    def test_explicit_actions_forward_current_preferences_before_playing(self):
        app = self.app()
        app.live2d = SimpleNamespace(ready=True, state=Mock())
        plugin = Plugin(SimpleNamespace(app=app, add_action=Mock()))
        plugin.perform('look')
        state = app.live2d.state.call_args.kwargs
        self.assertEqual(state['interaction'], 'look')
        self.assertTrue(state['visible'])
        self.assertFalse(app.pet_hidden)
        self.assertTrue(state['dnd'])
        self.assertFalse(state['speechEnabled'])

    def test_old_language_packs_remain_valid_and_action_lines_validate(self):
        data = json.loads((BASE/'assets/language/zh-CN.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'language.json'
            old = {k: v for k, v in data.items() if k != 'actions'}
            path.write_text(json.dumps(old), encoding='utf-8')
            self.assertIsNotNone(Dialogue(path).choose('greeting'))
            for invalid in [[], {'look': []}, {'look': '文字不是列表'}, {'look': ['x'*41]}]:
                data['actions'] = invalid
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(ValueError):
                    Dialogue(path)

    def test_new_controller_is_included_in_page_and_windows_package(self):
        page = (BASE/'review/live2d/pet.html').read_text(encoding='utf-8')
        self.assertLess(page.index('behavior-controller.js'), page.index('src="pet.js"'))
        self.assertIn('behavior-controller.js', (BASE/'XiaoXi.spec').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
