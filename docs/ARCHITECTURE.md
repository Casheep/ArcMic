# ArcMic architecture

```text
Physical microphone
        │
        ▼
Windows shared capture endpoint
        │
        ▼
Equalizer APO pre-mix stage
        │
        ├── 75 Hz–14 kHz natural cleanup (default)
        ├── RNNoise VST2 (optional strong mode)
        └── 0–30 dB gain
        │
        ├────────────► Game / Discord / WeChat
        │
        └────────────► ArcMic 15-second headphone monitor
```

## Why an APO instead of a permanent virtual microphone

- Games continue using their already configured physical microphone.
- No extra virtual device has to be selected inside every game.
- The real-time path runs in Windows Audio rather than a permanently running UI process.
- No application injection is required.
- Existing endpoint effects are preserved through Equalizer APO's child-APO chain and are backed up before ArcMic changes a binding.

The trade-off is that software explicitly requesting RAW, exclusive WASAPI or ASIO capture bypasses the Windows effects pipeline. ArcMic cannot transparently process a stream that Windows does not route through endpoint effects.

## First-run flow

1. The ordinary user process identifies the default WASAPI microphone and matches it to the corresponding MMDevice endpoint.
2. A narrowly scoped elevated helper copies the bundled engine to `%PROGRAMDATA%\ArcMic\engine`.
3. If Equalizer APO already exists, ArcMic reuses it. Otherwise the helper registers the bundled minimal APO engine.
4. The helper backs up only the target endpoint values it changes and attaches the pre-mix APO.
5. One marked include block is appended to the existing Equalizer APO `config.txt`; existing filters remain untouched.
6. Windows Audio is restarted once. Subsequent changes are picked up from `%LOCALAPPDATA%\ArcMic\ArcMic.txt` without elevation or restart.

## Runtime boundaries

- The managed config is atomically replaced to avoid partial reads.
- Endpoint rollback data is persisted before registry values are changed, and native engine files remain administrator-writable only.
- Gain is clamped to 30 dB in both persisted settings and config rendering.
- Monitoring automatically ends after 15 seconds and never writes samples to disk.
- Monitoring uses separate input/output streams and a bounded native resampling bridge, so a 48 kHz microphone can be heard through a 96 kHz DAC without changing either device.
- “Restore system settings” restores the backed-up endpoint and global audio values, removes only ArcMic's marked include block, and unregisters a minimal engine installed by ArcMic.
- If Equalizer APO existed before ArcMic, restoration does not unregister or remove it.
