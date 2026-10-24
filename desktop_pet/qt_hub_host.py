"""Separate-process Qt hub. The existing Tk host remains the sole data owner."""
from collections import OrderedDict
import importlib.util
import json
import logging
import multiprocessing
from pathlib import Path
import queue
import sys
import threading
import time
import traceback

from desktop_pet.hub_backend import HubBackend

BASE = Path(__file__).resolve().parent.parent


def run(connection):
    """Spawn target: no Store, PluginManager or Tk is created in this process."""
    sys.path.insert(0, str(BASE / '.runtime-live2d'))
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from desktop_pet.qt_hub import HubWindow
        qt = QApplication([])
        qt.setQuitOnLastWindowClosed(False)
        closed = False

        def send(message):
            nonlocal closed
            if closed:
                return
            try:
                connection.send(message)
            except (EOFError, OSError, BrokenPipeError):
                closed = True
                qt.quit()

        window = HubWindow(send)

        def poll():
            nonlocal closed
            try:
                for _ in range(50):
                    if not connection.poll():
                        break
                    message = connection.recv()
                    kind = message.get('event')
                    if kind == 'snapshot':
                        window.apply_snapshot(message['snapshot'])
                    elif kind == 'result':
                        window.apply_result(message)
                    elif kind == 'show':
                        if message.get('page') and hasattr(window, 'select_page'):
                            window.select_page(message['page'])
                        window.show()
                        window.raise_()
                        window.activateWindow()
                    elif kind == 'hide':
                        window.hide()
                        window.focus_changed(None, None)
                    elif kind == 'shutdown':
                        closed = True
                        window.close()
                        qt.quit()
                        break
            except (EOFError, OSError, BrokenPipeError):
                closed = True
                qt.quit()
            except Exception:
                send({'event': 'error', 'error': traceback.format_exc()[-3000:]})
                qt.quit()

        timer = QTimer()
        timer.timeout.connect(poll)
        timer.start(40)
        send({'event': 'ready'})
        qt.exec()
        # Destroy all widget-owned pixmaps before the QApplication is torn down.
        timer.stop()
        window.deleteLater()
        qt.processEvents()
    except Exception:
        try:
            connection.send({'event': 'error', 'error': traceback.format_exc()[-3000:]})
        except Exception:
            pass
    finally:
        connection.close()


class QtHubHost:
    def __init__(self, app, on_failure):
        self.app, self.on_failure = app, on_failure
        self.backend = HubBackend(app)
        self.process = self.connection = None
        self.ready = False
        self.visible = False
        self.closed = False
        self.started_at = 0
        self.last_snapshot = 0
        self.pending_page = None
        self.replies = OrderedDict()
        self.outgoing = queue.Queue(maxsize=64)
        self.writer = None
        self.stop_writer = threading.Event()
        self.writer_error = None
        self.job = None

    @staticmethod
    def available():
        runtime = str(BASE / '.runtime-live2d')
        if runtime not in sys.path:
            sys.path.insert(0, runtime)
        try:
            return importlib.util.find_spec('PySide6') is not None
        except (ImportError, ValueError):
            return False

    def start(self):
        if self.process is not None:
            return True
        if not self.available():
            return False
        parent, child = multiprocessing.get_context('spawn').Pipe()
        self.connection = parent
        self.process = multiprocessing.get_context('spawn').Process(target=run, args=(child,), daemon=True, name='XiaoXiHub')
        try:
            self.process.start()
        except Exception:
            parent.close()
            child.close()
            self.process = self.connection = None
            logging.exception('Qt hub startup failed')
            return False
        child.close()
        self.started_at = time.monotonic()
        self.writer = threading.Thread(target=self._write_loop, name='hub-pipe-writer', daemon=True)
        self.writer.start()
        self.job = self.app.root.after(50, self.poll)
        return True

    def _write_loop(self):
        while not self.stop_writer.is_set():
            try:
                message = self.outgoing.get(timeout=.2)
            except queue.Empty:
                continue
            if message is None:
                return
            try:
                self.connection.send(message)
            except (OSError, EOFError, BrokenPipeError) as exc:
                self.writer_error = str(exc)
                return

    def send(self, message):
        if self.closed:
            return False
        try:
            self.outgoing.put_nowait(message)
            return True
        except queue.Full:
            # Snapshots are replaceable; command acknowledgements are not.
            if message.get('event') != 'snapshot':
                self.writer_error = '界面消息队列已满'
            return False

    def show(self, page=None):
        self.visible = True
        self.pending_page = page
        if self.ready:
            self.refresh(force=True)
            self.send({'event': 'show', 'page': page})

    def hide(self):
        self.visible = False
        self.app.qt_hub_editing = False
        self.send({'event': 'hide'})

    def refresh(self, force=False):
        if not self.ready or not self.visible:
            return
        now = time.monotonic()
        if not force and now - self.last_snapshot < 1.0:
            return
        try:
            snapshot = self.backend.snapshot()
            self.send({'event': 'snapshot', 'snapshot': snapshot})
            self.last_snapshot = now
        except Exception:
            logging.exception('Qt hub snapshot failed')
            self.send({'event': 'result', 'id': 'snapshot', 'ok': False, 'error': '数据读取失败，请打开兼容面板检查；当前显示内容可能已过期。'})

    def handle(self, message):
        if not isinstance(message, dict):
            raise ValueError('无效界面消息')
        if message.get('event') == 'ready':
            self.ready = True
            if self.visible:
                self.refresh(force=True)
                self.send({'event': 'show', 'page': self.pending_page})
            return
        if message.get('event') == 'error':
            raise RuntimeError(str(message.get('error', '未知界面错误')))
        request_id = message.get('id')
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError('请求标识无效')
        if len(json.dumps(message, ensure_ascii=False, allow_nan=False)) > 65536:
            raise ValueError('请求内容过长')
        if request_id in self.replies:
            self.send(self.replies[request_id])
            return
        response = {'event': 'result', 'id': request_id}
        try:
            result = self.backend.execute(message.get('action'), message.get('payload', {}))
            response.update(ok=True, result=result if isinstance(result, (str, int, float, bool, dict, list, type(None))) else None)
        except Exception as exc:
            logging.exception('Qt hub action failed: %s', message.get('action'))
            response.update(ok=False, error=str(exc))
        self.replies[request_id] = response
        while len(self.replies) > 256:
            self.replies.popitem(last=False)
        self.send(response)
        self.refresh(force=True)

    def poll(self):
        self.job = None
        if self.closed:
            return
        try:
            if self.writer_error:
                raise RuntimeError(self.writer_error)
            if self.process is None or not self.process.is_alive():
                raise RuntimeError('新版小屋进程已退出')
            if not self.ready and time.monotonic() - self.started_at > 12:
                raise RuntimeError('新版小屋启动超时')
            for _ in range(40):
                if not self.connection.poll():
                    break
                self.handle(self.connection.recv())
            self.refresh()
        except Exception as exc:
            logging.exception('Qt hub unavailable; using compatible UI')
            was_visible = self.visible
            self.close()
            self.on_failure(str(exc), was_visible)
            return
        self.job = self.app.root.after(80, self.poll)

    def close(self):
        if self.closed:
            return
        self.send({'event': 'shutdown'})
        self.closed = True
        self.app.qt_hub_editing = False
        if self.job is not None:
            try:
                self.app.root.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        if self.process:
            self.process.join(timeout=.35)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=.35)
        self.stop_writer.set()
        if self.connection:
            self.connection.close()
        if self.writer and self.writer is not threading.current_thread():
            self.writer.join(timeout=.2)
        self.ready = self.visible = False
