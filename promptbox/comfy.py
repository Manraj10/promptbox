"""Thin client for a local ComfyUI instance.

Promptbox does not reimplement diffusion - it drives ComfyUI's HTTP API and hides
the node graph behind a single prompt box.
"""
from __future__ import annotations

import base64
import json
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_HOST = "127.0.0.1:8188"

# Appended to every prompt. Photo-realism is won by *removing* the glossy tells, not
# by adding "8k masterpiece" - those push SDXL toward plastic CGI faces.
QUALITY_SUFFIX = "natural light, shallow depth of field, visible skin texture"
DEFAULT_NEGATIVE = (
    "airbrushed, plastic skin, poreless, cgi, 3d render, illustration, painting, "
    "doll, waxy, uncanny, deformed face, asymmetric eyes, extra fingers, "
    "deformed hands, mutated hands, watermark, text, letters, logo, signature"
)

SIZES = {
    "Portrait 832x1216": (832, 1216),
    "Square 1024x1024": (1024, 1024),
    "Landscape 1216x832": (1216, 832),
    "Tall 768x1344": (768, 1344),
}


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, host: str = DEFAULT_HOST):
        self.host = host
        self._proc: subprocess.Popen | None = None

    # ---------------------------------------------------------------- lifecycle

    @property
    def base(self) -> str:
        return f"http://{self.host}"

    def is_up(self, timeout: float = 2.0) -> bool:
        try:
            urllib.request.urlopen(f"{self.base}/system_stats", timeout=timeout)
            return True
        except Exception:
            return False

    def start(self, comfy_dir: str) -> None:
        """Launch ComfyUI from an install directory, preferring its own venv."""
        root = Path(comfy_dir)
        main = root / "main.py"
        if not main.exists():
            raise ComfyError(f"main.py not found in {root}")

        venv_py = root / ".venv" / "Scripts" / "python.exe"
        alt_py = root / "venv" / "Scripts" / "python.exe"
        python = str(next((p for p in (venv_py, alt_py) if p.exists()), sys.executable))

        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW  # don't flash a console
        port = self.host.rsplit(":", 1)[-1]
        self._proc = subprocess.Popen(
            [python, str(main), "--port", port],
            cwd=str(root), creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def wait_until_up(self, timeout: float = 180.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_up(timeout=2.0):
                return True
            if self._proc and self._proc.poll() is not None:
                raise ComfyError("ComfyUI exited during startup")
            time.sleep(2)
        return False

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    @property
    def owns_process(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # -------------------------------------------------------------------- calls

    def _get(self, path: str, timeout: float = 15.0):
        with urllib.request.urlopen(f"{self.base}{path}", timeout=timeout) as r:
            return json.loads(r.read())

    def models(self) -> list[str]:
        info = self._get("/object_info/CheckpointLoaderSimple")
        opts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        return list(opts) if isinstance(opts, list) else []

    def samplers(self) -> list[str]:
        info = self._get("/object_info/KSampler")
        opts = info["KSampler"]["input"]["required"]["sampler_name"][0]
        return list(opts) if isinstance(opts, list) else []

    # ------------------------------------------------------------------ upload

    def upload_image(self, data_url: str, name: str) -> str:
        """Push a data: URL into ComfyUI's input folder. Returns the stored name."""
        raw = base64.b64decode(data_url.split(",", 1)[-1])
        boundary = "----promptbox" + str(random.randint(10**9, 10**10))
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n", raw, b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
            f"--{boundary}--\r\n".encode(),
        ])
        req = urllib.request.Request(
            f"{self.base}/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            res = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except urllib.error.HTTPError as e:
            raise ComfyError(f"Upload failed: {e.read()[:200].decode()}")
        sub = res.get("subfolder") or ""
        return f"{sub}/{res['name']}" if sub else res["name"]

    # ---------------------------------------------------------------- workflow

    @staticmethod
    def _edit_graph(model, prompt, negative, image_name, seed, steps, cfg,
                    sampler, denoise):
        """img2img: encode the source image and partially re-noise it.

        denoise is the whole story. Low values nudge, high values reinvent:
          0.25-0.40  recolour, lighting, small texture changes
          0.45-0.60  clothing, background, style; subject survives
          0.70+      effectively a new image loosely guided by the old one
        """
        return {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": negative, "clip": ["1", 1]}},
            "4": {"class_type": "LoadImage",
                  "inputs": {"image": image_name, "upload": "image"}},
            "5": {"class_type": "VAEEncode",
                  "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
            "6": {"class_type": "KSampler",
                  "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                             "sampler_name": sampler, "scheduler": "karras",
                             "denoise": denoise, "model": ["1", 0],
                             "positive": ["2", 0], "negative": ["3", 0],
                             "latent_image": ["5", 0]}},
            "7": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
            "8": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "promptbox/edit", "images": ["7", 0]}},
        }

    @staticmethod
    def _graph(model, prompt, negative, w, h, seed, steps, cfg, sampler):
        return {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": negative, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": w, "height": h, "batch_size": 1}},
            "5": {"class_type": "KSampler",
                  "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                             "sampler_name": sampler, "scheduler": "karras",
                             "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0],
                             "negative": ["3", 0], "latent_image": ["4", 0]}},
            "6": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "promptbox/img", "images": ["6", 0]}},
        }

    def generate(self, *, model, prompt, negative=None, size="Portrait 832x1216",
                 seed=None, steps=30, cfg=4.5, sampler="dpmpp_2m",
                 add_quality=True, source_image=None, denoise=0.55,
                 on_progress=None):
        if not prompt.strip():
            raise ComfyError("Prompt is empty")
        w, h = SIZES.get(size, SIZES["Portrait 832x1216"])
        seed = int(seed) if str(seed).strip().isdigit() else random.randint(1, 2**31 - 1)
        text = f"{prompt.strip()}, {QUALITY_SUFFIX}" if add_quality else prompt.strip()

        if source_image:
            name = self.upload_image(source_image, f"pb_src_{seed}.png")
            graph = self._edit_graph(model, text, negative or DEFAULT_NEGATIVE,
                                     name, seed, steps, cfg, sampler, float(denoise))
        else:
            graph = self._graph(model, text, negative or DEFAULT_NEGATIVE,
                                w, h, seed, steps, cfg, sampler)

        payload = json.dumps({"prompt": graph}).encode()
        req = urllib.request.Request(f"{self.base}/prompt", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            pid = json.loads(urllib.request.urlopen(req, timeout=30).read())["prompt_id"]
        except urllib.error.HTTPError as e:
            raise ComfyError(f"ComfyUI rejected the request: {e.read()[:300].decode()}")

        deadline = time.time() + 900
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                hist = self._get(f"/history/{pid}")
            except Exception:
                continue
            entry = hist.get(pid)
            if not entry:
                if on_progress:
                    on_progress()
                continue
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise ComfyError(self._explain(status))
            if status.get("completed"):
                for out in entry.get("outputs", {}).values():
                    for img in out.get("images", []):
                        return {"image": self._fetch_b64(img), "seed": seed,
                                "width": w, "height": h,
                                "filename": img["filename"]}
                raise ComfyError("Run finished but produced no image")
        raise ComfyError("Timed out waiting for the image")

    @staticmethod
    def _explain(status) -> str:
        for kind, payload in status.get("messages", []):
            if kind == "execution_error":
                msg = str(payload.get("exception_message", ""))
                if "out of memory" in msg.lower():
                    return ("Out of GPU memory. Try a smaller size, or close other "
                            "apps using the GPU.")
                return msg[:300] or "Generation failed"
        return "Generation failed"

    def _fetch_b64(self, img) -> str:
        q = urllib.parse.urlencode({"filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output")})
        with urllib.request.urlopen(f"{self.base}/view?{q}", timeout=60) as r:
            return "data:image/png;base64," + base64.b64encode(r.read()).decode()
