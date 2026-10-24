"""Safe, clearly labelled visual preview. Never connects to a user store."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path


def demo_snapshot():
    now=datetime.now()
    companion=[('greeting','打招呼'),('blink','眨眨眼'),('stretch','伸个懒腰'),('look','看看周围'),('relax','轻轻放松'),('mouth','嘴型演示'),('idle','恢复待机')]
    actions=[{'id':'companion.'+key,'title':title,'category':'companion','enabled':True} for key,title in companion]
    actions += [{'id':key,'title':title,'category':'shortcuts','enabled':True} for key,title in [('shortcuts.volume_up','音量增加'),('shortcuts.volume_down','音量降低'),('shortcuts.mute','静音'),('shortcuts.lock','锁定电脑')]]
    return {'version':1,'now':now.isoformat(),'timer':{'minutes':25,'due':(now+timedelta(minutes=18,seconds=42)).isoformat(),'kind':'专注','paused':False},'focused':False,'dnd':False,
      'todos':[{'id':'demo-todo-1','title':'把今天最重要的一件事做好','done':False},{'id':'demo-todo-2','title':'整理灵感和笔记','done':False},{'id':'demo-todo-3','title':'给自己倒一杯水','done':True,'completed':now.isoformat()}],
      'reminders':[{'id':'demo-reminder','title':'起来走走，看看窗外','due':(now+timedelta(minutes=35)).isoformat(),'interval':60}],
      'shortcuts':[{'id':'demo-1','name':'学习笔记','target':'https://example.com','kind':'入口'},{'id':'demo-2','name':'灵感文件夹','target':'C:/Notes','kind':'入口'},{'id':'demo-3','name':'开始学习','target':'学习笔记,灵感文件夹','kind':'场景'}],
      'actions':actions,'favorites':['companion.greeting','companion.stretch','shortcuts.mute'],
      'summary':{'focus_minutes':75,'completed_todos':1},
      'usage':{'days':7,'enabled':True,'total':9300,'break_minutes':50,'error':None,'daily':[{'day':(now-timedelta(days=i)).date().isoformat(),'seconds':seconds} for i,seconds in zip(range(6,-1,-1),[1200,1800,600,1800,900,1200,1800])],
        'records':[{'id':'demo-editor','display':'代码编辑器','category':'工作','seconds':5400,'limit':120},{'id':'demo-browser','display':'浏览器','category':'浏览','seconds':2700,'limit':0},{'id':'demo-notes','display':'笔记','category':'学习','seconds':1200,'limit':0}],
        'categories':[{'name':'工作','seconds':5400},{'name':'浏览','seconds':2700},{'name':'学习','seconds':1200}], 'category_choices':[{'id':x,'label':x} for x in ['工作','学习','娱乐','浏览','沟通','其他']]},
      'settings':{'behavior':{key:True for key in ['breathe','blink','wings','hair','mouth','actions']},'speech':True,'pet_visible':True,'scale':.8,'double_click':'companion.greeting','favorite_hotkeys':False,'startup':False,'live2d_mode':True,'hotkey_registered':True},
      'plugins':[{'id':'companion','name':'动作与互动','version':'1.0','status':'已加载','enabled':True,'description':'小动作和陪伴短句','permissions':[]},{'id':'productivity','name':'专注与事项','version':'1.0','status':'已加载','enabled':True,'description':'专注计时、待办与提醒','permissions':['notifications']}],
      'history':[{'at':now.strftime('%H:%M'),'title':'做得不错呀','body':'上一段专注已经完成，休息一下吧。'}],
      'language':{'events':{'welcome':['我在这里，慢慢来。'],'focus_start':['这一会儿，安静地陪着你。']},'actions':{'greeting':['嗨，今天也一起加油呀。']}}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--screenshots',type=Path);parser.add_argument('--page',default='home');args=parser.parse_args()
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtGui import QFont
    from .window import HubWindow,PAGES
    app=QApplication([]);app.setFont(QFont('Noto Sans CJK SC',10));window=HubWindow(lambda request:None,preview=True)
    window.setFont(QFont('Noto Sans CJK SC',10));window.resize(1120,790);window.apply_snapshot(demo_snapshot());window.show();window.select_page(args.page)
    window.toast('界面预览 · 示例数据 · 未连接真实桌宠，按钮不会执行操作')
    if args.screenshots:
        args.screenshots.mkdir(parents=True,exist_ok=True)
        for index,(key,_,_) in enumerate(PAGES,1):
            window.select_page(key);app.processEvents();window.grab().save(str(args.screenshots/f'{index:02d}-{key}.png'))
        window.hide();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents();return
    app.exec()

if __name__=='__main__':main()
