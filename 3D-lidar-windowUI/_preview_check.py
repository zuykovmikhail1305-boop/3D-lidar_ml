"""Verify the offscreen render preview contains actual colored points."""

from __future__ import annotations

import sys

import numpy as np
from PIL import Image


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "_r_pure_offscreen.png"
    img = np.array(Image.open(path).convert("RGB"))
    h, w, _ = img.shape

    bg = np.array([22, 22, 29])  # #16181d renderer background
    non_bg = np.abs(img.astype(int) - bg).sum(axis=2) > 30
    saturation = img.max(axis=2).astype(int) - img.min(axis=2).astype(int)
    colorful = saturation > 60

    print(f"size: {w}x{h}")
    print(f"non-background pixels: {int(non_bg.sum())} ({100 * non_bg.mean():.1f}%)")
    print(f"colorful pixels (turbo points): {int(colorful.sum())}")
    print(f"unique colors: {len(np.unique(img.reshape(-1, 3), axis=0))}")

    assert non_bg.mean() > 0.005, "render looks empty (no non-background pixels)"
    assert colorful.sum() > 1000, "no colorful point cloud detected"
    print("PREVIEW CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())