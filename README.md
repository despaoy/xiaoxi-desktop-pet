# 小汐 · Windows 桌面宠物

小汐是一个 Windows 桌面宠物应用：Tkinter 负责控制面板、插件和小屋，PySide6 / QtWebEngine 在独立进程中渲染 Live2D 角色，PyInstaller 打包为无控制台的桌面程序。

> 这是**核心代码仓库**。Live2D 模型、第三方渲染 SDK、完整美术源和打包后的 exe 体积较大，未直接放进 git；下载方式见 [RESOURCES.md](RESOURCES.md)。

- 仓库：https://github.com/despaoy/xiaoxi-desktop-pet
- Live2D 最小运行时（V26）：https://github.com/despaoy/xiaoxi-desktop-pet/releases/download/resources-v26/live2d-runtime-v26.zip
- 打包后的桌面版和 859 MB 完整美术源未上传；原因和自行发布命令见 [RESOURCES.md](RESOURCES.md)。

## 功能

- Live2D V26 角色：呼吸、眨眼、视线、翅膀、后发、嘴型、打招呼、拖拽与贴边。
- 功能小屋：左侧「今天」+ 五类入口；U2 分类统计卡；完整统计页 U1（环形分类 + 圆角应用排行）。
- 应用时间：前台应用识别、产品名归一、多进程/别名合并、分类、每日限时提醒、7/30 天数据。
- 专注与提醒：番茄钟、一次/重复提醒、待办、每日小结。
- 快捷操作：软件、文件、文件夹、HTTP(S) 网址、组合场景、音量/静音/锁屏。
- 右键图标宫格菜单与快捷面板。
- 开机自启（后台运行）、原生托盘图标、无角色后台模式。
- 插件体系：本地插件发现、启停、版本校验；内置 companion / productivity / shortcuts / usage。

## 快速开始（源码运行）

要求：Windows 10/11，Python 3.12（含 Tkinter）。

```powershell
git clone https://github.com/despaoy/xiaoxi-desktop-pet.git
cd xiaoxi-desktop-pet

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-live2d.txt
```

从 [RESOURCES.md](RESOURCES.md) 下载 `live2d-runtime-v26.zip`，解压后放到：

```text
review/live2d/vendor/
review/live2d/silver-v26-diagnostic/
```

启动：

```powershell
python run.py --live2d
```

如果 Chromium 沙箱在当前远程/受限会话中无法初始化，使用兼容模式：

```powershell
python run.py --live2d --live2d-no-sandbox
```

后台启动（只显示托盘，不显示角色）：

```powershell
python run.py --live2d --live2d-no-sandbox --background
```

托盘菜单：显示/隐藏角色、打开功能小屋、开机自启、退出。Windows 11 可能把新图标放进任务栏的 `^` 溢出区，可拖到任务栏固定。

## 开机自启

设置里的「开机自启（后台运行，显示托盘）」会把当前可执行文件写入：

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

不需要管理员权限；取消勾选会删除该项。源码运行时注册的是 `pythonw.exe run.py --live2d --live2d-no-sandbox --background`，打包版注册的是 `XiaoXi.exe --background`。

## 打包

需要 PyInstaller（仓库不提交构建工具）：

```powershell
pip install pyinstaller
# 准备 review/live2d/runtime 资源和 .runtime-live2d（见 RESOURCES.md）
.\build-desktop.ps1
.\install-desktop.ps1   # 创建桌面快捷方式
```

`XiaoXi.spec` 会打包 Python、PySide6、QtWebEngine、最小 Live2D 运行时和插件。`dist/`、`.runtime*/`、`data/` 都已在 `.gitignore` 中排除。

## 应用识别

- 内置别名表 + Windows `ProductName` / `FileDescription` / `CompanyName`。
- `java.exe`、`ApplicationFrameHost.exe` 等宿主只在内存中临时用窗口标题匹配；标题不写数据库、不写日志。
- 安装器、系统 Shell 组件、本应用自身默认排除。
- 旧数据按别名在读取时归一，不做破坏性迁移；新数据保存稳定 app id。
- 分类：开发与工作、浏览与资讯、AI 与沟通、娱乐与游戏、系统与工具、其他/待识别。

## 数据与隐私

- 数据默认在项目的 `data/`；打包版在 `dist/XiaoXi/data/`。
- 只记录前台应用和时长；不采集网页内容、聊天内容、键盘文字。
- 仅对 `java` 等无法按 exe 区分的宿主临时读取窗口标题做匹配，标题不落盘。
- 空闲、锁屏、休眠时暂停统计；应用切换约 1 秒采样误差。
- 所有数据保存在本机 SQLite，不上传。

## 代码结构

```text
desktop_pet/
  app.py               Tk 主程序、窗口、启动流程
  live2d_host.py       PySide6/QtWebEngine 独立渲染进程
  navigation.py        分类入口、小屋/仪表盘、可见性
  hub.py               B 方案侧栏小屋 + U2 紧凑统计卡
  usage_dashboard.py   U1 完整统计页
  menu.py              右键图标宫格、圆角卡片
  apps.py              应用别名/元数据/标题识别/分类
  storage.py           SQLite 设置与使用记录
  tray.py              pystray 原生托盘
  platform_win.py      Win32 前台应用、自启、热键
plugins/               内置插件
review/live2d/         前端 pet.html / pet.js 与最小运行时占位
tests/                 单元测试
docs/                  插件 API
```

## 测试

```powershell
python -m unittest discover -s tests -v
python run.py --smoke --data-dir data-smoke
```

`smoke` 会短暂创建真实 Tk 窗口，验证插件、面板和通知，不会执行锁屏或打开快捷目标。

当前核心测试 33 项通过。

## 资源与许可证

- 代码版权归作者所有；本仓库**暂未附加开源许可证**。如需 MIT / Apache-2.0，请先与作者确认。
- 第三方组件（PySide6/Qt、Live2D Cubism SDK、PIXI、pystray、Pillow 等）遵循各自许可证；详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
- Live2D 模型、SDK 与美术源未直接放入本仓库；请按 [RESOURCES.md](RESOURCES.md) 获取。

## 已知限制

- 旧历史里的 `java.exe`、`pythonw.exe` 无法追溯窗口标题/PID，会保留为 Java 应用 / Python；新数据会正确归类。
- 未签名的 exe 在部分机器会触发 SmartScreen；需要自行签名。
- Tk 界面目前是 DPI-unaware，150% 缩放下为位图放大，文字会略软。
- 浏览器只按应用整体统计，不按标签页/网址拆分。
