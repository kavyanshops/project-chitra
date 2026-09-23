import cv2
import numpy as np


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
    """RoMa v2 dense matcher (GPU/Colab only: `pip install chitra[roma]`). Not run on the local laptop."""
    import torch  # noqa: F401
    from PIL import Image
    from romav2 import RoMaV2

    m = roma.model = getattr(roma, "model", None) or RoMaV2()
    A, B = (Image.fromarray(x).convert("RGB") for x in (a_u8, b_u8))
    preds = m.match(A, B)
    matches, overlap, _, _ = m.sample(preds, n)
    ka, kb = m.to_pixel_coordinates(matches, *a_u8.shape, *b_u8.shape)
    return ka.cpu().numpy(), kb.cpu().numpy(), overlap.cpu().numpy()
