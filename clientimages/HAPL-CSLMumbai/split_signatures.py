#!/usr/bin/env python3
"""
Script to split composite signature images into individual signature PNG files
with a canvas size of 827 x 392 pixels (standard 1/3 A4 @ 300 DPI block).
"""

import os
import sys
import glob
from PIL import Image
import numpy as np


def find_signature_images(directory="."):
    """Find PNG images with 'signature' in the filename, ignoring already-split files."""
    candidates = []
    for f in os.listdir(directory):
        f_lower = f.lower()
        if f_lower.endswith(".png") and "signature" in f_lower:
            # Skip already split files like *_1.png, *_2.png
            name_no_ext = os.path.splitext(f)[0]
            parts = name_no_ext.split("_")
            if parts[-1].isdigit():
                continue
            candidates.append(os.path.join(directory, f))
    return sorted(candidates)


def split_signatures(
    image_path,
    target_size=(827, 392),
    output_dir=".",
    create_webp=True,
    max_w_ratio=0.72,
    max_h_ratio=0.78,
):
    """
    Detect individual signatures in a composite signature image and save each
    onto an individual canvas of target_size (default 827 x 392 pixels).
    """
    im = Image.open(image_path)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    print(f"Processing '{image_path}' (size: {im.size}, mode: {im.mode})...")

    # Determine ink mask
    if im.mode == "RGBA":
        a = im.split()[-1]
        if a.getextrema() != (255, 255):
            # Alpha-based transparency
            alpha_arr = np.array(a)
            ink = alpha_arr > 20
        else:
            gray = np.array(im.convert("L"))
            ink = gray < 240
    else:
        gray = np.array(im.convert("L"))
        ink = gray < 240

    col_ink = np.sum(ink, axis=0)

    # Minimum gap between separate signatures (at least 2.5% of image width or 15px)
    min_gap = max(15, int(im.width * 0.025))

    # Detect contiguous ink columns along the horizontal axis
    runs = []
    in_run = False
    start = 0
    for x in range(im.width):
        if col_ink[x] > 0 and not in_run:
            in_run = True
            start = x
        elif col_ink[x] == 0 and in_run:
            in_run = False
            runs.append((start, x - 1))
    if in_run:
        runs.append((start, im.width - 1))

    # Merge runs separated by less than min_gap
    merged = []
    for r in runs:
        if not merged:
            merged.append(r)
        else:
            prev = merged[-1]
            if r[0] - prev[1] < min_gap:
                merged[-1] = (prev[0], r[1])
            else:
                merged.append(r)

    print(f"Found {len(merged)} signatures in '{image_path}':")

    # Crop tight bounding boxes for each signature
    crops = []
    for i, (x0, x1) in enumerate(merged):
        sub_ink = ink[:, x0 : x1 + 1]
        rows = np.where(np.sum(sub_ink, axis=1) > 0)[0]
        y0, y1 = rows[0], rows[-1]
        crop = im.crop((x0, y0, x1 + 1, y1 + 1))
        crops.append(crop)
        print(f"  [{i + 1}] Bounding box: X=[{x0}, {x1}] (w={crop.width}), Y=[{y0}, {y1}] (h={crop.height})")

    # Determine uniform scale factor across all signatures in this image
    max_w = max(c.width for c in crops)
    max_h = max(c.height for c in crops)

    target_w, target_h = target_size
    max_allowed_w = int(target_w * max_w_ratio)
    max_allowed_h = int(target_h * max_h_ratio)

    scale = min(max_allowed_w / max_w, max_allowed_h / max_h)
    print(f"  Applied uniform scale factor: {scale:.4f}")

    created_files = []
    for i, crop in enumerate(crops):
        nw = int(round(crop.width * scale))
        nh = int(round(crop.height * scale))
        crop_scaled = crop.resize((nw, nh), Image.Resampling.LANCZOS)

        out_mode = "RGBA" if im.mode == "RGBA" else "RGB"
        bg_color = (255, 255, 255, 255) if out_mode == "RGBA" else (255, 255, 255)
        canvas = Image.new(out_mode, target_size, bg_color)

        # Center horizontally and vertically on canvas
        x_pos = (target_w - nw) // 2
        y_pos = (target_h - nh) // 2

        if crop_scaled.mode == "RGBA":
            canvas.paste(crop_scaled, (x_pos, y_pos), crop_scaled)
        else:
            canvas.paste(crop_scaled, (x_pos, y_pos))

        # Replace 'signature' with 'doctor' in base name (e.g. cslmumbai_signature -> cslmumbai_doctor)
        if "signature" in base_name.lower():
            doctor_base = base_name.replace("signature", "doctor").replace("Signature", "doctor")
        else:
            doctor_base = f"{base_name}_doctor"

        out_png = os.path.join(output_dir, f"{doctor_base}_{i + 1}.png")
        canvas.save(out_png)
        created_files.append(out_png)

        if create_webp:
            out_webp = os.path.join(output_dir, f"{doctor_base}_{i + 1}.webp")
            canvas.save(out_webp)
            created_files.append(out_webp)

        print(f"  -> Generated: {out_png} ({target_w}x{target_h})")

    return created_files


def main():
    target_w = 827
    target_h = 392

    if len(sys.argv) > 1:
        images = [sys.argv[1]]
        if len(sys.argv) >= 4:
            target_w = int(sys.argv[2])
            target_h = int(sys.argv[3])
    else:
        images = find_signature_images(".")

    if not images:
        print("No signature PNG image found in the current directory.")
        sys.exit(1)

    for img in images:
        split_signatures(img, target_size=(target_w, target_h))


if __name__ == "__main__":
    main()
