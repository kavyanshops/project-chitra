import cv2
import numpy as np


def normalize(a):
    """1-99 percentile stretch to uint8; NaN -> 0."""
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [1, 99]) if v.size else (0, 1)
    out = np.clip((np.nan_to_num(a, nan=lo) - lo) / max(hi - lo, 1e-9), 0, 1)
    return (out * 255).astype(np.uint8)


def clahe(u8):
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(u8)


def shadow_mask(u8, thresh=10):
    return u8 <= thresh


def saturation_mask(u8, thresh=250):
    return u8 >= thresh


def resample(a, factor):
    """Scale an image by `factor` (<1 shrinks). INTER_AREA for downsampling avoids aliasing."""
    if factor == 1:
        return a
    h, w = a.shape[:2]
    interp = cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC
    return cv2.resize(a, (max(1, round(w * factor)), max(1, round(h * factor))), interpolation=interp)


def iirs_proxy(cube):
    """IIRS (bands, H, W) -> PCA-1 image. Drops bands with non-finite pixels or near-zero variance."""
    b = cube.reshape(cube.shape[0], -1).astype(np.float64)
    good = np.isfinite(b).all(1) & (b.std(1) > 1e-6 * np.abs(b).mean())
    x = b[good] - b[good].mean(1, keepdims=True)
    x /= x.std(1, keepdims=True)
    u, _, _ = np.linalg.svd(x @ x.T)
    return (u[:, 0] @ x).reshape(cube.shape[1:]).astype(np.float32)
