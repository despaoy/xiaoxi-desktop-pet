"""Separate Qt renderer process; Tk retains all functional plugins."""
from pathlib import Path
import traceback

BASE = Path(__file__).resolve().parent.parent


def run(connection, position, model_version=26, disable_sandbox=False,
        size=(330, 345), visible=True):
    import os
    import sys
    if disable_sandbox:
        # Chromium's renderer sandbox cannot initialize in some restricted or
        # remote sessions. Only opt in explicitly; pages are served locally.
        os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'
    sys.path.insert(0, str(BASE / '.runtime-live2d'))
    stage = 'imports'
    try:
        connection.send({'event': 'loading', 'stage': stage})
        import json
        import threading
        from functools import partial
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Slot, Signal, QFile, QIODevice
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QApplication
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebChannel import QWebChannel
        stage = 'application'
        connection.send({'event': 'loading', 'stage': stage})

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/qwebchannel.js':
                    script = QFile(':/qtwebchannel/qwebchannel.js')
                    if not script.open(QIODevice.OpenModeFlag.ReadOnly):
                        self.send_error(500)
                        return
                    body = bytes(script.readAll())
                    script.close()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/javascript')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

            def list_directory(self, path):
                self.send_error(403)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(
            ('127.0.0.1', 0),
            partial(Handler, directory=str(BASE / 'review/live2d')))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        stage = 'server'
        connection.send({'event': 'loading', 'stage': stage})
        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        stage = 'webview'
        connection.send({'event': 'loading', 'stage': stage})
        window = QWebEngineView()
        class Page(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line, source):
                connection.send({'event': 'console', 'level': int(getattr(level, 'value', level)),
                                 'message': message[:1000], 'source': source, 'line': line})
        window.setPage(Page(window))

        def page_loaded(ok):
            connection.send({'event': 'loaded', 'ok': bool(ok),
                             'url': window.url().toString()[:500]})

        def renderer_terminated(status, code):
            status_value = int(getattr(status, 'value', status))
            status_name = {0: '正常结束', 1: '异常终止', 2: '崩溃', 3: '被终止'}.get(
                status_value, f'状态 {status_value}')
            connection.send({'event': 'error', 'stage': 'chromium',
                             'message': f'Chromium 渲染进程{status_name}（status={status_value}, exit={code}）'})

        window.loadFinished.connect(page_loaded)
        window.page().renderProcessTerminated.connect(renderer_terminated)
        window.setWindowTitle('银白龙娘 · Live2D 桌宠')
        window.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                              Qt.WindowType.WindowStaysOnTopHint |
                              Qt.WindowType.Tool)
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        window.setStyleSheet('background: transparent')
        window.page().setBackgroundColor(QColor('transparent'))
        window.resize(int(size[0]), int(size[1]))
        window.move(*position)
        window.setVisible(bool(visible))
        window.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        class Bridge(QObject):
            stateChanged = Signal(str)

            @Slot(str)
            def event(self, name):
                if name in ('ready', 'click', 'menu', 'hover', 'leave'):
                    connection.send({'event': name, 'x': window.x(), 'y': window.y(),
                                     'modelVersion': int(model_version)})

            @Slot(str)
            def error(self, message):
                connection.send({'event': 'error', 'stage': '页面脚本',
                                 'message': str(message)[:2000]})

            @Slot(float, int, float)
            def sample(self, breath, frames, faceY):
                connection.send({'event': 'sample', 'breath': breath,
                                 'frames': frames, 'faceY': faceY})

            @Slot(float, float)
            def mouthSample(self, value, height):
                connection.send({'event': 'mouth', 'value': value, 'height': height})

            @Slot(float, int, float, float)
            def motionSample(self, elapsed, frames, left_width, right_width):
                connection.send({'event': 'motion', 'elapsed': elapsed, 'frames': frames,
                                 'leftWidth': left_width, 'rightWidth': right_width})

            @Slot(str, float, float, float)
            def interactionSample(self, action, eye_height, wing_width, mouth_height):
                connection.send({'event': 'interaction', 'action': action,
                                 'eyeHeight': eye_height, 'wingWidth': wing_width,
                                 'mouthHeight': mouth_height})

            @Slot(str)
            def actionStarted(self, action):
                connection.send({'event':'action_started', 'action':action})

            @Slot()
            def beginDrag(self):
                self.origin = window.pos()

            @Slot(int, int)
            def drag(self, dx, dy):
                if hasattr(self, 'origin'):
                    area = window.screen().availableGeometry()
                    x = max(area.left(), min(self.origin.x() + dx, area.right() - window.width() + 1))
                    y = max(area.top(), min(self.origin.y() + dy, area.bottom() - window.height() + 1))
                    window.move(x, y)

            @Slot()
            def endDrag(self):
                connection.send({'event': 'moved', 'x': window.x(), 'y': window.y()})

        bridge = Bridge()
        channel = QWebChannel(window.page())
        channel.registerObject('pet', bridge)
        window.page().setWebChannel(channel)

        def poll():
            try:
                while connection.poll():
                    data = connection.recv()
                    if data.get('command') == 'close':
                        app.quit()
                        return
                    if data.get('command') == 'resize':
                        target = data.get('size') or (330, 345)
                        origin = data.get('position') or position
                        window.resize(int(target[0]), int(target[1]))
                        window.move(int(origin[0]), int(origin[1]))
                    if data.get('command') == 'state':
                        if 'visible' in data:
                            window.setVisible(bool(data['visible']))
                        bridge.stateChanged.emit(json.dumps(data))
            except (EOFError, OSError):
                app.quit()
        timer = QTimer()
        timer.timeout.connect(poll)
        timer.start(30)
        stage = 'page'
        window.load(QUrl(f'http://127.0.0.1:{server.server_port}/pet.html?v={int(model_version)}'))
        if visible:
            window.show()
        stage = 'waiting-ready'
        connection.send({'event': 'loading', 'stage': stage})
        app.exec()
        server.shutdown()
    except Exception as exc:
        try:
            connection.send({'event': 'error', 'stage': stage, 'message': str(exc),
                             'traceback': traceback.format_exc()})
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class Live2DHost:
    def __init__(self, position, model_version=26, disable_sandbox=False,
                 size=(330, 345), visible=True):
        import multiprocessing
        import time
        self.started = time.monotonic()
        self.disable_sandbox = bool(disable_sandbox)
        self.visible = bool(visible)
        self.size = tuple(int(value) for value in size)
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(
            target=run, args=(child, position, model_version, self.disable_sandbox,
                              self.size, self.visible), daemon=True)
        self.process.start()
        child.close()
        self.ready = False

    def events(self):
        result = []
        try:
            while self.connection.poll():
                result.append(self.connection.recv())
        except (EOFError, OSError):
            pass
        return result

    def state(self, **values):
        if self.process.is_alive():
            try:
                self.connection.send({'command': 'state', **values})
            except (EOFError, OSError):
                pass

    def resize(self, size, position):
        self.size = tuple(int(value) for value in size)
        if self.process.is_alive():
            try:
                self.connection.send({'command': 'resize', 'size': self.size,
                                      'position': tuple(int(value) for value in position)})
            except (EOFError, OSError):
                pass

    def close(self):
        if self.process.is_alive():
            try:
                self.connection.send({'command': 'close'})
            except (EOFError, OSError):
                pass
            self.process.join(3)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(1)
        self.connection.close()
