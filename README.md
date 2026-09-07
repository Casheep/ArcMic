# ArcMic

ArcMic 是一个面向 Windows 游戏语音的本地麦克风增强工具。最终发布物只有一个 `ArcMic.exe`：首次运行接受一次 Windows 管理员授权后，程序会自动识别当前默认麦克风、安装内置音频处理组件并开始工作，不要求用户单独安装 Equalizer APO 或手动配置 VST。

## 下载

普通用户只需要从 [GitHub Releases](../../releases/latest) 下载 `ArcMic.exe`，双击即可使用。Release 同时提供 SHA-256 校验文件，以及随 EXE 分发的 GPL 组件的对应源码包；不需要下载仓库源码、Python 或其他安装程序。

## 功能

- `0～30 dB` 麦克风数字增益，默认 `+6 dB`
- 五档净噪按强度排列：关闭、普通、中等、强力、最强（默认）
- 强力和最强模式使用新版 RNNoise v1.21；最强模式会先处理持续底噪，再交给 AI
- 中等模式完全不用 AI，优先保持原本声音
- 系统级麦克风处理：游戏继续使用原来的麦克风设备
- 15 秒耳机监听与实时输入电平
- 监听默认跟随 Windows 当前默认输出，也可在界面中固定选择耳机或扬声器
- 关闭或最小化窗口后驻留系统托盘，直接显示增强开关和当前增益
- 本地运行，无账号、无遥测、无录音文件、无网络请求
- 自动保存设置，并提供“恢复系统设置”入口

![ArcMic interface](docs/ui-preview.png)

## 使用

1. 双击 `ArcMic.exe`。
2. 首次运行时接受 Windows UAC 管理员授权。它用于把处理器绑定到麦克风；以后普通调节不需要管理员权限。当前公开版没有商业代码签名证书，因此 Windows 可能先显示“未知发布者”或 SmartScreen 提示；请只从本仓库 Release 下载，并用 `SHA256SUMS.txt` 校验后运行。
3. 游戏中继续选择原来的麦克风，或保持“系统默认输入设备”。
4. 先使用 `+6 dB`，声音仍小时逐步提高。`+20～30 dB` 属于极高区域，可能放大底噪或产生削波。
5. 监听时请佩戴耳机，避免扬声器和麦克风形成啸叫。
6. “监听输出”保持“跟随 Windows 默认输出”时，ArcMic 会在每次开始监听前重新读取 Windows 当前选择。

## 游戏兼容性

ArcMic 使用 Windows Audio Processing Object（APO）处理共享模式的录音流，不注入游戏进程，因此对大多数使用 WASAPI/DirectSound 默认共享录音路径的游戏有效，也不需要创建额外的虚拟麦克风。

少数游戏或专业软件会主动请求 WASAPI RAW、WASAPI Exclusive 或 ASIO，从而绕过所有 Windows 系统音效；这类程序也会绕过 ArcMic。此限制来自 Windows 音频路径，不是增益或净噪算法本身。游戏内若有“原始输入/Raw Input/绕过系统处理”，应保持关闭。

## 性能设计

实时链路运行在原生 Equalizer APO 中，只有选择“强力”或“最强”时才加载 RNNoise VST2。托盘进程只负责界面和开关状态，不搬运游戏中的实时音频；窗口隐藏后停止电平读取，只有用户点击监听时才创建输出监听流。每次开始监听都会重新读取 Windows 当前默认输出，并在状态栏显示声音实际送往的设备。

## 构建

需要 Windows 10/11 x64 与 Python 3.12：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建脚本会创建隔离的 `.venv`、运行测试并生成：

```text
artifacts\ArcMic.exe
```

构建依赖锁定在 [requirements-build.txt](requirements-build.txt)。仓库中的 `vendor` 目录包含单文件发布所需的固定版本运行库及其许可证。若替换任何二进制，应同步更新 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 中的版本和 SHA-256。

## 测试

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

不修改系统的界面预览模式：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe .\run_arcmic.py --demo
```

## 隐私与许可

隐私边界见 [PRIVACY.md](PRIVACY.md)。项目以 GPL-3.0-or-later 发布；使用了哪些开源组件、为什么使用、许可证和对应源码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。发布与源码对应关系见 [SOURCE_CODE.md](SOURCE_CODE.md)。
