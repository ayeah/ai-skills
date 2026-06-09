---
name: agnes-image
description: "Generate images via Agnes AI (text-to-image). Supports multiple styles, sizes, and models. For article illustrations, diagrams, charts, banners, and creative visuals."
version: 1.0.0
author: 虾小弟
metadata:
  hermes:
    tags: [agnes, image-generation, text-to-image, illustration, cover, diagram]
    related_skills: [cover-generator, hugo-site, research-and-write]
---

# Agnes Image Generator

Standalone image generation via Agnes AI API. Supports multiple styles, custom sizes, and two image models.

## Prerequisites

- `AGNES_API_KEY` environment variable (get from agnes-ai.com)
- `ffmpeg` (for size conversion and format output)
- Python 3.6+ (stdlib only, no pip packages)

## Quick Start

```bash
# Load API key
source ~/.bashrc  # or export AGNES_API_KEY=sk-xxx

# Basic usage
python3 scripts/agnes_image.py --prompt "a futuristic city skyline at sunset" --output city.png

# With style preset and custom size
python3 scripts/agnes_image.py \
  --prompt "system architecture diagram showing microservices" \
  --style technical \
  --size 1280x720 \
  --output arch_diagram.png

# Generate article illustration with specific model
python3 scripts/agnes_image.py \
  --prompt "abstract data visualization with glowing nodes" \
  --model agnes-image-2.1-flash \
  --style digital-art \
  --size 1024x1024 \
  --output data_viz.png
```

## CLI Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--prompt` | (required) | Image description (English recommended) |
| `--output` | `agnes_output.png` | Output file path (.png/.jpg/.webp) |
| `--size` | `1024x1024` | Target dimensions WxH (auto-scaled from 1024x1024) |
| `--style` | (none) | Style preset: `photorealistic`, `digital-art`, `watercolor`, `anime`, `pixel-art`, `technical`, `flat-design`, `3d-render`, `oil-painting`, `sketch` |
| `--model` | `agnes-image-2.1-flash` | Model: `agnes-image-2.0-flash` or `agnes-image-2.1-flash` |
| `--negative` | (none) | Negative prompt (things to avoid) |
| `--quality` | `5` | JPEG quality 2-31 (lower = better quality, only for .jpg output) |
| `--no-scale` | off | Skip scaling, keep native 1024x1024 output |
| `--verbose` | off | Show API request/response details |

## Built-in Configuration

The script has these values hardcoded — no env vars needed except the API key:

| Setting | Value |
|---------|-------|
| Base URL | `https://apihub.agnes-ai.com/v1` |
| Models | `agnes-image-2.1-flash` (default), `agnes-image-2.0-flash` |
| Native size | `1024x1024` (square only) |

## Style Presets

Style presets append descriptive modifiers to your prompt:

| Style | Description | Appended modifiers |
|-------|-------------|-------------------|
| `photorealistic` | Photo-like realism | `photorealistic, high detail, 8k, natural lighting, DSLR` |
| `digital-art` | Digital illustration | `digital art, vibrant colors, clean lines, modern illustration` |
| `watercolor` | Watercolor painting | `watercolor painting, soft edges, pastel colors, artistic` |
| `anime` | Japanese animation style | `anime style, cel shading, vibrant, detailed character art` |
| `pixel-art` | Retro pixel graphics | `pixel art, 16-bit, retro game style, clean pixels` |
| `technical` | Diagrams & charts | `technical diagram, clean infographic, white background, professional` |
| `flat-design` | Flat/minimal design | `flat design, minimal, vector art, solid colors, no gradients` |
| `3d-render` | 3D rendered scene | `3D render, octane, volumetric lighting, high polygon, cinema` |
| `oil-painting` | Classical oil painting | `oil painting, brush strokes, classical art, rich colors, canvas texture` |
| `sketch` | Pencil/ink sketch | `pencil sketch, hand drawn, line art, black and white, detailed` |

## Common Sizes

| Use Case | Size | Notes |
|----------|------|-------|
| Square (social/avatar) | `1024x1024` | Native, no scaling needed |
| Blog cover (wide) | `1200x630` | Open Graph / Twitter Card |
| WeChat cover | `1024x436` | 公众号封面大图 |
| WeChat thumb | `200x200` | 公众号封面小图 |
| HD banner | `1920x1080` | 16:9 widescreen |
| Article inline | `800x600` | 4:3 standard |

## Programmatic Usage

```python
from agnes_image import generate_image

# Basic
path = generate_image(
    prompt="a cat in a spacesuit on the moon",
    output_path="/tmp/cat.png",
)

# With style and size
path = generate_image(
    prompt="API flow diagram",
    style="technical",
    size="1280x720",
    output_path="/tmp/api_flow.png",
    model="agnes-image-2.1-flash",
)
```

## Pitfalls

1. **Square only**: Agnes API only accepts `1024x1024`. Non-square sizes cause HTTP 500. The script requests 1024x1024 then uses ffmpeg to scale.
2. **Model name dots**: `agnes-image-2.0-flash` (NOT `20`). The `2.1` variant uses `agnes-image-2.1-flash`.
3. **URL response**: API returns image via `url` field, NOT `b64_json`. Use `.get("b64_json")` (truthiness) not `"b64_json" in data_item` (key existence) to avoid NoneType errors.
4. **English prompts**: API works best with English prompts. Chinese prompts may produce unexpected results.
5. **API key**: Must be set as `AGNES_API_KEY` env var. Get/regenerate at agnes-ai.com.
6. **Rate limits**: No documented rate limit but be reasonable. Add delays in batch generation.
7. **ffmpeg required**: Size conversion needs ffmpeg. Available in most environments.
8. **Negative prompts**: Not all models support negative prompts. If ignored, the style modifiers still apply.

## Integration Examples

### With Hugo blog
```bash
python3 scripts/agnes_image.py \
  --prompt "dark theme developer workspace with code on screen" \
  --style digital-art \
  --output /opt/data/ayeah-hugo/static/images/covers/my-post.png
```

### With WeChat article
```bash
# Generate cover (1024x436)
python3 scripts/agnes_image.py \
  --prompt "AI agent workflow automation" \
  --style flat-design \
  --size 1024x436 \
  --output wechat_cover.png

# Generate inline illustration (800x600)
python3 scripts/agnes_image.py \
  --prompt "server architecture with load balancer" \
  --style technical \
  --size 800x600 \
  --output article_illustr.png
```
