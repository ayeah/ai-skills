#!/usr/bin/env python3
"""
Agnes Image Generator — Standalone text-to-image via Agnes AI API.

Built-in config:
  Base URL:  https://apihub.agnes-ai.com/v1
  Models:    agnes-image-2.1-flash (default), agnes-image-2.0-flash

Required env var:
  AGNES_API_KEY — API key from agnes-ai.com

Usage:
  python3 agnes_image.py --prompt "a futuristic city" --output city.png
  python3 agnes_image.py --prompt "flow diagram" --style technical --size 1280x720 --output flow.png
  python3 agnes_image.py --prompt "portrait" --style photorealistic --model agnes-image-2.0-flash --output portrait.jpg

Programmatic:
  from agnes_image import generate_image
  path = generate_image(prompt="...", output_path="out.png", style="digital-art", size="800x600")
"""

import os
import sys
import json
import base64
import argparse
import subprocess
import tempfile
import urllib.request
import urllib.parse
import urllib.error


# ═══════════════════════════════════════════════════
# Built-in Configuration (no env vars needed except API key)
# ═══════════════════════════════════════════════════

AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_MODELS = {
    "agnes-image-2.1-flash": "Latest model, best quality (default)",
    "agnes-image-2.0-flash": "Stable model, good quality",
}
DEFAULT_MODEL = "agnes-image-2.1-flash"
NATIVE_SIZE = "1024x1024"  # Agnes only supports square


# ═══════════════════════════════════════════════════
# Style Presets
# ═══════════════════════════════════════════════════

STYLE_PRESETS = {
    "photorealistic": "photorealistic, high detail, 8k, natural lighting, DSLR photography",
    "digital-art": "digital art, vibrant colors, clean lines, modern illustration, trending on artstation",
    "watercolor": "watercolor painting, soft edges, pastel colors, artistic, flowing pigments",
    "anime": "anime style, cel shading, vibrant colors, detailed character art, studio ghibli inspired",
    "pixel-art": "pixel art, 16-bit retro game style, clean pixels, nostalgic, SNES era",
    "technical": "technical diagram, clean infographic, white background, professional, clear labels, minimal",
    "flat-design": "flat design, minimal, vector art, solid colors, no gradients, modern UI illustration",
    "3d-render": "3D render, octane render, volumetric lighting, high polygon, cinema 4D, photorealistic 3D",
    "oil-painting": "oil painting, visible brush strokes, classical art, rich warm colors, canvas texture",
    "sketch": "pencil sketch, hand drawn, fine line art, black and white, detailed crosshatching",
}


# ═══════════════════════════════════════════════════
# Core API Call
# ═══════════════════════════════════════════════════

def _call_agnes_api(prompt, model=None, api_key=None, verbose=False):
    """Call Agnes AI image generation API. Returns raw image bytes."""
    if not api_key:
        api_key = os.environ.get("AGNES_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "AGNES_API_KEY not set. Export it or pass via --api-key.\n"
            "Get your key at: https://agnes-ai.com"
        )

    if not model:
        model = DEFAULT_MODEL

    if model not in AGNES_MODELS:
        available = ", ".join(AGNES_MODELS.keys())
        raise RuntimeError(f"Unknown model '{model}'. Available: {available}")

    url = AGNES_BASE_URL.rstrip("/") + "/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": NATIVE_SIZE,  # Always square — Agnes rejects non-square
    }

    if verbose:
        print(f"  [API] POST {url}")
        print(f"  [API] Model: {model}")
        print(f"  [API] Prompt: {prompt[:80]}...")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Agnes API HTTP {e.code}: {body}")

    if "error" in result:
        raise RuntimeError(f"Agnes API error: {result['error']}")

    items = result.get("data", [])
    if not items:
        raise RuntimeError("Agnes API returned empty data")

    item = items[0]

    # Agnes returns image via URL, not b64_json (b64_json is null)
    # Use .get() truthiness check — NOT "b64_json" in item (key exists but is None)
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    elif item.get("url"):
        img_url = item["url"]
        if verbose:
            print(f"  [API] Image URL: {img_url[:80]}...")
        img_req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; HermesAgent/1.0)",
        })
        with urllib.request.urlopen(img_req, timeout=180) as img_resp:
            return img_resp.read()
    else:
        raise RuntimeError(f"Unknown response format: {json.dumps(item)[:200]}")


# ═══════════════════════════════════════════════════
# Post-processing
# ═══════════════════════════════════════════════════

def _has_ffmpeg():
    """Check if ffmpeg is available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _save_and_scale(image_bytes, output_path, size="1024x1024", quality=5, no_scale=False, verbose=False):
    """Save image bytes to file, optionally scale to target size."""
    target_w, target_h = [int(x) for x in size.split("x")]
    native_w, native_h = [int(x) for x in NATIVE_SIZE.split("x")]

    # Determine output format from extension
    ext = os.path.splitext(output_path)[1].lower()

    # Write raw image to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        needs_scale = (not no_scale) and (target_w != native_w or target_h != native_h)

        if needs_scale and _has_ffmpeg():
            if verbose:
                print(f"  [Scale] {native_w}x{native_h} → {target_w}x{target_h}")

            if ext == ".jpg" or ext == ".jpeg":
                # Scale + convert to JPEG
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_path,
                    "-vf", f"scale={target_w}:{target_h}",
                    "-q:v", str(quality),
                    output_path,
                ], capture_output=True, check=True)
            elif ext == ".webp":
                # Scale + convert to WebP
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_path,
                    "-vf", f"scale={target_w}:{target_h}",
                    "-c:v", "libwebp", "-quality", "90",
                    output_path,
                ], capture_output=True, check=True)
            else:
                # Scale + keep as PNG (default)
                if not output_path.lower().endswith(".png"):
                    output_path = output_path + ".png"
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_path,
                    "-vf", f"scale={target_w}:{target_h}",
                    output_path,
                ], capture_output=True, check=True)
        else:
            # No scaling needed or ffmpeg unavailable
            if not needs_scale:
                if verbose:
                    print("  [Scale] Skipped (native size or --no-scale)")
            else:
                print("  [WARN] ffmpeg not found, skipping scale. Output is 1024x1024.")

            if ext in (".jpg", ".jpeg") and _has_ffmpeg():
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_path,
                    "-q:v", str(quality),
                    output_path,
                ], capture_output=True, check=True)
            elif ext == ".webp" and _has_ffmpeg():
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp_path,
                    "-c:v", "libwebp", "-quality", "90",
                    output_path,
                ], capture_output=True, check=True)
            else:
                # Just copy the raw file
                if not output_path.lower().endswith(".png"):
                    output_path = output_path + ".png"
                os.rename(tmp_path, output_path)
                return output_path
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return output_path


# ═══════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════

def generate_image(prompt, output_path="agnes_output.png", style=None,
                   size="1024x1024", model=None, negative_prompt=None,
                   quality=5, no_scale=False, verbose=False, api_key=None):
    """
    Generate an image via Agnes AI.

    Args:
        prompt:          Image description (English recommended)
        output_path:     Output file path (.png/.jpg/.webp)
        style:           Style preset name (see STYLE_PRESETS)
        size:            Target dimensions "WxH" (default: 1024x1024)
        model:           Model name (default: agnes-image-2.1-flash)
        negative_prompt: Things to avoid in the image
        quality:         JPEG quality 2-31 (lower = better)
        no_scale:        Skip scaling, keep native 1024x1024
        verbose:         Print API details
        api_key:         Override AGNES_API_KEY env var

    Returns:
        str: Absolute path to the generated image file
    """
    # Build final prompt with style
    final_prompt = prompt
    if style:
        style_lower = style.lower().replace(" ", "-").replace("_", "-")
        if style_lower in STYLE_PRESETS:
            final_prompt = f"{prompt}, {STYLE_PRESETS[style_lower]}"
        else:
            available = ", ".join(STYLE_PRESETS.keys())
            raise ValueError(f"Unknown style '{style}'. Available: {available}")

    if negative_prompt:
        final_prompt = f"{final_prompt}. Avoid: {negative_prompt}"

    # Call API
    print(f"[Agnes] Generating: {final_prompt[:80]}")
    image_bytes = _call_agnes_api(final_prompt, model=model, api_key=api_key, verbose=verbose)
    print(f"[Agnes] Received {len(image_bytes):,} bytes ({len(image_bytes)//1024} KB)")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Save and scale
    final_path = _save_and_scale(
        image_bytes, output_path,
        size=size, quality=quality, no_scale=no_scale, verbose=verbose,
    )

    abs_path = os.path.abspath(final_path)
    file_size = os.path.getsize(abs_path)
    print(f"[Agnes] Saved: {abs_path} ({file_size:,} bytes, {file_size//1024} KB)")
    return abs_path


# ═══════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Agnes AI Image Generator — text-to-image with style presets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --prompt "a cat on the moon" --output cat.png
  %(prog)s --prompt "server architecture" --style technical --size 1280x720
  %(prog)s --prompt "portrait" --style photorealistic --model agnes-image-2.0-flash
  %(prog)s --prompt "logo concept" --style flat-design --negative "text, words, letters"

Styles: {styles}
Models: {models}
        """.format(
            styles=", ".join(STYLE_PRESETS.keys()),
            models=", ".join(AGNES_MODELS.keys()),
        ),
    )
    parser.add_argument("--prompt", required=True, help="Image description (English recommended)")
    parser.add_argument("--output", default="agnes_output.png", help="Output file path (.png/.jpg/.webp)")
    parser.add_argument("--size", default="1024x1024", help="Target size WxH (default: 1024x1024)")
    parser.add_argument("--style", choices=list(STYLE_PRESETS.keys()),
                        help="Style preset to apply")
    parser.add_argument("--model", choices=list(AGNES_MODELS.keys()),
                        default=DEFAULT_MODEL, help=f"Model (default: {DEFAULT_MODEL})")
    parser.add_argument("--negative", help="Negative prompt (things to avoid)")
    parser.add_argument("--quality", type=int, default=5, help="JPEG quality 2-31 (default: 5)")
    parser.add_argument("--no-scale", action="store_true", help="Keep native 1024x1024, skip scaling")
    parser.add_argument("--verbose", action="store_true", help="Show API request/response details")
    parser.add_argument("--api-key", help="Override AGNES_API_KEY env var")

    args = parser.parse_args()

    try:
        path = generate_image(
            prompt=args.prompt,
            output_path=args.output,
            style=args.style,
            size=args.size,
            model=args.model,
            negative_prompt=args.negative,
            quality=args.quality,
            no_scale=args.no_scale,
            verbose=args.verbose,
            api_key=args.api_key,
        )
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
