# 小屋透明窗口原型（第一批）

这是独立、主动启动的交互预览，不是生产小屋替换。主程序、托盘、旧插件和数据文件均不受影响。

## 启动

使用已装有项目 `requirements-live2d.txt` 中 PySide6 的 Python 环境，从仓库根目录运行：

```sh
python -m prototypes.qt_hub
```

若项目使用 `.runtime-live2d` 依赖目录，请使用该目录对应的现有 Python 启动环境；不要假定系统 Python 已安装依赖。

- 我的小屋、陪我专注两个页面可切换，内容可滚动。
- 首页以项目现有 app-icon.png 小汐头像（256×256 原图平滑缩至 80×80）、问候气泡和互动为主，淡紫与奶桃色小角落、日常小纸条形成亲切的小屋感；专注入口退居次要位置。
- 摸摸头、打招呼、歇一会只切换演示气泡文案，不驱动真实人物动作。头像保留现有角色和完整淡紫圆角框，不裁掉龙角，没有另造角色。
- 标题栏空白区域可拖动；关闭按钮或 Escape 退出。
- 所有按钮带图标和文字，支持 Tab 键焦点。
- 专注按钮仅切换演示状态。25:00 是静态展示，没有后台计时器，没有写库、真实提醒或任务联动。
- 不联网、不获取窗口活动、不修改真实桌宠状态。

## 消除硬裁剪边缘的方式

窗口使用 `WA_TranslucentBackground` 和 QPainter 抗锯齿圆角，保留逐像素透明度。没有 Tk 透明色键、二值窗口 mask 或全局透明度，因此轮廓可在与桌面合成时保留平滑过渡。软阴影同样通过 alpha 绘制。Qt 使用逻辑像素，实际 Windows DPI 与多屏结果仍需真机验证。

## 测试与截图

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p test_qt_hub_prototype.py -v
QT_QPA_PLATFORM=offscreen python -m prototypes.qt_hub --screenshot hub-today.png
QT_QPA_PLATFORM=offscreen python -m prototypes.qt_hub --page focus --screenshot hub-focus.png
```

上面的环境变量写法适用于 Linux/macOS shell。Windows PowerShell 使用 `$env:QT_QPA_PLATFORM = 'offscreen'`；交互查看时不要设置 offscreen。

截图是真实 Qt 离屏渲染，包含透明边缘与明确标注的演示数据，不是 Windows 桌面运行截图。无 PySide6 时，可选原型测试会明确跳过，而非假装通过。

人工验收仍需：Windows 100%/125%/150%/200% 缩放、深浅桌面背景、跨屏拖动、负坐标屏幕、小工作区、中文字体回退、键盘导航、连续开关。原型审核通过后才考虑服务接入和全面界面迁移。

已为带头像窗口的截图进程增加退出测试：窗口及其图片在 QApplication 销毁前释放，避免信号闭包延迟清理导致退出异常。

头像黑边修正：原型改用仓库已有的干净 app-icon.png；仅切换代码引用并平滑缩小，未修改任何位图。旧 menu-avatar.png 和生产界面保持不变。两处头像均验证透明角及外缘不含不透明黑边；眼睛等内部深色细节保留。
