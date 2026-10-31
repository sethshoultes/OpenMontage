"""Re-colour a cool-palette still (blue-black ground, grey art) into the warm palette (brown-black ground, cream art), orange kept.

Each pixel is split into two amounts, a neutral level t (0 = cool ground, 1 = white) and an orange amount o, by least squares on
the two axes (ground->white, ground->orange). Anything off those two axes (compression noise) is dropped, so flat areas stay flat
and edges stay pin-sharp. The neutral level is then re-mapped piecewise: ground -> warm ground, the still's own grey -> cream,
white -> warm white; the orange amount goes to the warm orange.

Usage: warm_regrade.py <in.png> <out.png>
"""
import sys

import numpy as np
from PIL import Image

WARM_GROUND, CREAM, WARM_WHITE, ORANGE = (np.array(c, dtype=np.float64) for c in ((23, 17, 12), (241, 230, 214), (255, 248, 232), (255, 108, 30)))


def main(src, dst):
    a = np.asarray(Image.open(src).convert("RGB")).astype(np.float64)
    h, w, _ = a.shape
    flat = a.reshape(-1, 3)
    ground = np.median(np.concatenate([a[:20, :20].reshape(-1, 3), a[-20:, -20:].reshape(-1, 3)]), axis=0)
    mx, mn = flat.max(axis=1), flat.min(axis=1)
    neutral = (mx - mn < 14) & (mx > 110)
    grey = np.median(flat[neutral], axis=0) if neutral.sum() > 2000 else np.array([165.0, 165.0, 165.0])
    orange_px = (flat[:, 0] > 200) & (flat[:, 1] > 70) & (flat[:, 1] < 150) & (flat[:, 2] < 90)
    orange = np.median(flat[orange_px], axis=0) if orange_px.sum() > 500 else np.array([255.0, 115.0, 10.0])
    white = np.array([255.0, 255.0, 255.0])
    basis = np.stack([white - ground, orange - ground], axis=1)            # 3x2
    coef = np.linalg.pinv(basis) @ (flat - ground).T                       # 2xN: (t, o)
    t, o = coef[0], np.clip(coef[1], 0, 1.2)
    tg = float((np.linalg.pinv(basis) @ (grey - ground))[0])
    tt = np.clip(t, 0, 1.05)[:, None]
    low = WARM_GROUND + (tt / tg) * (CREAM - WARM_GROUND)
    high = CREAM + ((tt - tg) / (1 - tg)) * (WARM_WHITE - CREAM)
    out = np.where(tt <= tg, low, high) + o[:, None] * (ORANGE - WARM_GROUND)
    out = np.clip(out, 0, 255).astype(np.uint8).reshape(h, w, 3)
    Image.fromarray(out).save(dst)
    print("ok", dst, "ground", ground.astype(int), "grey", grey.astype(int), "tg", round(tg, 3), "orange", orange.astype(int))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
