from pathlib import Path

from PIL import ImageGrab

from arcmic.ui import ArcMicApp


ROOT = Path(__file__).resolve().parents[1]
app = ArcMicApp(demo=True)


def capture() -> None:
    app.root.update_idletasks()
    # Pillow uses PrintWindow for a window handle, so the system pointer and
    # anything covering the app are not captured.
    preview = ImageGrab.grab(window=app.root.winfo_id())
    output = ROOT / "docs" / "ui-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output, optimize=True)
    app.close()


app.root.after(900, capture)
app.run()
