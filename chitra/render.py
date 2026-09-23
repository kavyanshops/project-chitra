"""Hapke-family shading of a DEM (Lommel-Seeliger disk x Henyey-Greenstein phase) with cast shadows.

Conventions: north-up raster (row increases southward); Sun azimuth clockwise from north; nadir view.
"""
import cv2
import numpy as np

XI = -0.3  # HG asymmetry, backscattering regolith


def _sun_vec(az, el):
    az, el = np.radians(az), np.radians(el)
    return np.array([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)])  # (east, north, up)


def cast_shadow(dem, px, az, el, max_steps=400):
    """True where terrain toward the Sun rises above the Sun's elevation (horizon test)."""
    z = np.nan_to_num(dem, nan=np.nanmean(dem)).astype(np.float32)
    tan_el = np.tan(np.radians(el))
    steps = int(min(max_steps, np.ceil((z.max() - z.min()) / (px * tan_el)) + 1))
    rows, cols = np.indices(z.shape, dtype=np.float32)
    dc, dr = float(np.sin(np.radians(az))), float(-np.cos(np.radians(az)))  # one pixel toward the Sun
    shadow = np.zeros(z.shape, bool)
    for k in range(1, steps + 1):
        zk = cv2.remap(z, cols + k * dc, rows + k * dr, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        shadow |= (zk - z) > k * px * tan_el
    return shadow


def shade(dem, px, az, el, shadows=True, xi=XI):
    """Reflectance image in [0, 1]-ish; NaN where the DEM is NaN."""
    gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmean(dem)), px)
    n = np.stack([-gx, gy, np.ones_like(gx)])  # dz/dnorth = -dz/drow
    n /= np.linalg.norm(n, axis=0)
    s = _sun_vec(az, el)
    mu0 = np.clip(np.tensordot(s, n, 1), 0, None)
    mu = n[2]
    cos_g = s[2]  # phase angle between Sun and nadir view
    p = (1 - xi**2) / (1 + 2 * xi * cos_g + xi**2) ** 1.5
    img = mu0 / (mu0 + mu + 1e-9) * p
    if shadows:
        img[cast_shadow(dem, px, az, el)] = 0
    img[~np.isfinite(dem)] = np.nan
    return img.astype(np.float32)


def fit_sun(dem, px, img):
    """Estimate (az, el) of a real image by maximising correlation with DEM renders (coarse-to-fine)."""
    small = 2
    d = cv2.resize(np.nan_to_num(dem, nan=np.nanmean(dem)), None, fx=1 / small, fy=1 / small, interpolation=cv2.INTER_AREA)
    t = cv2.resize(np.nan_to_num(img, nan=np.nanmean(img)), None, fx=1 / small, fy=1 / small, interpolation=cv2.INTER_AREA).ravel()

    def score(az, el):
        return np.corrcoef(shade(d, px * small, az, el, shadows=False).ravel(), t)[0, 1]

    best = max(((score(a, e), a, e) for a in range(0, 360, 15) for e in range(5, 80, 5)))
    _, a0, e0 = best
    best = max(((score(a % 360, e), a % 360, e) for a in range(a0 - 14, a0 + 15, 2) for e in range(max(1, e0 - 4), min(89, e0 + 5))))
    return best[1], best[2], best[0]


def similarity(size_ref, angle_deg, scale, shift, size_src):
    """2x3 matrix mapping reference px -> source px: rotate/scale about the ref centre, land on the src centre."""
    cx, cy = size_ref[1] / 2, size_ref[0] / 2
    M = cv2.getRotationMatrix2D((cx, cy), angle_deg, scale)
    M[:, 2] += np.array([size_src[1] / 2 - cx, size_src[0] / 2 - cy]) + shift
    return M


def synthetic_source(ref_lit, M, src_size, down=1, noise=0.01, seed=0):
    """Warp a reference-grid render into a source frame and optionally downscale it by `down`.
    Returns (source image, 2x3 truth ref->source px in the output frame)."""
    src = cv2.warpAffine(np.nan_to_num(ref_lit), M, (src_size[1], src_size[0]), flags=cv2.INTER_CUBIC)
    if down > 1:
        src = cv2.resize(src, (src_size[1] // down, src_size[0] // down), interpolation=cv2.INTER_AREA)
        # ponytail: exact for pixel-area downsampling; centre-of-pixel offset (down-1)/2 is folded in
        M = np.vstack([M, [0, 0, 1]])
        M = (np.array([[1 / down, 0, -(down - 1) / (2 * down)], [0, 1 / down, -(down - 1) / (2 * down)], [0, 0, 1]]) @ M)[:2]
    src = src + np.random.default_rng(seed).normal(0, noise * np.nanstd(src), src.shape).astype(np.float32)
    return src.astype(np.float32), M
