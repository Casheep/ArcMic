from __future__ import annotations

import ctypes
import math
import queue
import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from PIL import ImageTk

from .config import AppSettings, MAX_GAIN_DB, SettingsStore, write_managed_config
from .devices import (
    CaptureDevice,
    choose_monitor_output,
    choose_default_device,
    get_wasapi_devices,
    list_capture_devices,
    list_wasapi_outputs,
    match_wasapi_index,
    refresh_wasapi_devices,
)
from .engine import installation_ready, resource_path, run_elevated_and_wait
from .graphics import (
    arc_logo as render_arc_logo,
    gain_dial as render_gain_dial,
    level_meter as render_level_meter,
    pill_switch as render_pill_switch,
    rounded_panel as render_rounded_panel,
    status_dot as render_status_dot,
)
from .monitor import AudioMonitor


BG = "#F1F3F7"
CARD = "#FFFFFF"
TEXT = "#111318"
MUTED = "#59616E"
BORDER = "#D8DDE7"
TRACK = "#E1E5ED"
ACCENT = "#506CF5"
ACCENT_LIGHT = "#E9EDFF"
GREEN = "#20B97A"
AMBER = "#E89A38"
RED = "#E45D66"
UI_FONT = "Microsoft YaHei UI"
DISPLAY_FONT = "Segoe UI Variable Display"
FOLLOW_SYSTEM_OUTPUT = "跟随 Windows 默认输出"
NOISE_MODE_LABELS = {
    "off": "关闭",
    "natural": "普通",
    "hum": "中等",
    "ai": "强力",
    "ai_hum": "最强（推荐）",
}
NOISE_MODE_ORDER = ("off", "natural", "hum", "ai", "ai_hum")
NOISE_MODE_FROM_LABEL = {label: mode for mode, label in NOISE_MODE_LABELS.items()}
NOISE_MODE_DESCRIPTIONS = {
    "off": "不降噪，只增大麦克风声音",
    "natural": "轻微清理杂音，声音最接近原声",
    "hum": "进一步清理持续底噪，基本不改变人声",
    "ai": "使用 AI 清理大部分环境噪音",
    "ai_hum": "优先保证干净度，适合底噪明显的麦克风",
}

UI_TICK_MS = 50
HIDDEN_TICK_MS = 100


class PillSwitch(tk.Canvas):
    def __init__(self, parent, value: bool, command, scale: float = 1.0):
        width, height = round(52 * scale), round(30 * scale)
        super().__init__(parent, width=width, height=height, highlightthickness=0, bg=CARD, cursor="hand2")
        self.value = bool(value)
        self.command = command
        self._scale = scale
        self._width = width
        self._height = height
        self.bind("<Button-1>", self._toggle)
        self.draw()

    def _toggle(self, _event=None):
        self.value = not self.value
        self.draw()
        self.command(self.value)

    def set(self, value: bool):
        self.value = bool(value)
        self.draw()

    def draw(self):
        self.delete("all")
        image = render_pill_switch(
            self._width,
            self._height,
            self._scale,
            self.value,
            background=CARD,
            accent=ACCENT,
        )
        self._image = ImageTk.PhotoImage(image)
        self.create_image(0, 0, anchor="nw", image=self._image)


class GainDial(tk.Canvas):
    START = 210
    SPAN = -240
    CENTER = (143.0, 129.0)
    RADIUS = 111.0

    def __init__(self, parent, value: float, command, scale: float = 1.0):
        self._width = round(286 * scale)
        self._height = round(252 * scale)
        super().__init__(parent, width=self._width, height=self._height, highlightthickness=0, bg=CARD, cursor="hand2")
        self.value = float(value)
        self.command = command
        self._scale = scale
        self.bind("<Button-1>", self._set_from_pointer)
        self.bind("<B1-Motion>", self._set_from_pointer)
        self.bind("<MouseWheel>", self._wheel)
        self.draw()

    def _wheel(self, event):
        self.set_value(self.value + (0.5 if event.delta > 0 else -0.5), notify=True)

    @classmethod
    def value_from_point(cls, x: float, y: float) -> float:
        angle = math.degrees(math.atan2(-(y - cls.CENTER[1]), x - cls.CENTER[0])) % 360
        travelled = (cls.START - angle) % 360
        span = abs(cls.SPAN)
        if travelled > span:
            # The pointer is in the unpainted gap. Choose the nearest endpoint
            # instead of always clamping to the maximum; otherwise moving just
            # past the 0 dB endpoint wraps around and suddenly produces 30 dB.
            start = cls.START % 360
            end = (cls.START + cls.SPAN) % 360
            start_distance = abs((angle - start + 180) % 360 - 180)
            end_distance = abs((angle - end + 180) % 360 - 180)
            travelled = 0.0 if start_distance <= end_distance else span
        return (travelled / abs(cls.SPAN)) * MAX_GAIN_DB

    @classmethod
    def point_for_value(cls, value: float) -> tuple[float, float]:
        value = min(MAX_GAIN_DB, max(0.0, float(value)))
        angle = math.radians(cls.START + cls.SPAN * value / MAX_GAIN_DB)
        return (
            cls.CENTER[0] + cls.RADIUS * math.cos(angle),
            cls.CENTER[1] - cls.RADIUS * math.sin(angle),
        )

    def _set_from_pointer(self, event):
        pointer_x, pointer_y = event.x / self._scale, event.y / self._scale
        self.set_value(self.value_from_point(pointer_x, pointer_y), notify=True)

    def set_value(self, value: float, notify: bool = False):
        value = min(MAX_GAIN_DB, max(0.0, round(float(value) * 2) / 2))
        if value == self.value and notify:
            return
        self.value = value
        self.draw()
        if notify:
            self.command(value)

    def draw(self):
        self.delete("all")
        p = lambda value: value * self._scale
        colour = ACCENT if self.value <= 12 else (AMBER if self.value <= 20 else RED)
        image = render_gain_dial(
            self._width,
            self._height,
            self._scale,
            self.value,
            MAX_GAIN_DB,
            background=CARD,
            track=TRACK,
            colour=colour,
            start=self.START,
            span=self.SPAN,
            centre=self.CENTER,
            radius=self.RADIUS,
        )
        self._image = ImageTk.PhotoImage(image)
        self.create_image(0, 0, anchor="nw", image=self._image)
        self.create_text(p(143), p(106), text=f"+{self.value:.1f}", fill=TEXT, font=(DISPLAY_FONT, 32, "bold"))
        self.create_text(p(143), p(145), text="dB 增益", fill=MUTED, font=(UI_FONT, 11))
        label = "舒适" if self.value <= 12 else ("强劲" if self.value <= 20 else "极高")
        self.create_text(p(143), p(177), text=label, fill=colour, font=(UI_FONT, 10, "bold"))


class LevelBar(tk.Canvas):
    def __init__(self, parent, width: int = 610, scale: float = 1.0):
        super().__init__(parent, width=round(width * scale), height=round(18 * scale), highlightthickness=0, bg=CARD)
        self._width = round(width * scale)
        self._scale = scale
        self.level = 0.0
        self.display_level = 0.0
        self._last_render_key = None
        self.bind("<Configure>", self._resize)
        self.draw(force=True)

    def _resize(self, event):
        width = max(1, event.width)
        if width != self._width:
            self._width = width
            self.draw(force=True)

    def set_level(self, level: float):
        self.level = min(1.0, max(0.0, float(level)))

    def animate(self):
        previous = self.display_level
        if self.level > self.display_level:
            self.display_level = self.level
        else:
            self.display_level *= 0.82
        self.level *= 0.70
        if self.display_level < 0.001:
            self.display_level = 0.0
        if abs(self.display_level - previous) >= 0.002 or self.display_level == 0.0 < previous:
            self.draw()

    def draw(self, force: bool = False):
        colour = GREEN if self.display_level < 0.78 else (AMBER if self.display_level < 0.93 else RED)
        render_key = (self._width, round(self.display_level, 3), colour)
        if not force and render_key == self._last_render_key:
            return
        self._last_render_key = render_key
        self.delete("all")
        image = render_level_meter(
            self._width,
            round(18 * self._scale),
            self._scale,
            self.display_level,
            background=CARD,
            track=TRACK,
            colour=colour,
        )
        self._image = ImageTk.PhotoImage(image)
        self.create_image(0, 0, anchor="nw", image=self._image)


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text: str, command, scale: float = 1.0):
        self._scale = scale
        self._height = round(43 * scale)
        super().__init__(
            parent,
            height=self._height,
            bg=CARD,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self.command = command
        self._text = text
        self._background = ACCENT_LIGHT
        self._active_background = "#DDE3FF"
        self._foreground = ACCENT
        self._hovered = False
        self._pressed = False
        self._last_render_key = None
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", self._invoke)
        self.bind("<space>", self._invoke)

    def set_appearance(self, *, text: str, background: str, foreground: str, active_background: str):
        self._text = text
        self._background = background
        self._foreground = foreground
        self._active_background = active_background
        self._last_render_key = None
        self._draw()

    def _enter(self, _event=None):
        self._hovered = True
        self._draw()

    def _leave(self, _event=None):
        self._hovered = False
        self._pressed = False
        self._draw()

    def _press(self, _event=None):
        self._pressed = True
        self._draw()

    def _release(self, event):
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.command()

    def _invoke(self, _event=None):
        self.command()
        return "break"

    def _draw(self, _event=None):
        width = max(1, self.winfo_width())
        background = self._active_background if self._hovered or self._pressed else self._background
        render_key = (width, background, self._foreground, self._text)
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key
        image = render_rounded_panel(
            width,
            self._height,
            12 * self._scale,
            fill=background,
            background=CARD,
        )
        self._image = ImageTk.PhotoImage(image)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=self._image)
        self.create_text(
            width / 2,
            self._height / 2,
            text=self._text,
            fill=self._foreground,
            font=(UI_FONT, 11, "bold"),
        )


class ArcMicApp:
    def __init__(self, demo: bool = False):
        self.demo = demo
        self._tray_icon = None
        self._tray_actions: queue.SimpleQueue = queue.SimpleQueue()
        self._exiting = False
        self.root = tk.Tk()
        self.root.title("ArcMic 麦克风增强")
        try:
            icon_path = resource_path("assets", "app.ico")
            if icon_path.exists():
                self.root.iconbitmap(default=str(icon_path))
        except (OSError, tk.TclError):
            pass
        try:
            dpi = int(ctypes.windll.user32.GetDpiForWindow(self.root.winfo_id()))
        except (AttributeError, OSError):
            dpi = 96
        requested_scale = max(1.0, dpi / 96.0)
        fit_scale = min(self.root.winfo_screenwidth() / 860, self.root.winfo_screenheight() / 820)
        self.ui_scale = max(1.0, min(requested_scale, fit_scale))
        self.root.tk.call("tk", "scaling", dpi / 72.0)
        self.root.geometry(f"{self._px(820)}x{self._px(760)}")
        self.root.minsize(self._px(780), self._px(720))
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.root.bind("<Unmap>", self._on_unmap)
        self._round_window_corners()

        self.store = SettingsStore()
        self.settings = AppSettings() if demo else self.store.load()
        self.devices = self._load_devices()
        self.wasapi_inputs, self.default_audio_name, self.default_input_index, self.default_output_index = get_wasapi_devices()
        self.wasapi_outputs = (
            [{"index": 7, "name": "耳机（推荐）", "channels": 2}] if demo else list_wasapi_outputs()
        )
        self.selected_output = choose_monitor_output(
            self.wasapi_outputs, self.settings.monitor_output_name, self.default_output_index
        )
        self.selected_device = self._select_initial_device()
        self._pending_level = 0.0
        self.monitor = AudioMonitor(self._receive_level)
        self._save_job = None
        self._monitor_timeout = None
        self._setup_running = False
        self._last_tray_title = ""

        self._configure_styles()
        self._build_ui()
        if not demo:
            self._start_tray()
        self.root.after(80, self._tick)
        self.root.after(220, self._start_meter)
        if not demo:
            self.root.after(350, self._ensure_ready)
        else:
            self._set_status("界面预览 · 未修改系统", MUTED)

    def _px(self, value: float) -> int:
        return max(1, round(value * self.ui_scale))

    def _round_window_corners(self):
        try:
            self.root.update_idletasks()
            preference = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self.root.winfo_id(), 33, ctypes.byref(preference), ctypes.sizeof(preference)
            )
        except Exception:
            pass

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure(
            "Arc.TCombobox",
            padding=(10, 5),
            fieldbackground="#F7F8FA",
            background="#F7F8FA",
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=MUTED,
            font=(UI_FONT, 10),
        )
        style.map("Arc.TCombobox", fieldbackground=[("readonly", "#F7F8FA")], foreground=[("readonly", TEXT)])

    def _load_devices(self) -> list[CaptureDevice]:
        if self.demo:
            return [CaptureDevice("{00000000-0000-0000-0000-000000000001}", "默认麦克风", "游戏耳机", 1)]
        return list_capture_devices(active_only=True)

    def _select_initial_device(self) -> CaptureDevice | None:
        if self.settings.device_guid:
            existing = next((item for item in self.devices if item.guid.casefold() == self.settings.device_guid.casefold()), None)
            if existing:
                return existing
        selected = choose_default_device(self.devices, self.default_audio_name) if self.devices else None
        if selected:
            self.settings.device_guid = selected.guid
        return selected

    def _card(self, parent, **grid_options):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, height=1)
        if grid_options:
            canvas.grid(**grid_options)
        frame = tk.Frame(canvas, bg=CARD)

        def redraw(_event=None):
            width = max(1, canvas.winfo_width())
            height = max(1, canvas.winfo_height())
            render_key = (width, height)
            if render_key != getattr(canvas, "_card_render_key", None):
                canvas._card_render_key = render_key
                image = render_rounded_panel(
                    width,
                    height,
                    self._px(24),
                    fill=CARD,
                    background=BG,
                    outline=BORDER,
                    outline_width=self._px(1),
                )
                canvas._card_image = ImageTk.PhotoImage(image)
                canvas.delete("card")
                canvas.create_image(0, 0, anchor="nw", image=canvas._card_image, tags="card")
                canvas.tag_lower("card")
            canvas.coords(window, self._px(24), self._px(22))
            canvas.itemconfigure(
                window,
                width=max(1, width - self._px(48)),
                height=max(1, height - self._px(44)),
            )

        window = canvas.create_window(self._px(24), self._px(22), window=frame, anchor="nw")
        canvas.bind("<Configure>", redraw)
        return canvas, frame

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=self._px(38), pady=(self._px(28), self._px(30)))

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        logo = tk.Canvas(header, width=self._px(46), height=self._px(46), bg=BG, highlightthickness=0)
        logo.pack(side="left", padx=(0, self._px(13)))
        logo._image = ImageTk.PhotoImage(render_arc_logo(self._px(46), self.ui_scale, background=BG, accent=ACCENT))
        logo.create_image(0, 0, anchor="nw", image=logo._image)
        title_wrap = tk.Frame(header, bg=BG)
        title_wrap.pack(side="left")
        tk.Label(title_wrap, text="ArcMic", bg=BG, fg=TEXT, font=(DISPLAY_FONT, 22, "bold")).pack(anchor="w")
        tk.Label(title_wrap, text="游戏麦克风增强", bg=BG, fg=MUTED, font=(UI_FONT, 10)).pack(anchor="w")
        status_wrap = tk.Frame(header, bg=BG)
        status_wrap.pack(side="right")
        self.status_dot = tk.Canvas(status_wrap, width=self._px(12), height=self._px(12), bg=BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, self._px(7)))
        self.status_label = tk.Label(status_wrap, text="正在准备", bg=BG, fg=MUTED, font=(UI_FONT, 10))
        self.status_label.pack(side="left")

        device_canvas, device_card = self._card(outer)
        device_canvas.pack_configure(fill="x", pady=(self._px(24), self._px(14)))
        device_canvas.configure(height=self._px(116))
        input_wrap = tk.Frame(device_card, bg=CARD)
        input_wrap.pack(side="left", fill="both", expand=True, padx=(0, self._px(7)))
        output_wrap = tk.Frame(device_card, bg=CARD)
        output_wrap.pack(side="left", fill="both", expand=True, padx=(self._px(7), 0))
        tk.Label(input_wrap, text="输入设备", bg=CARD, fg=MUTED, font=(UI_FONT, 10, "bold")).pack(anchor="w")
        self.device_var = tk.StringVar(value=self.selected_device.label if self.selected_device else "未找到可用麦克风")
        self.device_combo = ttk.Combobox(
            input_wrap,
            textvariable=self.device_var,
            values=[item.label for item in self.devices],
            state="readonly" if self.devices else "disabled",
            style="Arc.TCombobox",
        )
        self.device_combo.pack(fill="x", pady=(self._px(8), 0))
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_changed)
        tk.Label(output_wrap, text="监听输出", bg=CARD, fg=MUTED, font=(UI_FONT, 10, "bold")).pack(anchor="w")
        self.output_var = tk.StringVar(
            value=str(self.selected_output["name"]) if self.settings.monitor_output_name and self.selected_output else FOLLOW_SYSTEM_OUTPUT
        )
        self.output_combo = ttk.Combobox(
            output_wrap,
            textvariable=self.output_var,
            values=[FOLLOW_SYSTEM_OUTPUT, *[str(item["name"]) for item in self.wasapi_outputs]],
            state="readonly" if self.wasapi_outputs else "disabled",
            style="Arc.TCombobox",
        )
        self.output_combo.pack(fill="x", pady=(self._px(8), 0))
        self.output_combo.bind("<<ComboboxSelected>>", self._on_output_changed)

        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1, uniform="content")
        content.grid_columnconfigure(1, weight=1, uniform="content")
        content.grid_rowconfigure(0, weight=1)

        dial_canvas, dial_card = self._card(content, row=0, column=0, sticky="nsew", padx=(0, self._px(7)))
        self.dial = GainDial(dial_card, self.settings.gain_db, self._on_gain_changed, self.ui_scale)
        self.dial.pack(expand=True)
        tk.Label(
            dial_card,
            text="12 dB 以上可能放大底噪\n20～30 dB 仅用于特别小的麦克风",
            bg=CARD,
            fg=MUTED,
            wraplength=self._px(300),
            justify="center",
            font=(UI_FONT, 9),
        ).pack(pady=(0, self._px(4)))

        controls_canvas, controls = self._card(content, row=0, column=1, sticky="nsew", padx=(self._px(7), 0))
        tk.Label(controls, text="声音处理", bg=CARD, fg=TEXT, font=(UI_FONT, 15, "bold")).pack(anchor="w", pady=(self._px(2), self._px(14)))
        self.master_switch = self._setting_row(controls, "麦克风增强", "游戏与语音全局生效", self.settings.enabled, self._on_enabled_changed)
        self._noise_mode_row(controls)

        divider = tk.Frame(controls, bg=BORDER, height=1)
        divider.pack(fill="x", pady=(self._px(12), self._px(16)))
        self.listen_button = RoundedButton(controls, "耳机监听 15 秒", self._toggle_monitor, self.ui_scale)
        self.listen_button.pack(fill="x")
        tk.Label(
            controls,
            text="请佩戴耳机，扬声器监听可能产生啸叫",
            bg=CARD,
            fg=MUTED,
            font=(UI_FONT, 9),
        ).pack(anchor="w", pady=(self._px(9), 0))

        meter_canvas, meter_card = self._card(outer)
        meter_canvas.pack_configure(fill="x", pady=(self._px(14), 0))
        meter_canvas.configure(height=self._px(88))
        top = tk.Frame(meter_card, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="实时输入电平", bg=CARD, fg=TEXT, font=(UI_FONT, 10, "bold")).pack(side="left")
        tk.Label(top, text="仅本机处理 · 不录音 · 不上传", bg=CARD, fg=GREEN, font=(UI_FONT, 9)).pack(side="right")
        self.level_bar = LevelBar(meter_card, scale=self.ui_scale)
        self.level_bar.pack(fill="x", pady=(self._px(11), 0))

        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", pady=(self._px(13), 0))
        tk.Label(footer, text="关闭或最小化后驻留托盘，可随时查看开关状态", bg=BG, fg=MUTED, font=(UI_FONT, 9)).pack(side="left")
        restore = tk.Label(footer, text="恢复系统设置", bg=BG, fg=ACCENT, cursor="hand2", font=(UI_FONT, 9, "underline"))
        restore.pack(side="right")
        restore.bind("<Button-1>", self._restore)

    def _setting_row(self, parent, title: str, subtitle: str, value: bool, command):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, self._px(16)))
        labels = tk.Frame(row, bg=CARD)
        labels.pack(side="left", fill="x", expand=True)
        tk.Label(labels, text=title, bg=CARD, fg=TEXT, font=(UI_FONT, 11, "bold")).pack(anchor="w")
        tk.Label(labels, text=subtitle, bg=CARD, fg=MUTED, font=(UI_FONT, 9)).pack(anchor="w", pady=(self._px(3), 0))
        switch = PillSwitch(row, value, command, self.ui_scale)
        switch.pack(side="right")
        return switch

    def _noise_mode_row(self, parent):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=(0, self._px(14)))
        heading = tk.Frame(row, bg=CARD)
        heading.pack(fill="x")
        tk.Label(heading, text="净噪模式", bg=CARD, fg=TEXT, font=(UI_FONT, 11, "bold")).pack(side="left")
        self.noise_var = tk.StringVar(value=NOISE_MODE_LABELS[self.settings.noise_mode])
        self.noise_combo = ttk.Combobox(
            row,
            textvariable=self.noise_var,
            values=[NOISE_MODE_LABELS[mode] for mode in NOISE_MODE_ORDER],
            state="readonly",
            style="Arc.TCombobox",
            width=18,
        )
        self.noise_combo.pack(fill="x", pady=(self._px(7), self._px(4)))
        self.noise_combo.bind("<<ComboboxSelected>>", self._on_noise_mode_changed)
        self.noise_description = tk.Label(
            row,
            text=NOISE_MODE_DESCRIPTIONS[self.settings.noise_mode],
            bg=CARD,
            fg=MUTED,
            font=(UI_FONT, 9),
        )
        self.noise_description.pack(anchor="w")

    def _set_status(self, text: str, colour: str):
        self.status_label.configure(text=text, fg=colour)
        self.status_dot.delete("all")
        image = render_status_dot(self._px(12), self.ui_scale, background=BG, colour=colour)
        self._status_dot_image = ImageTk.PhotoImage(image)
        self.status_dot.create_image(0, 0, anchor="nw", image=self._status_dot_image)
        self._update_tray()

    def _receive_level(self, level: float):
        self._pending_level = max(self._pending_level, level)

    def _tick(self):
        while True:
            try:
                action = self._tray_actions.get_nowait()
            except queue.Empty:
                break
            action()
            if self._exiting:
                return
        visible = self.root.state() != "withdrawn" and self.root.winfo_viewable()
        if visible:
            self.level_bar.set_level(self._pending_level)
            self._pending_level = 0.0
            self.level_bar.animate()
        else:
            self._pending_level = 0.0
        self.root.after(UI_TICK_MS if visible else HIDDEN_TICK_MS, self._tick)

    def _current_input_index(self) -> int | None:
        if self.selected_device:
            return match_wasapi_index(self.selected_device, self.wasapi_inputs)
        return self.default_input_index

    def _current_output_index(self) -> int | None:
        if not self.settings.monitor_output_name:
            return self.default_output_index
        return int(self.selected_output["index"]) if self.selected_output else self.default_output_index

    def _refresh_audio_routes(self):
        self.wasapi_inputs, self.default_audio_name, self.default_input_index, self.default_output_index = (
            refresh_wasapi_devices()
        )
        self.wasapi_outputs = list_wasapi_outputs()
        self.selected_output = choose_monitor_output(
            self.wasapi_outputs,
            self.settings.monitor_output_name,
            self.default_output_index,
        )
        output_values = [FOLLOW_SYSTEM_OUTPUT] + [str(item["name"]) for item in self.wasapi_outputs]
        self.output_combo.configure(values=output_values)

    def _start_meter(self):
        try:
            self.monitor.start(self._current_input_index(), self._current_output_index(), monitoring=False)
        except Exception:
            self._set_status("麦克风正被占用", AMBER)

    def _apply_soon(self):
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(140, self._apply_now)

    def _apply_now(self):
        self._save_job = None
        if self.selected_device:
            self.settings.device_guid = self.selected_device.guid
        try:
            if not self.demo:
                self.store.save(self.settings)
                write_managed_config(self.settings)
            if self.demo:
                self._set_status("界面预览 · 未修改系统", MUTED)
            elif installation_ready(self.settings.device_guid):
                self._set_status("正在增强" if self.settings.enabled else "增强已关闭", GREEN if self.settings.enabled else MUTED)
        except OSError:
            self._set_status("无法写入设置", RED)

    def _on_gain_changed(self, value: float):
        self.settings.gain_db = value
        self._apply_soon()

    def _on_enabled_changed(self, value: bool):
        self.settings.enabled = value
        self._apply_now()

    def _toggle_enabled_from_tray(self):
        value = not self.settings.enabled
        self.master_switch.set(value)
        self._on_enabled_changed(value)

    def _on_noise_mode_changed(self, _event=None):
        self.settings.noise_mode = NOISE_MODE_FROM_LABEL.get(self.noise_var.get(), "ai_hum")
        self.noise_description.configure(text=NOISE_MODE_DESCRIPTIONS[self.settings.noise_mode])
        self._apply_now()

    def _on_device_changed(self, _event=None):
        label = self.device_var.get()
        selected = next((item for item in self.devices if item.label == label), None)
        if not selected:
            return
        self.selected_device = selected
        self.settings.device_guid = selected.guid
        self._apply_now()
        self._start_meter()
        if not self.demo:
            self._ensure_ready()

    def _on_output_changed(self, _event=None):
        name = self.output_var.get()
        if name == FOLLOW_SYSTEM_OUTPUT:
            self.selected_output = None
            self.settings.monitor_output_name = ""
            self._apply_soon()
            return
        selected = next((item for item in self.wasapi_outputs if str(item["name"]) == name), None)
        if not selected:
            return
        self.selected_output = selected
        self.settings.monitor_output_name = name
        self._apply_soon()

    def _ensure_ready(self):
        if not self.selected_device:
            self._set_status("未找到麦克风", RED)
            return
        if installation_ready(self.selected_device.guid):
            self._apply_now()
            return
        if self._setup_running:
            return
        self._setup_running = True
        self._set_status("首次配置 · 请允许系统授权", AMBER)

        def worker():
            code = run_elevated_and_wait(["--setup", self.selected_device.guid])
            self.root.after(0, lambda: self._setup_finished(code))

        threading.Thread(target=worker, daemon=True).start()

    def _setup_finished(self, code: int):
        self._setup_running = False
        if code == 0 and self.selected_device and installation_ready(self.selected_device.guid):
            self._apply_now()
            self._set_status("正在增强", GREEN)
            self._start_meter()
        elif code == 1223:
            self._set_status("已取消系统授权", AMBER)
        else:
            self._set_status("配置失败 · 可重新启动重试", RED)

    def _toggle_monitor(self):
        if self.monitor.monitoring:
            self._stop_monitoring()
            return
        try:
            # The Windows default output may have changed since ArcMic opened.
            # Stop the meter first so PortAudio can be safely refreshed.
            self.monitor.stop()
            self._refresh_audio_routes()
            output_index = self._current_output_index()
            self.monitor.start(self._current_input_index(), output_index, monitoring=True)
            self.listen_button.set_appearance(
                text="停止监听",
                background="#FFF1E4",
                foreground=AMBER,
                active_background="#FFE4C7",
            )
            output = next(
                (item for item in self.wasapi_outputs if int(item["index"]) == output_index),
                None,
            )
            output_name = str(output["name"]) if output else "当前输出设备"
            if len(output_name) > 22:
                output_name = output_name[:21] + "…"
            self._set_status(f"监听中 · {output_name}", AMBER)
            self._monitor_timeout = self.root.after(15_000, self._stop_monitoring)
        except Exception as exc:
            self._set_status(f"监听失败 · {str(exc)[:18]}", RED)
            self._start_meter()

    def _stop_monitoring(self):
        if self._monitor_timeout is not None:
            self.root.after_cancel(self._monitor_timeout)
            self._monitor_timeout = None
        self.monitor.stop()
        self.listen_button.set_appearance(
            text="耳机监听 15 秒",
            background=ACCENT_LIGHT,
            foreground=ACCENT,
            active_background="#DDE3FF",
        )
        self._start_meter()
        if self.demo:
            self._set_status("界面预览 · 未修改系统", MUTED)
        else:
            self._apply_now()

    def _restore(self, _event=None):
        if self.demo:
            self._set_status("预览模式没有修改系统", MUTED)
            return
        if not messagebox.askyesno("恢复系统设置", "移除 ArcMic 的系统音频绑定并恢复原来的麦克风处理吗？"):
            return
        self.monitor.stop()
        self._set_status("正在恢复", AMBER)

        def worker():
            code = run_elevated_and_wait(["--restore"])
            self.root.after(0, lambda: self._restore_finished(code))

        threading.Thread(target=worker, daemon=True).start()

    def _restore_finished(self, code: int):
        if code == 0:
            self._set_status("系统设置已恢复", MUTED)
        else:
            self._set_status("恢复失败", RED)
        self._start_meter()

    def _start_tray(self):
        try:
            import pystray
            from PIL import Image

            image = Image.open(resource_path("assets", "app.ico")).convert("RGBA")
            menu = pystray.Menu(
                pystray.MenuItem(lambda _item: self._tray_status_text(), None, enabled=False),
                pystray.MenuItem(
                    "打开 ArcMic",
                    lambda _icon, _item: self._queue_tray_action(self._show_window),
                    default=True,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "麦克风增强",
                    lambda _icon, _item: self._queue_tray_action(self._toggle_enabled_from_tray),
                    checked=lambda _item: self.settings.enabled,
                ),
                pystray.MenuItem(
                    "退出 ArcMic",
                    lambda _icon, _item: self._queue_tray_action(self._exit_app),
                ),
            )
            self._tray_icon = pystray.Icon("ArcMic", image, self._tray_status_text(), menu)
            self._tray_icon.run_detached()
        except Exception:
            self._tray_icon = None

    def _queue_tray_action(self, action):
        self._tray_actions.put(action)

    def _tray_status_text(self) -> str:
        if self.settings.enabled:
            return f"ArcMic 正在增强 · +{self.settings.gain_db:.1f} dB"
        return "ArcMic 增强已关闭"

    def _update_tray(self):
        if self._tray_icon is None:
            return
        title = self._tray_status_text()
        if title == self._last_tray_title:
            return
        try:
            self._tray_icon.title = title
            self._tray_icon.update_menu()
            self._last_tray_title = title
        except Exception:
            pass

    def _on_unmap(self, event):
        if event.widget is self.root and not self._exiting:
            self.root.after(20, self._hide_if_minimized)

    def _hide_if_minimized(self):
        if not self._exiting and self.root.state() == "iconic":
            self._hide_to_tray()

    def _hide_to_tray(self):
        if self.demo or self._tray_icon is None:
            self._exit_app()
            return
        self.monitor.stop()
        self._apply_now()
        self.root.withdraw()

    def _show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self._start_meter()

    def _exit_app(self):
        if self._exiting:
            return
        self._exiting = True
        self.monitor.stop()
        if not self.demo:
            self.store.save(self.settings)
            write_managed_config(replace(self.settings, enabled=False))
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.root.destroy()

    def close(self):
        self._hide_to_tray()

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            if self._tray_icon is not None:
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
