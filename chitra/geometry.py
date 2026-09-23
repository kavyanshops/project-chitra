import cv2
import numpy as np


def grid_balance(pa, score, shape, grid=8, k=40):
    """Keep at most k best-scoring matches per cell of a grid x grid partition of image A."""
    h, w = shape
    cell = (np.clip(pa[:, 1] * grid // h, 0, grid - 1) * grid + np.clip(pa[:, 0] * grid // w, 0, grid - 1)).astype(int)
    keep = []
    for c in np.unique(cell):
        idx = np.where(cell == c)[0]
        keep.extend(idx[np.argsort(-score[idx])[:k]])
    return np.sort(np.array(keep, int))


def fit(pa, pb, model="affine", thresh=1.0):
    """MAGSAC++ fit A->B. Returns (3x3 matrix or None, inlier mask)."""
    if len(pa) < 4:
        return None, np.zeros(len(pa), bool)
    a, b = pa.astype(np.float32), pb.astype(np.float32)
    if model == "homography":
        H, m = cv2.findHomography(a, b, cv2.USAC_MAGSAC, thresh, maxIters=10000, confidence=0.9999)
    else:
        H, m = cv2.estimateAffine2D(a, b, method=cv2.USAC_MAGSAC, ransacReprojThreshold=thresh,
                                    maxIters=10000, confidence=0.9999)
        H = None if H is None else np.vstack([H, [0, 0, 1]])
    return H, (np.zeros(len(pa), bool) if m is None else m.ravel().astype(bool))


def apply(H, p):
    q = np.c_[p, np.ones(len(p))] @ H.T
    return q[:, :2] / q[:, 2:3]


def warp(src, H, out_shape):
    """Resample the source onto the reference grid, given H mapping source px -> reference px."""
    return cv2.warpPerspective(np.nan_to_num(src).astype(np.float32), H, (out_shape[1], out_shape[0]),
                               flags=cv2.INTER_CUBIC, borderValue=np.nan)
