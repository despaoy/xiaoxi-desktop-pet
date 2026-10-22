# 资源文件

核心代码仓库只包含小体积 UI 资源和前端脚本。以下资源体积较大或属于第三方/美术源，按需下载。

## 运行必需：Live2D 最小运行时

下载：

**https://github.com/despaoy/xiaoxi-desktop-pet/releases/download/resources-v26/live2d-runtime-v26.zip**

解压后，把其中的 `vendor/` 与 `silver-v26-diagnostic/` 放到：

```text
review/live2d/vendor/
review/live2d/silver-v26-diagnostic/
```

目录应包含：

```text
review/live2d/
  pet.html
  pet.js
  idle-motion.js
  interaction-motion.js
  vendor/
    pixi.min.js
    live2dcubismcore.min.js
    cubism4.min.js
  silver-v26-diagnostic/
    silver-dragon-v26.model3.json
    ...
```

`qwebchannel.js` 由 Qt 的 `:/qtwebchannel/qwebchannel.js` 资源动态提供，不需要下载。

## 打包后的桌面应用

当前本地构建产物在：

```text
dist/XiaoXi/XiaoXi.exe
```

体积约 484 MB（压缩后的 `XiaoXi-win64.zip` 约 185 MB）。本次尝试上传到 GitHub Release 时连接中断，因此没有在仓库里放伪造的下载链接。需要发布时：

```powershell
tar -a -c -f XiaoXi-win64.zip -C dist --exclude "XiaoXi/data" XiaoXi
```

然后把它上传到你自己的 GitHub Release、网盘或 CDN，并把真实链接补到这里；不要打包 `data/`，里面是个人使用记录。

## 完整美术源

`assets/characters/silver-dragon/` 约 **859 MB**，包含：

- `live2d/authoring/`：分层/PSD 制作源
- `live2d/prepared-*`、`runtime-v*`：模型准备中间版本
- `design/`、`animations/`：设计稿与旧图片形象素材

这部分是美术源，不是运行必需资源；当前未上传到 GitHub。需要二次编辑模型时再从作者处获取（或自行上传到 Releases/LFS/网盘后补链接）。

## 图片形象模式（可选）

旧的 Tk 图片形象模式还需要：

```text
.runtime/                  # opencv / Pillow / numpy
assets/characters/         # 旧帧素材
requirements-motion.txt
```

如果只使用 Live2D 桌面应用，可以忽略这一节。

## 资源校验

- Live2D V26 模型目录：4 个文件，约 2.1 MB。
- `vendor/`：6 个文件，约 0.7 MB。
- 运行时资源压缩包约 2.8 MB。
