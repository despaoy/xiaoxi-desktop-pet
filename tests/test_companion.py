import json
from pathlib import Path
import unittest
from desktop_pet.companion import Dialogue, Timeline, FrameClock

BASE = Path(__file__).resolve().parent.parent


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        # Timeline behavior is independent of the optional, untracked art pack.
        self.config = {'actions': {
            'idle': {'frames': [0, 2, 0], 'durations_ms': [3000, 160, 1000], 'loop': True},
            'click': {'frames': [0, 5, 0], 'durations_ms': [100, 200, 100]},
            'reminder': {'frames': [0, 8, 0], 'durations_ms': [100, 200, 100]},
            'success': {'frames': [0, 12, 0], 'durations_ms': [100, 200, 100]},
        }}

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

    def test_dialogue_states_use_supported_animation_names(self):
        d = Dialogue(BASE/'assets/language/zh-CN.json')
        self.assertEqual(sum(len(v['lines']) for v in d.data['events'].values()),50)
        for entry in d.data['events'].values():
            self.assertIn(entry['action'],self.config['actions'])


class FrameClockTests(unittest.TestCase):
    def test_sixty_fps_deadlines_compensate_render_time(self):
        now = [0.0]
        timer = FrameClock(clock=lambda: now[0])
        now[0] = .005
        self.assertEqual(timer.delay(), 12)
        now[0] = .021
        self.assertEqual(timer.delay(), 12)
        now[0] = .2
        self.assertGreater(timer.delay(), 0)


class LegacyCharacterIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((BASE / 'assets/characters/silver-dragon/character.json').is_file(),
                         'Optional legacy character art absent; see RESOURCES.md')
    def test_real_character_actions_cover_dialogue(self):
        config = json.loads((BASE / 'assets/characters/silver-dragon/character.json').read_text(encoding='utf-8'))
        Timeline(config['actions'])  # Invalid durations still fail when installed.
        dialogue = Dialogue(BASE / 'assets/language/zh-CN.json')
        for entry in dialogue.data['events'].values():
            self.assertIn(entry['action'], config['actions'])
