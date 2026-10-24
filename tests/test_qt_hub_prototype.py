"""Optional real-Qt tests. Run with QT_QPA_PLATFORM=offscreen on headless CI."""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

QT_AVAILABLE = importlib.util.find_spec('PySide6') is not None


@unittest.skipUnless(QT_AVAILABLE, 'Optional Qt prototype requires PySide6')
class QtHubPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from prototypes.qt_hub import HubPrototype
        self.window = HubPrototype()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_window_has_real_alpha_edges_and_opaque_center(self):
        from PySide6.QtCore import Qt
        self.assertTrue(self.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(self.window.mask().isEmpty())
        image = self.window.grab().toImage()
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(image.pixelColor(image.width() // 2, 20).alpha(), 255)
        alphas = {image.pixelColor(x, y).alpha() for x in range(45) for y in range(45)}
        self.assertTrue(any(0 < alpha < 255 for alpha in alphas), alphas)

    def test_repeated_navigation_and_demo_toggle_remain_consistent(self):
        for _ in range(5):
            self.window.show_focus()
            self.assertEqual(self.window.pages.currentIndex(), 1)
            self.assertTrue(self.window.tab_group.button(1).isChecked())
            self.window.demo_button.click()
            self.assertTrue(self.window.demo_running)
            self.window.demo_button.click()
            self.assertFalse(self.window.demo_running)
            self.window.tab_group.button(0).click()
            self.assertEqual(self.window.pages.currentIndex(), 0)
        self.assertIn('没有修改真实', self.window.feedback.text())

    def test_small_window_uses_vertical_scroll_and_preserves_labels(self):
        self.window.resize(420, 430)
        self.app.processEvents()
        areas = [self.window.pages.widget(0), self.window.pages.widget(1)]
        self.assertGreater(areas[0].verticalScrollBar().maximum(), 0)
        self.assertEqual(areas[0].horizontalScrollBar().maximum(), 0)
        self.assertIn('演示数据', self.window.feedback.text())

    def test_escape_closes_and_window_can_be_shown_again(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        self.assertFalse(self.window.isVisible())
        self.window.show()
        self.assertTrue(self.window.isVisible())

    def test_original_portrait_and_greeting_are_primary(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        from prototypes.qt_hub import AVATAR
        self.assertTrue(AVATAR.is_file())
        self.assertIn('你回来啦', self.window.corner.bubble.text())
        portraits = [item for item in self.window.corner.findChildren(QLabel)
                     if item.accessibleName() == '小汐的原版白发小龙娘头像']
        self.assertEqual(len(portraits), 1)
        self.assertEqual(portraits[0].pixmap().size().width(), 80)
        for text in ('摸摸头', '打招呼', '歇一会'):
            control = next(item for item in self.window.findChildren(QPushButton)
                           if item.text() == text)
            control.click()
            self.assertIn('未触发真实', self.window.feedback.text())
        self.assertIn('安静坐一会儿', self.window.corner.bubble.text())

    def test_clean_existing_avatar_has_no_opaque_black_border(self):
        from PySide6.QtWidgets import QLabel
        from prototypes.qt_hub import AVATAR
        self.assertEqual(AVATAR.name, 'app-icon.png')
        portraits = [item for item in self.window.findChildren(QLabel)
                     if item.accessibleName() in ('小汐的原版白发小龙娘头像', '小汐在身边')]
        self.assertEqual(len(portraits), 2)
        for portrait in portraits:
            image = portrait.pixmap().toImage()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            # Inspect only the outer band; dark eyes/hair details inside must survive.
            for x in range(image.width()):
                for y in range(image.height()):
                    if min(x, y, image.width()-1-x, image.height()-1-y) >= 5:
                        continue
                    color = image.pixelColor(x, y)
                    self.assertFalse(color.alpha() > 240 and
                                     max(color.red(), color.green(), color.blue()) < 32,
                                     (portrait.accessibleName(), x, y, color.getRgb()))

    def test_screenshot_process_exits_cleanly_with_portrait_pixmaps(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'preview.png'
            result = subprocess.run(
                [sys.executable, '-m', 'prototypes.qt_hub', '--screenshot', str(destination)],
                cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(destination.is_file())
            self.assertGreater(destination.stat().st_size, 1000)

    def test_all_buttons_have_accessible_text_and_icons(self):
        from PySide6.QtWidgets import QPushButton
        for control in self.window.findChildren(QPushButton):
            self.assertTrue(control.text())
            self.assertTrue(control.accessibleName())
            self.assertFalse(control.icon().isNull())


if __name__ == '__main__':
    unittest.main()
