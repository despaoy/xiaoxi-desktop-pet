"""Real Qt -> command adapter -> backend -> temporary SQLite integration.

Only desktop/OS effects are replaced. Requests are queued, exactly as the child
process transport does, to exercise pending locks and acknowledgements.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit
    from desktop_pet.qt_hub.window import HubWindow
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith(('PySide6', 'shiboken6')):
        raise unittest.SkipTest('Optional PySide6 frontend is not installed') from exc
    raise
import test_hub_backend
from desktop_pet.actions import Action
from desktop_pet.storage import Store


class HubIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        test_hub_backend.BackendTests.setUp(self)
        self.app.plugins.records=[]
        self.app.favorite_ids=lambda:self.store.get('navigation.favorites',[])
        self.app.pet_hidden=False
        self.app.history=[]
        self.app.live2d_mode=True
        self.app.live2d_scale=.8
        self.app.pet_width,self.app.pet_height=160,240
        self.app.pet_x,self.app.pet_y=100,100
        self.app.live2d_size=lambda:(int(200*self.app.live2d_scale),int(300*self.app.live2d_scale))
        self.app.root=SimpleNamespace(winfo_screenwidth=lambda:1920,winfo_screenheight=lambda:1080)
        self.app.pet=SimpleNamespace(geometry=Mock())
        self.app.live2d=None
        self.app.close_hub=lambda:None
        self.app.registry.add(Action('companion.greeting','companion','打招呼',lambda:None))
        self.app.registry.add(Action('companion.wave','companion','挥挥手',lambda:None))
        self.app.registry.add(Action('shortcuts.lock','shortcuts','锁定电脑',lambda:None))
        self.startup=patch('desktop_pet.platform_win.startup_enabled',return_value=False)
        self.startup.start()
        self.requests=[];self.sent=[]
        self.window=HubWindow(self.send)
        self.window.apply_snapshot(self.backend.snapshot())

    def tearDown(self):
        self.window.watchdog.stop()
        self.window.hide()
        self.window.deleteLater()
        self.qt.processEvents()
        self.startup.stop()
        test_hub_backend.BackendTests.tearDown(self)

    def send(self,message):
        self.sent.append(message.copy());self.requests.append(message.copy())

    def flush(self):
        while self.requests:
            message=self.requests.pop(0)
            try:
                value=self.backend.execute(message['action'],message['payload'])
                result={'id':message['id'],'ok':True,'result':value}
            except Exception as exc:
                result={'id':message['id'],'ok':False,'error':str(exc)}
            result['snapshot']=self.backend.snapshot()
            self.window.apply_result(result)
            self.assertTrue(result['ok'],result.get('error'))
        self.qt.processEvents()

    def actions(self,name): return [m for m in self.sent if m['action']==name]

    def test_editor_save_persists_and_poll_preserves_draft(self):
        page=self.window.page_widgets['focus']
        page._todo_editor(create=True)
        editor=page._editors[-1];title=editor.findChild(QLineEdit)
        title.setText('在小屋里完成的事项')
        self.window.apply_snapshot(self.backend.snapshot())
        self.assertEqual(title.text(),'在小屋里完成的事项')
        editor.save_button.click()
        self.assertFalse(editor.save_button.isEnabled())
        self.window.apply_snapshot(self.backend.snapshot())
        self.assertFalse(editor.save_button.isEnabled())
        self.flush()
        self.assertEqual(page.todo_table.rowCount(),1)
        reopened=Store(self.temp.name)
        try:self.assertEqual(reopened.get('plugin.productivity.todos')[0]['title'],'在小屋里完成的事项')
        finally:reopened.close()

    def test_timer_buttons_and_pending_lock_across_snapshot(self):
        page=self.window.page_widgets['focus'];page.minutes.setValue(35)
        page.start_button.click();self.assertFalse(page.start_button.isEnabled())
        self.window.apply_snapshot(self.backend.snapshot())
        self.assertFalse(page.start_button.isEnabled())
        page.start_button.click();self.assertEqual(len(self.actions('timer.start')),1)
        self.flush()
        self.assertEqual(self.store.get('plugin.productivity.timer')['minutes'],35)
        self.assertTrue(page.pause_button.isEnabled())
        page.pause_button.click();self.flush()
        self.assertTrue(self.store.get('plugin.productivity.timer')['paused'])
        self.assertTrue(page.resume_button.isEnabled())

    def test_focus_true_false_true_each_emits_after_ack(self):
        control=self.window.page_widgets['settings'].focused
        for desired in [True,False,True]:
            control.click();self.flush();self.assertEqual(self.app.focused,desired)
        self.assertEqual([m['payload']['enabled'] for m in self.actions('settings.focused')],[True,False,True])

    def test_double_click_selection_excludes_non_companion_actions(self):
        combo=self.window.page_widgets['settings'].double
        self.assertEqual([combo.itemData(i) for i in range(combo.count())],['companion.greeting','companion.wave'])
        combo.setCurrentIndex(1);combo.activated.emit(1);self.flush()
        self.assertEqual(self.store.get('navigation.double_click'),'companion.wave')
        self.assertNotIn('shortcuts.lock',[combo.itemData(i) for i in range(combo.count())])

    def test_slider_keyboard_commits_to_real_backend(self):
        page=self.window.page_widgets['interaction'];slider=page.scale
        self.assertTrue(slider.isEnabled());self.assertEqual(slider.value(),80)
        QTest.keyClick(slider,Qt.Key.Key_Right)
        # Timer debounce protects keyboard-driven value from polling overwrites.
        self.window.apply_snapshot(self.backend.snapshot())
        self.assertEqual(slider.value(),81)
        QTest.qWait(250)
        self.assertEqual(len(self.actions('settings.scale')),1)
        self.flush()
        self.assertAlmostEqual(self.store.get('live2d.scale'),.81)
        self.assertEqual(self.app.live2d_scale,.81)
        self.app.pet.geometry.assert_called_once()

if __name__=='__main__':unittest.main()
