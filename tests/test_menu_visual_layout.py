"""Headless presentation checks; these do not replace real Tk/Windows rendering."""
import ast
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

try:
    from PIL import Image, ImageFont
except ImportError:
    Image = ImageFont = None

from desktop_pet.action_usage import ELIGIBLE_IDS
from desktop_pet.actions import CATEGORIES
from desktop_pet.menu import QuickButton, draw_menu_icon
from desktop_pet.menu_style import display_scale, layout_width, shortcut_presentation, wrap_label

ROOT = Path(__file__).resolve().parents[1]
CJK_FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')


class PresentationTests(unittest.TestCase):
    def test_reported_clipped_actions_keep_complete_distinct_names(self):
        for key, title in (
            ('productivity.focus', '继续专注'),
            ('companion.relax', '轻轻放松'),
            ('companion.look', '看看周围'),
        ):
            with self.subTest(action=key):
                label, icon = shortcut_presentation(key, title)
                self.assertEqual(label, title)
                self.assertNotIn('…', label)
                self.assertTrue(icon)

    def test_focus_state_and_break_kind_are_not_lost(self):
        self.assertEqual(shortcut_presentation('productivity.focus', '开始 25 分钟专注'), ('开始专注', 'clock'))
        for title in ('暂停专注', '继续专注', '暂停休息', '继续休息', '开始 45 分钟专注'):
            with self.subTest(title=title):
                self.assertEqual(shortcut_presentation('productivity.focus', title), (title, 'clock'))

    def test_do_not_disturb_opposite_actions_remain_distinct(self):
        self.assertEqual(shortcut_presentation('settings.dnd', '开启免打扰'), ('开启免扰', 'moon'))
        self.assertEqual(shortcut_presentation('settings.dnd', '关闭免打扰'), ('关闭免扰', 'moon'))
        self.assertEqual(shortcut_presentation('settings.dnd', '未来的新模式')[0], '未来的新模式')

    def test_every_recommended_builtin_has_a_meaningful_visible_label(self):
        expected = {
            'companion.greeting': '打招呼', 'companion.blink': '眨眨眼',
            'companion.stretch': '舒展翅膀', 'companion.mouth': '嘴型演示',
            'companion.look': '看看周围', 'companion.relax': '轻轻放松',
            'companion.idle': '恢复待机', 'productivity.focus': '开始专注',
            'productivity.reminder': '添加提醒', 'productivity.todo': '添加待办',
            'shortcuts.mute': '静音切换', 'shortcuts.volume_up': '音量增加',
            'shortcuts.volume_down': '音量降低', 'usage.today': '今日排行',
            'settings.dnd': '开启免扰', 'settings.history': '通知记录',
        }
        self.assertEqual(set(expected), set(ELIGIBLE_IDS))
        for key, label in expected.items():
            title = {'productivity.focus': '开始 25 分钟专注', 'settings.dnd': '开启免打扰'}.get(key, 'original full title')
            with self.subTest(action=key):
                self.assertEqual(shortcut_presentation(key, title)[0], label)
                self.assertNotIn('…', label)

    def test_basic_navigation_import_does_not_require_pillow(self):
        import subprocess
        import sys
        script = '''import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == "PIL" or name.startswith("PIL."):
        raise ImportError("Pillow deliberately unavailable")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from desktop_pet.navigation import Navigation
from desktop_pet.menu import Image
assert Image is None
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_future_action_is_not_silently_renamed(self):
        title = '一个很长但包含重要含义的新动作'
        self.assertEqual(shortcut_presentation('plugin.future', title)[0], title)

    def test_dpi_scaling_is_finite_bounded_and_handles_invalid_input(self):
        for dpi, expected in ((96, 1), (120, 1.25), (144, 1.5), (192, 2), (0, .75), (-96, .75), (96000, 4)):
            with self.subTest(dpi=dpi):
                self.assertEqual(display_scale(dpi), expected)
        for dpi in (None, 'invalid', float('nan'), float('inf'), -float('inf'), 10 ** 1000):
            with self.subTest(dpi_type=type(dpi).__name__):
                self.assertEqual(display_scale(dpi), 1)
                self.assertTrue(math.isfinite(display_scale(dpi)))

    def test_metric_budget_includes_three_shortcuts_not_just_category(self):
        measure = lambda text: len(text) * 12
        labels = ('继续专注', '轻轻放松', '看看周围')
        width = layout_width(measure, labels, ('动作与互动',), 1, 1920)
        budget = (width - 40) // 3 - 34
        self.assertGreaterEqual(budget, max(map(measure, labels)))
        wider = layout_width(measure, ('开始 45 分钟专注',), ('动作与互动',), 1, 1920)
        self.assertGreater(wider, width)

    def test_small_screen_wraps_without_losing_characters(self):
        measure = lambda text: len(text) * 12
        title = '一个很长但包含重要含义的新动作'
        width = layout_width(measure, (title,), ('动作与互动',), 1, 220)
        self.assertEqual(width, 204)
        lines = wrap_label(title, measure, (width - 40) // 3 - 34)
        self.assertEqual(''.join(lines), title)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(measure(line) <= 20 for line in lines))

    def test_wrap_handles_empty_and_too_narrow_budget_without_ellipsis(self):
        measure = lambda text: len(text) * 12
        self.assertEqual(wrap_label('', measure, 20), [''])
        for budget in (0, 1, 12, 24):
            lines = wrap_label('继续休息', measure, budget)
            self.assertEqual(''.join(lines), '继续休息')
            self.assertNotIn('…', ''.join(lines))


class CanvasRecorder:
    def __init__(self):
        self.shapes = []
        self.texts = []

    def _shape(self, kind, *coords, **kwargs):
        self.shapes.append((kind, coords, kwargs))

    def create_line(self, *coords, **kwargs):
        self._shape('line', *coords, **kwargs)

    def create_oval(self, *coords, **kwargs):
        self._shape('oval', *coords, **kwargs)

    def create_arc(self, *coords, **kwargs):
        self._shape('arc', *coords, **kwargs)

    def create_rectangle(self, *coords, **kwargs):
        self._shape('rectangle', *coords, **kwargs)

    def create_text(self, *coords, **kwargs):
        self.texts.append((coords, kwargs))

    def delete(self, *_args):
        self.shapes.clear()
        self.texts.clear()


class IconTests(unittest.TestCase):
    def test_line_icons_stay_inside_declared_box_without_font_glyphs(self):
        for icon in ('folder', 'speaker', 'eye', 'eye_off', 'power', 'moon', 'home', 'heart', 'clock', 'bell', 'chart', 'settings', 'check', 'sparkle'):
            with self.subTest(icon=icon):
                canvas = CanvasRecorder()
                draw_menu_icon(canvas, 10, 20, icon, 24, '#8866aa')
                self.assertTrue(canvas.shapes)
                self.assertEqual(canvas.texts, [])
                for _, coordinates, _ in canvas.shapes:
                    for index, value in enumerate(coordinates):
                        low = 10 if index % 2 == 0 else 20
                        self.assertGreaterEqual(value, low)
                        self.assertLessEqual(value, low + 24)


@unittest.skipUnless(ImageFont is not None and CJK_FONT.exists(), 'Optional Linux CJK font unavailable; not a Tk rendering test')
class ActualCjkMetricsTests(unittest.TestCase):
    def test_reported_labels_fit_and_canvas_draws_complete_names_at_common_dpi(self):
        labels = ('继续专注', '轻轻放松', '看看周围')
        categories = tuple(title for title, _ in CATEGORIES.values())
        for scale in (1, 1.25, 1.5, 2):
            font = ImageFont.truetype(str(CJK_FONT), round(12 * scale), index=2)
            measure = font.getlength
            width = layout_width(measure, labels, categories, scale, 3840)
            cell_width = (width - round(40 * scale)) // 3
            budget = cell_width - round(34 * scale)
            for label in labels:
                with self.subTest(scale=scale, label=label):
                    self.assertLessEqual(measure(label), budget)
                    lines = wrap_label(label, measure, budget)
                    self.assertEqual(lines, [label])
                    canvas = CanvasRecorder()
                    canvas.scale = scale
                    canvas.font = SimpleNamespace(measure=measure)
                    canvas.hover = False
                    canvas.lines = lines
                    canvas.icon_name = 'clock'
                    canvas.winfo_width = lambda: cell_width
                    canvas.winfo_height = lambda: round(34 * scale)
                    QuickButton._draw(canvas)
                    self.assertEqual(len(canvas.texts), 1)
                    (x, _), options = canvas.texts[0]
                    self.assertEqual(options['text'], label)
                    self.assertGreaterEqual(x, 0)
                    self.assertLessEqual(x + measure(label), cell_width)


class PortraitAssetTests(unittest.TestCase):
    @unittest.skipUnless(Image is not None, 'Optional Pillow unavailable for pixel inspection')
    def test_portrait_is_different_rgba_asset_with_transparent_corners(self):
        portrait = ROOT / 'assets/ui/menu-portrait-lavender.png'
        old = ROOT / 'assets/ui/menu-avatar-72.png'
        self.assertNotEqual(hashlib.sha256(portrait.read_bytes()).digest(), hashlib.sha256(old.read_bytes()).digest())
        with Image.open(portrait) as image:
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.width, image.height)
            self.assertGreaterEqual(image.width, 144)
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertGreater(image.getpixel((image.width // 2, image.height // 2))[3], 200)

    def test_packaging_data_directory_includes_new_portrait(self):
        # Evaluate just declarative data assignments, never run PyInstaller.
        tree = ast.parse((ROOT / 'XiaoXi.spec').read_text(encoding='utf-8'))
        selected = [node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id in ('root', 'datas') for target in node.targets)]
        namespace = {'Path': Path, 'SPECPATH': str(ROOT)}
        exec(compile(ast.Module(body=selected, type_ignores=[]), 'packaging-data', 'exec'), namespace)
        asset = ROOT / 'assets/ui/menu-portrait-lavender.png'
        self.assertTrue(any(asset.is_relative_to(Path(source)) and destination == 'assets/ui'
                            for source, destination in namespace['datas']))


if __name__ == '__main__':
    unittest.main()
