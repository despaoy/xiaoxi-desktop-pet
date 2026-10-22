"""Narrow Windows integration. Never records window titles or keystrokes."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

IS_WINDOWS = os.name == 'nt'
STARTUP_NAME = 'XiaoXi'
STARTUP_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
if IS_WINDOWS:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.SwitchDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    kernel32.GetTickCount.restype = wintypes.DWORD


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    path: str
    name: str
    title: str


def foreground_app_info():
    """Return the foreground process, without persisting the window title."""
    if not IS_WINDOWS:
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        path = buffer.value
        name = Path(path).name
        if name.lower() in {'lockapp.exe', 'logonui.exe'}:
            return None
        length = min(1024, max(0, user32.GetWindowTextLengthW(hwnd)))
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        return ProcessInfo(pid.value, path, name, title_buffer.value)
    finally:
        kernel32.CloseHandle(handle)


def foreground_app():
    info = foreground_app_info()
    return info.name if info else None


def startup_command(background=True):
    """Command stored in HKCU Run. Packaged builds need no Python."""
    if getattr(sys, 'frozen', False):
        parts = [str(Path(sys.executable).resolve())]
    else:
        python = Path(sys.executable).resolve()
        if python.name.lower() == 'python.exe':
            windowed = python.with_name('pythonw.exe')
            if windowed.exists():
                python = windowed
        parts = [str(python), str(Path(__file__).resolve().parent.parent / 'run.py'),
                 '--live2d', '--live2d-no-sandbox']
    if background:
        parts.append('--background')
    return subprocess.list2cmdline(parts)


def startup_enabled():
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY) as key:
            winreg.QueryValueEx(key, STARTUP_NAME)
        return True
    except OSError:
        return False


def set_startup(enabled, background=True):
    if not IS_WINDOWS:
        return False
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_SZ,
                              startup_command(background))
        else:
            try:
                winreg.DeleteValue(key, STARTUP_NAME)
            except FileNotFoundError:
                pass
    return bool(enabled)


def idle_seconds():
    if not IS_WINDOWS:
        return 0
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 999999
    return ((kernel32.GetTickCount() - info.dwTime) & 0xffffffff) / 1000


def unlocked():
    if not IS_WINDOWS:
        return True
    handle = user32.OpenInputDesktop(0, False, 0x0100)
    if not handle:
        return False
    try:
        return bool(user32.SwitchDesktop(handle))
    finally:
        user32.CloseDesktop(handle)


def system_action(action):
    if not IS_WINDOWS:
        raise RuntimeError('此操作需要 Windows')
    if action == 'lock':
        if not user32.LockWorkStation():
            raise OSError('锁屏失败')
        return
    key = {'volume_up': 0xAF, 'volume_down': 0xAE, 'mute': 0xAD}[action]
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 2, 0)


def open_target(target):
    target = str(target).strip()
    if target.lower().startswith(('https://', 'http://')):
        if not webbrowser.open(target):
            raise RuntimeError('无法打开浏览器')
        return
    path = Path(os.path.expandvars(os.path.expanduser(target)))
    if not path.exists():
        raise FileNotFoundError('路径不存在：' + str(path))
    if IS_WINDOWS:
        os.startfile(str(path))
    else:
        subprocess.Popen(['xdg-open', str(path)])


class Hotkey:
    """Registered hotkey only; no keyboard hook or input capture."""
    ID = 0xB041

    def __init__(self, favorite_hotkeys=False):
        import queue
        self.favorite_queue = queue.SimpleQueue()
        self.favorite_hotkeys = favorite_hotkeys
        self.favorite_registered = []
        self.registered = False
        self.pending = threading.Event()
        self.stop = threading.Event()
        self.ready = threading.Event()
        if IS_WINDOWS:
            self.thread = threading.Thread(target=self._listen, daemon=True)
            self.thread.start()
            self.ready.wait(timeout=2)

    def _listen(self):
        # Own thread queue prevents Tk's message loop consuming WM_HOTKEY.
        self.registered = bool(user32.RegisterHotKey(None, self.ID, 0x4000 | 0x2 | 0x4, 0x50))
        self.ready.set()
        if not self.registered:
            return
        if self.favorite_hotkeys:
            for slot in range(4):
                if user32.RegisterHotKey(None, self.ID+slot+1, 0x4000 | 0x2 | 0x4, 0x31+slot):
                    self.favorite_registered.append(slot)
        msg = wintypes.MSG()
        try:
            while not self.stop.wait(0.05):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                    if msg.wParam == self.ID:
                        self.pending.set()
                    elif self.ID < msg.wParam <= self.ID+4:
                        self.favorite_queue.put(msg.wParam-self.ID-1)
        finally:
            user32.UnregisterHotKey(None, self.ID)
            for slot in self.favorite_registered:
                user32.UnregisterHotKey(None, self.ID+slot+1)

    def poll_favorite(self):
        import queue
        try:
            return self.favorite_queue.get_nowait()
        except queue.Empty:
            return None

    def poll(self):
        if not self.registered:
            return False
        found = self.pending.is_set()
        self.pending.clear()
        return found

    def close(self):
        self.stop.set()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1)


def acquire_instance():
    if not IS_WINDOWS:
        return None
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, 'Local\\MioDesktopCompanion-v1')
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        raise RuntimeError('桌宠已经在运行，请单击角色或按 Ctrl+Alt+P 打开面板。')
    return handle
