import importlib.util
import json
import logging
from pathlib import Path

API_VERSION = 1


class PluginContext:
    def __init__(self, app, plugin_id):
        self.app = app
        self.plugin_id = plugin_id

    def get(self, key, default=None):
        return self.app.store.get(f'plugin.{self.plugin_id}.{key}', default)

    def set(self, key, value):
        self.app.store.set(f'plugin.{self.plugin_id}.{key}', value)

    def notify(self, title, body, actions=None):
        self.app.notify(title, body, actions)

    def add_action(self, label, callback, *, action_id=None, category=None, enabled=lambda: True):
        self.app.actions.append((label, callback))
        registry = getattr(self.app, 'registry', None)
        if registry is not None:
            from desktop_pet.actions import Action, CATEGORIES
            return registry.add(Action(action_id or f'{self.plugin_id}.{len(self.app.actions)}',
                category or (self.plugin_id if self.plugin_id in CATEGORIES else 'settings'),
                label, callback, self.plugin_id, enabled))

    def emit(self, event):
        """Optional character event; harmless if companion support is disabled."""
        handler = getattr(self.app,'react',None)
        if handler:
            handler(event)


class PluginManager:
    def __init__(self, app, directory):
        self.app = app
        self.directory = Path(directory)
        self.records = []
        self.plugins = {}

    def load(self):
        disabled = self.app.store.get('disabled_plugins', [])
        seen = set()
        for manifest in sorted(self.directory.glob('*/plugin.json')):
            record = {'id': manifest.parent.name, 'name': manifest.parent.name, 'status': '未加载'}
            try:
                info = json.loads(manifest.read_text(encoding='utf-8'))
                record.update(info)
                plugin_id = info['id']
                if plugin_id in seen:
                    raise ValueError('插件 ID 重复')
                seen.add(plugin_id)
                if info.get('api_version') != API_VERSION:
                    raise ValueError('插件 API 版本不兼容')
                if plugin_id in disabled:
                    record['status'] = '已停用'
                else:
                    source = (manifest.parent / info.get('entry', 'plugin.py')).resolve()
                    if not source.is_relative_to(manifest.parent.resolve()):
                        raise ValueError('插件入口必须位于插件目录')
                    spec = importlib.util.spec_from_file_location(f'pet_plugin_{plugin_id}', source)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    plugin = module.Plugin(PluginContext(self.app, plugin_id))
                    self.plugins[plugin_id] = plugin
                    record['status'] = '运行中'
            except Exception as exc:
                logging.exception('Plugin load failed')
                record['status'] = '错误：' + str(exc)
            self.records.append(record)

    def call(self, method, *args):
        for plugin_id, plugin in list(self.plugins.items()):
            handler = getattr(plugin, method, None)
            if handler:
                try:
                    handler(*args)
                except Exception as exc:
                    logging.exception('Plugin %s failed in %s', plugin_id, method)
                    if method == 'tick':
                        self.plugins.pop(plugin_id, None)
                    for record in self.records:
                        if record['id'] == plugin_id:
                            record['status'] = '错误：' + str(exc)

    def command(self, text):
        for plugin in self.plugins.values():
            handler = getattr(plugin, 'command', None)
            if handler:
                try:
                    result = handler(text)
                    if result:
                        return result
                except Exception as exc:
                    logging.exception('Command failed')
                    return '未完成：' + str(exc)
        return '暂时不认识这条指令。可以试试：每60分钟提醒我休息 / 10分钟后提醒我喝水 / 开始25分钟专注 / 添加待办 买牛奶 / 添加快捷入口 工作文件夹 | C:\\Work'
