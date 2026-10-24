"""Real offscreen widget regression tests. Run with Qt dependency available."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget, QCheckBox
    from desktop_pet.qt_hub.productivity import FocusPage, ShortcutsPage
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith(("PySide6", "shiboken6")):
        raise unittest.SkipTest("Optional PySide6 frontend is not installed") from exc
    raise


class Owner:
    def __init__(self): self.calls=[]
    def dispatch(self,command,payload,source_button=None,on_success=None):
        self.calls.append((command,payload,source_button,on_success))
        if source_button: source_button.setEnabled(False)
        return str(len(self.calls))
    def toast(self,*args,**kwargs): pass


class ProductivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self): self.owner=Owner();self.pages=[]
    def tearDown(self):
        for page in self.pages: page.close();page.deleteLater()
        self.app.processEvents()
    def page(self,kind):
        p=kind(self.owner);self.pages.append(p)
        p.update_snapshot({'todos':[],'reminders':[],'shortcuts':[],'actions':[],'favorites':[]})
        return p
    def test_timer_and_focus_dispatch(self):
        p=self.page(FocusPage);p.minutes.setValue(42);p.start_button.click()
        self.assertEqual(self.owner.calls[-1][:2],('timer.start',{'minutes':42}))
        p.focus_mode.click();self.assertEqual(self.owner.calls[-1][:2],('settings.focused',{'enabled':True}))
        p.update_snapshot({'now':'2026-10-24T13:00:00','timer':{'due':'2026-10-24T13:10:00','minutes':25,'kind':'专注'}})
        self.assertEqual(p.clock.text(),'10:00');self.assertTrue(p.pause_button.isEnabled());self.assertFalse(p.start_button.isEnabled())
        p.update_snapshot({'timer':{'paused':True,'remaining':125,'minutes':25}})
        self.assertEqual(p.clock.text(),'02:05');self.assertTrue(p.resume_button.isEnabled())
    def test_todo_draft_survives_poll_and_save_retry(self):
        p=self.page(FocusPage);p._todo_editor(create=True);e=p._editors[-1]
        title=e.findChild(QLineEdit);title.setText('尚未保存的草稿')
        p.update_snapshot({'todos':[{'id':'a','title':'已有事项','done':False}]})
        self.assertEqual(title.text(),'尚未保存的草稿')
        e.save_button.click();self.assertEqual(self.owner.calls[-1][1],{'title':'尚未保存的草稿'})
        self.assertFalse(e.save_button.isEnabled());e.save_button.click();self.assertEqual(len(self.owner.calls),1)
        # Simulate host rejection: the same form must be retryable, not silently stuck.
        e.save_button.setEnabled(True);title.setText('修正后的草稿');e.save_button.click()
        self.assertEqual(len(self.owner.calls),2);self.assertEqual(self.owner.calls[-1][1]['title'],'修正后的草稿')
        self.owner.calls[-1][3]();self.assertNotIn(e,p._editors)
    def test_repeat_reminder_single_form(self):
        p=self.page(FocusPage);p._reminder_editor(create=True);e=p._editors[-1]
        e.findChild(QLineEdit).setText('喝水');e.findChild(QCheckBox).setChecked(True);e.save_button.click()
        self.assertEqual(self.owner.calls[-1][:2],('reminder.save',{'title':'喝水','minutes':30,'interval':60}))
    def test_scene_uses_names_and_filter_preserves_data(self):
        p=self.page(ShortcutsPage)
        p.update_snapshot({'shortcuts':[{'id':'a','name':'文档','target':'https://example.com','kind':'入口'}]})
        p._scene_editor(create=True);e=p._editors[-1];e.findChild(QLineEdit).setText('学习')
        choices=e.findChild(QListWidget);choices.item(0).setCheckState(Qt.CheckState.Checked);e.save_button.click()
        self.assertEqual(self.owner.calls[-1][:2],('shortcut.save',{'name':'学习','target':'文档','kind':'场景'}))
        p.search.setText('找不到');self.assertEqual(p.entries.rowCount(),0)
        p.search.clear();self.assertEqual(p.entries.rowCount(),1)
    def test_system_commands_are_registered(self):
        p=self.page(ShortcutsPage);p.update_snapshot({'actions':[{'id':'shortcuts.volume_up','enabled':True}]})
        p.system_buttons[1].click();self.assertEqual(self.owner.calls[-1][:2],('action.invoke',{'id':'shortcuts.volume_up'}))
        self.assertFalse(p.system_buttons[0].isEnabled())

if __name__=='__main__':unittest.main()
