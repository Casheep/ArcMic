from __future__ import annotations

import audioop
import threading
from collections.abc import Callable


class AudioMonitor:
    """Low-latency, temporary headphone monitor and live level meter.

    Audio is never written to disk. The normal Windows shared capture path is
    used so the meter and monitor hear the same APO-processed signal as games.
    """

    def __init__(self, level_callback: Callable[[float], None]) -> None:
        self.level_callback = level_callback
        self.input_index: int | None = None
        self.output_index: int | None = None
        self.monitoring = False
        self._input_stream = None
        self._output_stream = None
        self._state_lock = threading.Lock()
        self._buffer_lock = threading.Lock()
        self._playback_buffer = bytearray()

    @property
    def running(self) -> bool:
        return self._input_stream is not None

    def start(self, input_index: int | None, output_index: int | None, monitoring: bool = False) -> None:
        self.stop()
        if input_index is None:
            raise RuntimeError("No microphone input is available")
        if monitoring and output_index is None:
            raise RuntimeError("No monitoring output is available")
        import sounddevice as sd

        self.input_index = input_index
        self.output_index = output_index
        self.monitoring = monitoring
        input_rate = max(8_000, int(round(float(sd.query_devices(input_index)["default_samplerate"]))))

        if monitoring and output_index is not None:
            output_channels = max(1, min(2, int(sd.query_devices(output_index)["max_output_channels"])))
            output_rate = max(8_000, int(round(float(sd.query_devices(output_index)["default_samplerate"]))))
            input_block = max(64, input_rate // 100)
            output_block = max(64, output_rate // 100)
            max_buffer_bytes = max(output_block * output_channels * 2, output_rate * output_channels // 2)
            silence = bytes(output_block * output_channels * 2)
            rate_state = None

            def monitor_input_callback(indata, frames, time_info, status) -> None:
                nonlocal rate_state
                del frames, time_info, status
                samples = memoryview(indata).cast("h")
                peak = max((abs(samples[index]) for index in range(0, len(samples), 4)), default=0)
                self.level_callback(min(1.0, float(peak) / 32768.0))

                converted, rate_state = audioop.ratecv(
                    bytes(indata),
                    2,
                    1,
                    input_rate,
                    output_rate,
                    rate_state,
                )
                if output_channels == 2:
                    converted = audioop.tostereo(converted, 2, 1.0, 1.0)
                with self._buffer_lock:
                    self._playback_buffer.extend(converted)
                    overflow = len(self._playback_buffer) - max_buffer_bytes
                    if overflow > 0:
                        del self._playback_buffer[:overflow]

            def monitor_output_callback(outdata, frames, time_info, status) -> None:
                del frames, time_info, status
                required = len(outdata)
                outdata[:] = silence[:required] if required <= len(silence) else bytes(required)
                with self._buffer_lock:
                    available = min(required, len(self._playback_buffer))
                    if available:
                        outdata[:available] = self._playback_buffer[:available]
                        del self._playback_buffer[:available]

            self._input_stream = sd.RawInputStream(
                samplerate=input_rate,
                blocksize=input_block,
                device=input_index,
                channels=1,
                dtype="int16",
                latency="low",
                callback=monitor_input_callback,
            )
            self._output_stream = sd.RawOutputStream(
                samplerate=output_rate,
                blocksize=output_block,
                device=output_index,
                channels=output_channels,
                dtype="int16",
                latency="low",
                callback=monitor_output_callback,
            )
        else:

            def input_callback(indata, frames, time_info, status) -> None:
                del frames, time_info, status
                samples = memoryview(indata).cast("f")
                peak = max((abs(samples[index]) for index in range(0, len(samples), 4)), default=0.0)
                self.level_callback(min(1.0, float(peak)))

            self._input_stream = sd.RawInputStream(
                samplerate=input_rate,
                blocksize=max(128, input_rate // 50),
                device=input_index,
                channels=1,
                dtype="float32",
                latency="low",
                callback=input_callback,
            )
        try:
            self._input_stream.start()
            if self._output_stream is not None:
                self._output_stream.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        with self._state_lock:
            input_stream, self._input_stream = self._input_stream, None
            output_stream, self._output_stream = self._output_stream, None
        for stream in (output_stream, input_stream):
            if stream is None:
                continue
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._buffer_lock:
            self._playback_buffer.clear()
        self.monitoring = False
