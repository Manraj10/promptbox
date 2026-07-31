"""Promptbox - a plain desktop window over a local ComfyUI install."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import webview

from .comfy import SIZES, ComfyClient, ComfyError, DEFAULT_NEGATIVE

APP_NAME = "Promptbox"
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "Promptbox" / "settings.json"
UI = Path(__file__).parent / "ui" / "index.html"


def load_settings() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def guess_comfy_dir() -> str:
    """Look in the usual places so most people never open Settings."""
    home = Path.home()
    candidates = [
        home / "ComfyUI", home / "AI" / "ComfyUI", home / "Documents" / "ComfyUI",
        home / "Desktop" / "ComfyUI", Path("C:/ComfyUI"),
        home / "ComfyUI_windows_portable" / "ComfyUI",
    ]
    for c in candidates:
        if (c / "main.py").exists():
            return str(c)
    return ""


class Api:
    """Exposed to the page as `pywebview.api`."""

    def __init__(self):
        self.settings = load_settings()
        self.client = ComfyClient(self.settings.get("host", "127.0.0.1:8188"))
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ status

    def status(self):
        up = self.client.is_up()
        comfy_dir = self.settings.get("comfy_dir") or guess_comfy_dir()
        return {
            "up": up,
            "comfy_dir": comfy_dir,
            "host": self.client.host,
            "models": self.client.models() if up else [],
            "samplers": self.client.samplers() if up else [],
            "sizes": list(SIZES.keys()),
            "settings": {
                "model": self.settings.get("model"),
                "steps": self.settings.get("steps", 30),
                "cfg": self.settings.get("cfg", 4.5),
                "sampler": self.settings.get("sampler", "dpmpp_2m"),
                "size": self.settings.get("size", "Portrait 832x1216"),
                "negative": self.settings.get("negative", DEFAULT_NEGATIVE),
                "add_quality": self.settings.get("add_quality", True),
            },
        }

    def start_backend(self, comfy_dir: str):
        try:
            comfy_dir = comfy_dir or guess_comfy_dir()
            if not comfy_dir:
                return {"error": "Set your ComfyUI folder in Settings first."}
            if self.client.is_up():
                return {"ok": True, "already": True}
            self.client.start(comfy_dir)
            if not self.client.wait_until_up(240):
                return {"error": "ComfyUI did not start within 4 minutes."}
            self.settings["comfy_dir"] = comfy_dir
            save_settings(self.settings)
            return {"ok": True}
        except ComfyError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # -------------------------------------------------------------- generation

    def generate(self, opts: dict):
        if not self._lock.acquire(blocking=False):
            return {"error": "Already generating."}
        try:
            if not self.client.is_up():
                return {"error": "ComfyUI isn't running. Press Start backend."}
            model = opts.get("model") or (self.client.models() or [None])[0]
            if not model:
                return {"error": "No checkpoint found in ComfyUI/models/checkpoints."}
            out = self.client.generate(
                model=model,
                prompt=opts.get("prompt", ""),
                negative=opts.get("negative") or None,
                size=opts.get("size", "Portrait 832x1216"),
                seed=opts.get("seed", ""),
                steps=int(opts.get("steps", 30)),
                cfg=float(opts.get("cfg", 4.5)),
                sampler=opts.get("sampler", "dpmpp_2m"),
                add_quality=bool(opts.get("add_quality", True)),
            )
            self.settings.update({
                "model": model, "steps": int(opts.get("steps", 30)),
                "cfg": float(opts.get("cfg", 4.5)),
                "sampler": opts.get("sampler", "dpmpp_2m"),
                "size": opts.get("size", "Portrait 832x1216"),
                "negative": opts.get("negative", DEFAULT_NEGATIVE),
                "add_quality": bool(opts.get("add_quality", True)),
            })
            save_settings(self.settings)
            return out
        except ComfyError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            self._lock.release()

    # ----------------------------------------------------------------- helpers

    def pick_folder(self):
        win = webview.windows[0]
        res = win.create_file_dialog(webview.FOLDER_DIALOG)
        return {"path": res[0] if res else ""}

    def save_setting(self, key: str, value):
        self.settings[key] = value
        save_settings(self.settings)
        if key == "host":
            self.client.host = value
        return {"ok": True}

    def open_output(self):
        d = Path(self.settings.get("comfy_dir") or guess_comfy_dir())
        target = d / "output" / "promptbox"
        target.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(target)                                  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"ok": True}


def main():
    api = Api()
    window = webview.create_window(
        APP_NAME, str(UI), js_api=api,
        width=1180, height=820, min_size=(920, 640),
        background_color="#0a0a0b",
    )

    def cleanup():
        # Only stop ComfyUI if we were the ones who started it.
        if api.client.owns_process:
            api.client.stop()

    window.events.closed += cleanup
    webview.start()


if __name__ == "__main__":
    main()
