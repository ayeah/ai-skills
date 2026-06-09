# Agnes Image API Reference

## API Endpoint

| Setting | Value |
|---------|-------|
| Base URL | `https://apihub.agnes-ai.com/v1` |
| Image endpoint | `POST /v1/images/generations` |
| Model list | `GET /v1/models` |
| Auth | `Authorization: Bearer ***
| Content-Type | `application/json` |

## Available Models (as of 2026-06)

| Model ID | Description |
|----------|-------------|
| `agnes-image-2.1-flash` | Latest model, best quality (recommended) |
| `agnes-image-2.0-flash` | Stable model, good quality |

Other models available on the platform (not image):
- `agnes-1.5-flash` — text model
- `agnes-2.0-flash` — text model
- `agnes-video-v2.0` — video generation

## Request Format

```json
{
  "model": "agnes-image-2.1-flash",
  "prompt": "a futuristic city skyline",
  "n": 1,
  "size": "1024x1024"
}
```

**Critical**: `size` must be `1024x1024` (square). Any non-square value causes HTTP 500.

## Response Format

```json
{
  "data": [
    {
      "b64_json": null,
      "revised_prompt": null,
      "url": "https://platform-outputs.agnes-ai.space/images/text-to-image/..."
    }
  ]
}
```

**Critical**: Image is returned via `url` field, NOT `b64_json`. The `b64_json` key exists but is `null`. Always use truthiness check:

```python
# CORRECT
if item.get("b64_json"):
    img = base64.b64decode(item["b64_json"])
elif item.get("url"):
    img = download(item["url"])

# WRONG — key exists but value is None → TypeError
if "b64_json" in item:
    img = base64.b64decode(item["b64_json"])  # NoneType error!
```

## Common Errors

| Code | Message | Cause | Fix |
|------|---------|-------|-----|
| 401 | `invalid or expired token` (000501) | Key expired or invalid | Regenerate at agnes-ai.com |
| 500 | Internal Server Error | Non-square `size` param | Use `1024x1024` |
| 503 | `model_not_found` | Wrong model name | Check `/v1/models` |

## Size Handling Strategy

Since Agnes only supports 1024×1024 square output:

1. **Request 1024×1024** from the API (always)
2. **Scale with ffmpeg** to the target aspect ratio
3. ffmpeg `scale=W:H` may distort; for better results use `scale=W:H:force_original_aspect_ratio=decrease` + `pad`

### ffmpeg scaling examples

```bash
# Simple scale (may stretch)
ffmpeg -y -i input.png -vf scale=1280:720 output.png

# Aspect-fit with padding (preserves proportions)
ffmpeg -y -i input.png -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" output.png

# Convert to JPEG with quality
ffmpeg -y -i input.png -vf scale=1024:436 -q:v 5 output.jpg
```

## Tips for Better Results

1. **Write prompts in English** — the model understands English much better than Chinese
2. **Be specific** — "a red sports car driving on a mountain road at sunset" > "car"
3. **Use style presets** — they add proven modifiers that improve output quality
4. **Negative prompts** — add things to avoid: "text, watermark, low quality, blurry"
5. **Iterate** — regenerate with slightly different prompts if the first result isn't right
