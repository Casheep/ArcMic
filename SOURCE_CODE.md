# Source code and release correspondence

ArcMic v0.2.4 is distributed as `ArcMic.exe`. The preferred form for modifying ArcMic is the source tree at Git tag `v0.2.4`; GitHub automatically exposes that tagged tree as the Release's `Source code (zip)` and `Source code (tar.gz)` downloads.

The same Release also carries the unmodified corresponding source archives for the two GPL audio binaries bundled inside the EXE:

| Runtime component | Binary version | Corresponding source asset | SHA-256 |
| --- | --- | --- | --- |
| Equalizer APO | 1.4.2 x64 | `EqualizerAPO-src-1.4.2.zip` | `BACD5C78BE71F3AAAB010684AB39F0E5C1BBB45FCD75CBB92C103A145A731DC4` |
| Real-time Noise Suppression Plugin | 1.21 x64 mono VST2 | `noise-suppression-for-voice-v1.21-source.zip` | `08D1D406FE240CB688F32A3F13CC3C4D86A03B3662378F37141C5E84DAEEEBF8` |

Both archives include their upstream license files. The RNNoise plugin archive also contains its vendored JUCE, FST and RNNoise sources. ArcMic does not modify either third-party audio binary.

The exact Python package versions used for the build are pinned in `requirements-build.txt` and expanded in `THIRD_PARTY_NOTICES.md`. Their license texts are kept in `vendor/licenses` and are also embedded into the one-file build. Build reproduction instructions are in `README.md` and `scripts/build.ps1`.

`SHA256SUMS.txt` on the Release covers the executable, the two corresponding-source archives, and the accompanying notice/license files.
