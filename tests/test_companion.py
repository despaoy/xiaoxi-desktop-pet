import json
from pathlib import Path
import unittest
from desktop_pet.companion import Dialogue, Timeline

BASE = Path(__file__).resolve().parent.parent


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.config = json.loads((BASE/'assets/characters/silver-dragon/character.json').read_text(encoding='utf-8'))

    def test_blink_has_short_frame_and_loops(self):
        t = Timeline(self.config['actions'],lambda:self.now)
        self.now = 3.11
        self.assertEqual(t.frame(),2)
        self.now = 4.16
        self.assertEqual(t.frame(),0)

    def test_nonloop_returns_idle(self):
        t = Timeline(self.config['actions'],lambda:self.now)
        t.play('success')
        self.now = 3
        self.assertEqual(t.frame(),0)
        self.assertEqual(t.state,'idle')

    def test_unknown_action_preserves_state(self):
        t = Timeline(self.config['actions'],lambda:self.now)
        self.assertFalse(t.play('missing'))
        self.assertEqual(t.state,'idle')

    def test_dialogue_cooldown_and_no_repeat(self):
        d = Dialogue(BASE/'assets/language/zh-CN.json',lambda:self.now)
        first = d.choose('click')
        self.assertIsNone(d.choose('click'))
        self.now = 21
        self.assertNotEqual(first,d.choose('click'))

    def test_important_line_can_bypass_cooldown(self):
        d = Dialogue(BASE/'assets/language/zh-CN.json',lambda:self.now)
        d.choose('click')
        self.assertIsNotNone(d.choose('reminder',force=True))

    def test_all_dialogue_states_have_animation(self):
        d = Dialogue(BASE/'assets/language/zh-CN.json')
        self.assertEqual(sum(len(v['lines']) for v in d.data['events'].values()),50)
        for entry in d.data['events'].values():
            self.assertIn(entry['action'],self.config['actions'])
