# 插件 API v1

每个插件是 `plugins/<id>/` 文件夹，包含 `plugin.json` 和 `plugin.py`。
核心应用提供窗口、通知、存储、全局快捷键和插件生命周期。功能插件可以独立修改。

```json
{
  "id": "example",
  "name": "示例功能",
  "version": "1.0.0",
  "api_version": 1,
  "entry": "plugin.py",
  "description": "功能说明",
  "permissions": ["本地设置"]
}
```

```python
from tkinter import ttk

class Plugin:
    def __init__(self, ctx):
        self.ctx = ctx
        ctx.add_action('示例菜单', lambda: ctx.notify('你好', '插件已运行'))

    def build(self, notebook):
        frame = ttk.Frame(notebook, padding=20)
        notebook.add(frame, text='示例')
        ttk.Label(frame, text='我的新功能').pack()

    def command(self, text):
        if text == '测试插件':
            self.ctx.set('count', self.ctx.get('count', 0) + 1)
            return '已完成测试'
        return None

    def tick(self, now):
        pass

    def shutdown(self):
        pass
```

## 稳定接口

- `ctx.get(key, default)` / `ctx.set(key, value)`：按插件 ID 隔离的 JSON 设置，SQLite 持久化。
- `ctx.add_action(label, callback)`：加入桌宠右键菜单。
- `ctx.add_action(label, callback, action_id='插件ID.操作ID', category='productivity', enabled=lambda: True)`：注册共享操作。label 可以是返回当前名称的函数；按钮、右键、收藏和常用快捷键共享同一操作。category 为 companion / productivity / shortcuts / usage / settings；省略时使用内置插件分类，其他插件归入设置。稳定 ID 用于保存收藏，不能随版本随意改变。旧版两参数调用仍可使用。
- `ctx.emit(event)`：触发角色事件，例如 click、success、reminder；动作与语言插件停用时不产生效果。
- `ctx.notify(title, body, actions=None)`：气泡和持久通知记录；actions 是 `(按钮名, 无参数回调)` 列表。
- `build(notebook)`：创建功能页。仅在面板首次创建时调用。
- `refresh()`：面板打开时刷新。
- `tick(now)`：每秒回调，now 为本机 datetime。请保持快速，不做阻塞网络请求。
- `command(text)`：返回字符串表示已处理；返回 None 让下一个插件处理。
- `shutdown()`：退出时收尾。

`ctx.app` 属于内部接口，内置插件用它访问统计和窗口；外部插件应优先使用稳定接口。
插件按目录名排序加载，命令由第一个匹配者处理。API 版本不匹配时不加载。
加载错误不会阻止其他插件启动；tick 异常会停止该插件后续回调，错误写入日志。
启用/停用和新代码在重启时生效，暂不支持模块热卸载。

## AI 插件接入建议

用工作线程做网络调用，通过主线程的 `root.after` 投递界面更新；不要在 tick 或 command 中等待网络。
将模型输出约束为有限动作（新增提醒、添加入口、更新设置），验证参数后调用功能层。
不要把模型返回的字符串直接当系统命令执行。密钥使用系统凭据存储，不放入插件清单或日志。
未来要兼容多个 agent，可新增独立适配插件，不改变基础计时和提醒服务。
