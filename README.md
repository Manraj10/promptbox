# Promptbox

A plain desktop app for local image generation. Type a prompt, get a picture.

Promptbox is a small native window over a [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
install. ComfyUI is powerful and its node graph is a wall — if you just want an image
from a sentence, this is that.

- **Native window**, not a browser tab
- **Fully local** — no accounts, no API keys, nothing leaves your machine
- **Starts the backend for you** — point it at your ComfyUI folder once
- **Sane defaults** — the realism prompt-shaping is built in
- **One dependency** — `pywebview`, plus Python's standard library

---

## Why the defaults matter

The most common mistake with SDXL is stuffing the prompt with `8k, masterpiece,
photorealistic, ultra detailed`. Those terms pull the model *toward* glossy CGI —
they are the reason so much local output has plastic skin and dead eyes.

Promptbox does the opposite by default. It appends a short realism suffix and ships a
negative prompt that bans the glossy tells:

```
airbrushed, plastic skin, poreless, cgi, 3d render, doll, waxy, uncanny …
```

So write plainly — *"a golden retriever puppy asleep on a windowsill"* — and let the
defaults do the work. Both are editable under **Advanced** if you disagree.

---

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+
- An existing [ComfyUI](https://github.com/comfyanonymous/ComfyUI) install with at
  least one checkpoint in `models/checkpoints/`
- A GPU with ~6GB VRAM for SDXL models (CPU works, slowly)

Promptbox deliberately does **not** bundle ComfyUI or ship model weights.

## Install

```bash
git clone https://github.com/YOURNAME/promptbox
cd promptbox
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m promptbox
```

On first run it looks for ComfyUI in the usual places (`~/ComfyUI`, `~/AI/ComfyUI`,
`~/Documents/ComfyUI`, `C:\ComfyUI`, and the Windows portable layout). If it can't
find yours, set the folder under **Advanced → ComfyUI folder**, then press
**Start backend**.

## Use

| | |
|---|---|
| Generate | `Ctrl`/`Cmd` + `Enter`, or the button |
| Size | portrait, square, landscape, tall |
| Seed | blank for random; reuse a number to reproduce an image exactly |
| Advanced | steps, CFG, sampler, negative prompt, model |
| Output | button in the header opens the folder |

Images are written to `ComfyUI/output/promptbox/`.

## How it works

```
┌─────────────┐   pywebview JS bridge   ┌──────────────┐   HTTP    ┌─────────┐
│  index.html │ ──────────────────────► │  Api (Python)│ ────────► │ ComfyUI │
└─────────────┘                         └──────────────┘           └─────────┘
```

`comfy.py` builds a fixed seven-node graph and posts it to ComfyUI's `/prompt`
endpoint, polls `/history/{id}`, and returns the image as a data URI. No node editing,
no workflow JSON to manage.

If Promptbox started ComfyUI, it shuts it down on exit. If ComfyUI was already
running, it's left alone.

## Roadmap

- [ ] Batch generation (n images per prompt)
- [ ] Image-to-image and inpainting
- [ ] Character consistency via IPAdapter reference image
- [ ] Packaged `.exe` / `.app` so Python isn't a prerequisite
- [ ] Prompt history that survives restarts

Issues and PRs welcome.

## License

MIT — see [LICENSE](LICENSE).
