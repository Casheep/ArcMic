from __future__ import annotations

import argparse
import ctypes
import traceback

from .config import local_app_dir
from .engine import install_or_repair, restore_system, set_diagnostic_trace


_instance_mutex = None


def _acquire_single_instance() -> bool:
    """Keep the normal app single-instance without affecting preview builds."""
    global _instance_mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\ArcMic.Application")
    if not mutex:
        return True
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        return False
    _instance_mutex = mutex
    return True


def _enable_dpi_awareness() -> None:
    """Render Tk directly at the monitor DPI instead of bitmap stretching it."""
    try:
        set_context = ctypes.windll.user32.SetProcessDpiAwarenessContext
        set_context.argtypes = [ctypes.c_void_p]
        if set_context(ctypes.c_void_p(-4)):  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except (AttributeError, OSError):
        pass


def _write_setup_error() -> None:
    try:
        path = local_app_dir() / "setup-error.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ArcMic", add_help=True)
    parser.add_argument("--setup", metavar="DEVICE_GUID", help="install or repair the system audio binding")
    parser.add_argument("--install-mode", choices=("sfx", "lfx"), default="sfx", help=argparse.SUPPRESS)
    parser.add_argument("--restore", action="store_true", help="restore audio endpoint settings")
    parser.add_argument("--diagnostic-trace", choices=("on", "off"), help=argparse.SUPPRESS)
    parser.add_argument("--demo", action="store_true", help="show the interface without changing the system")
    args = parser.parse_args(argv)

    try:
        if args.setup is not None:
            return install_or_repair(args.setup, args.install_mode)
        if args.restore:
            return restore_system()
        if args.diagnostic_trace:
            return set_diagnostic_trace(args.diagnostic_trace == "on")
        if not args.demo and not _acquire_single_instance():
            return 0
        _enable_dpi_awareness()
        from .ui import ArcMicApp

        ArcMicApp(demo=args.demo).run()
        return 0
    except Exception:
        _write_setup_error()
        return 1
