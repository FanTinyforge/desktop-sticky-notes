# 桌面便利贴 · Desktop Sticky Notes

<img src="app_icon.png" width="96" align="right" alt="icon">

一个 Windows 桌面便利贴小工具：奶油色纸片、胶带标题条、柔和投影，默认贴在壁纸上，也可以把某一张钉到最前面。

A lightweight Windows sticky-note app built with PySide6. Cream-colored paper, a washi-tape title bar, and a soft shadow. Notes live on the desktop by default; pin any note above other windows when you need it.

## 下载 / Download

去 [Releases](../../releases/latest) 下载 `desktop-sticky-notes-1.1.3-win64.zip`，解压后双击 `桌面便利贴.exe`，免安装。

- 仅支持 **Windows 10 1809+ / Windows 11，x64**
- 未做代码签名，首次运行 Windows SmartScreen 会提示：点「更多信息 → 仍要运行」
- 压缩包里只有 exe、使用说明、卸载脚本，**不含任何便签数据**

## 功能

- **贴桌面 / 置顶双层级**：默认压在所有窗口下面、贴着壁纸；点标题条的「钉」浮到最前，再点回桌面层
- **折叠**：只留一条胶带标题条，再点展开
- **单张透明度**：30%–100%，只作用于选中的那一张
- **自由缩放**：拖右下角斜线改大小；小 / 中 / 大三档预设
- **配色与字体**：纸色、胶带色可取色器任选；楷体 / 宋体 / 黑体
- **标题可单独排版**：标题字号 10–28、标题颜色独立设置，胶带标题条高度随字号自动缩放
- **正文局部格式**：选中文字后改字号 / 字色只作用于选区，同一张便签可以混排大小和颜色；没有选区时才改整张便签默认样式
- **默认开机自启**：打包版首次运行自动写入当前用户启动项，托盘可随时关闭，不需要管理员权限
- **音效可换**：拖动是轻纸面摩擦 + 短「嗒」，落纸是低频闷响；支持换成自己的 wav，可随时恢复默认
- **自动存档**：0.7 秒防抖，删除 / 拖动结束立即写盘；写 `.tmp` → fsync → 备份 → 原子替换
- **坏档不静默清空**：主文件读不出来回退 `.bak`；两份都坏则保留 `.corrupt` 并在托盘提示
- **多屏防丢**：监听屏幕增删、分辨率变化，跑到屏幕外的便签会被拉回可视区
- **无网络、无遥测、无账号**：所有数据只在本机

## 怎么用

| 操作 | 效果 |
| --- | --- |
| 拖动标题条 | 移动便签，起手 / 松手各有音效，拖动中投影变大 |
| 双击标题文字 | 修改标题，默认「待办事项」；回车或点别处保存，Esc 取消，也可以右键修改 |
| 选中正文文字后改字号 / 字色 | 只改选中的字，不污染整张便签默认样式 |
| 控制条「标题字号 / 标题色」 | 只改选中便签的标题文字，胶带条高度自动跟着字号缩放 |
| 鼠标移到便签上 | 标题条右侧浮出 `钉` / `▲` / `✕` |
| 点 `钉` | 置顶；再点回桌面层 |
| 点 `▲` | 折叠成只剩标题条，箭头变 `▼` |
| 双击正文 | 编辑，直接打字 |
| 拖右下角斜线 | 改大小 |
| 右键便签 | 层级、透明度、折叠、删除 |
| 点 `✕` | 便签底部弹确认条，再点「删除」 |
| 单击便签 | 选中，控制条上的颜色 / 字体 / 尺寸 / 透明度作用于它 |

启动后桌面底部中间有一条控制条，托盘区有便签图标。托盘右键可新建、全部置顶 / 全部贴桌面、音效、开机自启、隐藏、退出。

## 音效自定义

默认音效由程序实时合成，不依赖外部文件。

换自己的声音：托盘右键 →「音效」→「选择拖动音效 / 选择落纸音效」，或控制条「音效」按钮右键。只接受 **16 位 PCM 的 `.wav`**，建议 0.1–0.6 秒。文件会复制到数据目录的 `snap_custom.wav` / `drop_custom.wav`，立即生效并持久保存；「恢复默认音效」会删掉自定义文件。

程序内没有独立音量滑杆，音量跟随系统。

## 数据与隐私

数据目录：`%APPDATA%\StickyNotesTool\`

| 文件 | 用途 |
| --- | --- |
| `notes.json` | 当前便签 |
| `notes.json.bak` | 上一版备份 |
| `notes.json.corrupt` | 仅在主档损坏时出现，原文件留证 |
| `app.log` | 未捕获异常、层级设置失败、保存失败 |
| `snap_custom.wav` / `drop_custom.wav` | 仅在你自定义音效后出现 |

便签内容是**明文 JSON**，不上传、不加密。要彻底清除：退出程序后删除整个 `StickyNotesTool` 文件夹，或运行包内的 `卸载.bat`。

## 从源码运行

需要 Python 3.10+（开发环境为 3.13）。

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

源码模式不会写开机启动项，避免调试时污染系统；设置环境变量 `STICKY_NO_AUTOSTART=1` 也可以强制禁用。

## 开机自启

打包版默认开启：首次运行写入 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\StickyNotesTool`，指向当前 exe 路径，不需要管理员权限。托盘右键可取消勾选「开机自启」；再勾上会重新写入当前路径。移动 exe 后下次启动会自动更新路径。

如果之前手动把快捷方式放进 `shell:startup`，请先删掉，避免和注册表启动项重复。

## 自己打包

```powershell
powershell -File build.ps1      # 生成 dist\桌面便利贴.exe
powershell -File package.ps1    # 生成 release\桌面便利贴-1.1.3-win64.zip
```

`build.ps1` 使用仓库内的 `.venv`，调用 PyInstaller 按 `桌面便利贴.spec` 打单文件；spec 里已排除 QtQml / QtQuick / QtSql / QtPdf / WebEngine / tkinter，关闭 UPX，并带 `version_info.txt` 版本资源。

## 项目结构

```
main.py       启动、托盘、控制条管理、单实例、异常日志
note.py       便签窗口：拖动、缩放、折叠、阴影、层级
panel.py      底部控制条
theme.py      配色、尺寸、阴影参数
store.py      存档：校验、原子写入、备份与损坏隔离
sound.py      合成默认音效、自定义 wav 校验
make_icon.py  生成 app_icon.png
```

## 已知限制

- 只支持 Windows x64；没有 macOS / Linux 版本
- 安装包未签名，SmartScreen 会提示；没有自动更新
- PyInstaller onefile 运行时会有一个引导进程 + 主进程，属正常现象；退出请走托盘，强杀会留下子进程
- 便签明文存储，不提供加密；换机请手动备份 `notes.json`
- 正文支持局部字号 / 颜色，但不支持图片、提醒、云同步，定位就是轻量桌面纸片

## License

[MIT](LICENSE)
