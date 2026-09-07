# ArcMic

Windows 游戏麦克风增益与本地降噪工具。

## 下载

从 [GitHub Releases](https://github.com/Casheep/ArcMic/releases/latest) 下载 `ArcMic.exe`。

## 功能

- `0～30 dB` 麦克风数字增益
- 五档净噪：关闭、普通、中等、强力、最强
- 系统级麦克风处理，游戏继续使用原来的麦克风设备
- 15 秒耳机监听与实时输入电平
- 监听默认跟随 Windows 当前默认输出，也可固定选择耳机或扬声器
- 最小化到系统托盘，可随时查看开关状态
- 本地运行，无账号、无录音、无遥测、无网络请求

![ArcMic 界面](docs/ui-preview.png)

## 使用

1. 双击 `ArcMic.exe`，首次运行时接受 Windows 管理员授权。
2. 游戏中继续选择原来的麦克风，或保持系统默认输入设备。
3. 监听时请佩戴耳机，避免扬声器和麦克风形成啸叫。
4. “监听输出”选择“跟随 Windows 默认输出”时，每次监听都会使用 Windows 当前选择的输出设备。

## 兼容性

ArcMic 处理 Windows 共享模式录音流，适用于大多数使用 WASAPI 或 DirectSound 的游戏。WASAPI RAW、WASAPI Exclusive 和 ASIO 会绕过 Windows 系统音效，因此也会绕过 ArcMic。

## References

- [Equalizer APO 1.4.2](https://sourceforge.net/projects/equalizerapo/files/1.4.2/)：Windows 系统级低延迟麦克风处理
- [Real-time Noise Suppression Plugin 1.21](https://github.com/werman/noise-suppression-for-voice/tree/v1.21)：基于 RNNoise 的本地 AI 降噪
- [Python 3.12.10](https://www.python.org/)：界面与设置逻辑
- [python-sounddevice 0.5.2 / PortAudio](https://python-sounddevice.readthedocs.io/)：输入电平与耳机监听
- [CFFI 2.1.1](https://cffi.readthedocs.io/)：Python 与本地音频接口连接
- [pycparser 3.0](https://github.com/eliben/pycparser)：CFFI 解析支持
- [PyInstaller 6.16.0](https://pyinstaller.org/)：生成单文件 EXE
- [PyInstaller Hooks Contrib 2026.7](https://github.com/pyinstaller/pyinstaller-hooks-contrib)：PyInstaller 第三方库打包支持
- [altgraph 0.17.5](https://github.com/ronaldoussoren/altgraph)：构建依赖关系分析
- [packaging 26.3](https://github.com/pypa/packaging)：构建版本与包信息处理
- [pefile 2023.2.7](https://github.com/erocarrera/pefile)：Windows PE 文件处理
- [pywin32-ctypes 0.2.3](https://github.com/enthought/pywin32-ctypes)：Windows 构建接口支持
- [setuptools 84.0.0](https://github.com/pypa/setuptools)：Python 构建支持
- [pystray 0.19.5](https://github.com/moses-palmer/pystray)：系统托盘
- [six 1.17.0](https://github.com/benjaminp/six)：pystray 兼容支持
- [Pillow 11.3.0](https://python-pillow.github.io/)：托盘图标处理

## 许可证

ArcMic 采用 [GNU General Public License v3.0](LICENSE)。
