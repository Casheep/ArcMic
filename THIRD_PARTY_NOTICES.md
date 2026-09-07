# Third-party notices

ArcMic distributes the following local runtime components inside its single-file Windows build. No component below is contacted over the network by the running application.

ArcMic 没有把下列项目包装成自研功能：这里明确列出每个公开组件的版本、用途、许可证、官方来源和对应源码。选择它们的原因是让系统级低延迟处理、轻量 AI 净噪、设备监听和单文件打包都能在本机完成。

## Equalizer APO 1.4.2

- Upstream: https://sourceforge.net/projects/equalizerapo/files/1.4.2/
- Corresponding source: `EqualizerAPO-src-1.4.2.zip`, attached to the ArcMic v0.2.4 GitHub Release
- Source SHA-256: `BACD5C78BE71F3AAAB010684AB39F0E5C1BBB45FCD75CBB92C103A145A731DC4`
- License: GPL-2.0-or-later; included as `vendor/licenses/EqualizerAPO-GPL-2.0.txt`
- Purpose/reason: low-latency system-wide Windows Audio Processing Object host and filter engine, so games can keep using the original microphone instead of a virtual cable

Vendored x64 hashes:

```text
EqualizerAPO.dll  FB73FC8B94F271464AE4F83918BB3CB3243C4F50A8035C07FA538AD16AD66AA4
fftw3f.dll        6C5DF497751D694E9C617F4C931A7F870B64784CB1A0EF09FCCC155BC86D1232
sndfile.dll       4E3BD2DE8E1485110EAEBEF8E1239471F73D608773831C323BF528E05645655E
```

The Microsoft Visual C++ app-local runtime files distributed with Equalizer APO retain Microsoft's license terms:

```text
msvcp140.dll       A4C2229BDC2A2A630ACDC095B4D86008E5C3E3BC7773174354F3DA4F5BEB9CDE
msvcp140_1.dll     91CD05C16C61C39788C47434602A59C17F5B08DBB3EEE04CE85F8D5B70E8E604
msvcp140_2.dll     713F17B253D802D283D306CE75647E37D83A546AEB1A881E5D9E529E856C007E
vcruntime140.dll   02C6AA0E6E624411A9F19B0360A7865AB15908E26024510E5C38A9C08362C35A
vcruntime140_1.dll 7DD9AA02E271C68CA6D5F18D651D23A15D7259715AF43326578F7DDE27F37637
```

## Real-time Noise Suppression Plugin 1.21

- Upstream/source: https://github.com/werman/noise-suppression-for-voice/tree/v1.21
- Release: https://github.com/werman/noise-suppression-for-voice/releases/tag/v1.21
- Corresponding source: `noise-suppression-for-voice-v1.21-source.zip`, attached to the ArcMic v0.2.4 GitHub Release
- Source SHA-256: `08D1D406FE240CB688F32A3F13CC3C4D86A03B3662378F37141C5E84DAEEEBF8`
- License: GPL-3.0; included as `vendor/licenses/RNNoise-Plugin-GPL-3.0.txt`
- Purpose/reason: CPU-efficient RNNoise speech denoising in an x64 mono VST2, providing the stronger modes without continuously routing audio through the Python UI
- SHA-256: `664CE729BACA985652C24515593E43A7C0105F7A0FB64E75B6B90776B9BD6495`

## Python packaging and monitoring libraries

- Python 3.12.10: https://www.python.org/; PSF License; included as `vendor/licenses/Python-PSF-LICENSE.txt`; runs the desktop UI and setup logic
- python-sounddevice 0.5.2 and PortAudio: https://python-sounddevice.readthedocs.io/; MIT; included as `vendor/licenses/python-sounddevice-LICENSE.txt`; reads the local meter and performs user-requested monitoring
- CFFI 2.1.1: https://cffi.readthedocs.io/; MIT; included as `vendor/licenses/cffi-LICENSE.txt`; sounddevice's native binding layer
- pycparser 3.0: https://github.com/eliben/pycparser; BSD-3-Clause; included as `vendor/licenses/pycparser-LICENSE.txt`; CFFI support dependency
- PyInstaller 6.16.0: https://pyinstaller.org/; GPL with the PyInstaller bootloader exception; included as `vendor/licenses/PyInstaller-COPYING.txt`; creates the standalone EXE

PyInstaller is used only to assemble the executable. python-sounddevice is used only while the ArcMic window is open for the live meter and user-initiated monitoring; the system-wide enhancement path remains native.

The remaining pinned packages in `requirements-build.txt` are build-time helpers pulled by PyInstaller and are not imported by the ArcMic application at runtime:

- pyinstaller-hooks-contrib 2026.7: https://github.com/pyinstaller/pyinstaller-hooks-contrib; GPL-2.0-or-later for standard hooks, Apache-2.0 for runtime hooks
- altgraph 0.17.5: https://github.com/ronaldoussoren/altgraph; MIT
- packaging 26.3: https://github.com/pypa/packaging; Apache-2.0 OR BSD-2-Clause
- pefile 2023.2.7: https://github.com/erocarrera/pefile; MIT
- pywin32-ctypes 0.2.3: https://github.com/enthought/pywin32-ctypes; BSD-3-Clause
- setuptools 84.0.0: https://github.com/pypa/setuptools; MIT

Their source and license files are available from those upstream repositories and the exact package releases named above.

## System tray libraries

- pystray 0.19.5: https://github.com/moses-palmer/pystray; LGPL-3.0; included as `vendor/licenses/pystray-LGPL-3.0.txt` together with `vendor/licenses/pystray-GPL-3.0.txt`; provides the notification-area icon and menu
- six 1.17.0: https://github.com/benjaminp/six; MIT; included as `vendor/licenses/six-MIT-LICENSE.txt`; pystray compatibility dependency
- Pillow 11.3.0: https://python-pillow.github.io/; MIT-CMU; included as `vendor/licenses/Pillow-LICENSE.txt`; loads the local tray icon

These libraries only provide the local Windows notification-area icon and menu. They do not add network access or telemetry.

The source for ArcMic itself is the GitHub repository at the exact release tag. Unmodified third-party source archives accompanying the executable are provided for convenient, same-page access; copyright remains with their respective authors. See `SOURCE_CODE.md` for the reproducibility map.
