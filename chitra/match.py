import cv2
import numpy as np


def default():
    """'roma' when RoMa v2 is installed (`pip install chitra[roma]`), else 'sift'."""
    import importlib.util
    return "roma" if importlib.util.find_spec("romav2") else "sift"


def sift(a_u8, b_u8, ratio=0.75, nfeatures=8000):
    """SIFT + Lowe ratio. Returns (pts_a Nx2, pts_b Nx2, score N) where score = 1 - d1/d2."""
    s = cv2.SIFT_create(nfeatures=nfeatures)
    ka, da = s.detectAndCompute(a_u8, None)
    kb, db = s.detectAndCompute(b_u8, None)
    if da is None or db is None or len(ka) < 2 or len(kb) < 2:
        return np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0)
    pa, pb, sc = [], [], []
    for m in cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2):
        if len(m) == 2 and m[0].distance < ratio * m[1].distance:
            pa.append(ka[m[0].queryIdx].pt)
            pb.append(kb[m[0].trainIdx].pt)
            sc.append(1 - m[0].distance / max(m[1].distance, 1e-9))
    return np.array(pa).reshape(-1, 2), np.array(pb).reshape(-1, 2), np.array(sc)


def roma(a_u8, b_u8, n=5000):
    """RoMa v2 dense matcher (`pip install chitra[roma]`). 'precise' (800 px + 1280 px refine) on CUDA,
    'base' (640 px) on Apple MPS / CPU to fit a 16 GB laptop."""
    import torch
    from PIL import Image
    from romav2 import RoMaV2

    if getattr(roma, "model", None) is None:
        roma.model = RoMaV2(RoMaV2.Cfg(setting="precise" if torch.cuda.is_available() else "base"))
    m = roma.model
    A, B = (Image.fromarray(x).convert("RGB") for x in (a_u8, b_u8))
    preds = m.match(A, B)
    matches, overlap, _, _ = m.sample(preds, n)
    ka, kb = m.to_pixel_coordinates(matches, *a_u8.shape, *b_u8.shape)
    return ka.cpu().numpy(), kb.cpu().numpy(), overlap.cpu().numpy()
