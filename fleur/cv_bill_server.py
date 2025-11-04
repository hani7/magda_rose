# cv_bill_server.py
# -----------------------------------------
# POC de reconnaissance de billets (500/1000/2000 DA) par OpenCV.
# - Multi-templates par valeur (ex: ancienne/nouvelle série).
# - ORB + Homography (SIFT optionnel si opencv-contrib est installé).
# - Expose 2 endpoints:
#     GET  /healthz          -> "ok"
#     GET  /cv/scan          -> détecte un billet (sans notifier Django)
#     POST /cv/stack         -> détecte + notifie Django si confiance OK
#
# DEPENDANCES:
#   pip install opencv-python flask flask-cors requests numpy
#   (optionnel SIFT) pip install opencv-contrib-python
#
# DOSSIER TEMPLATES (exemple) :
#   templates/
#     500_a.jpg   500_b.jpg
#     1000_a.jpg  1000_b.jpg
#     2000_a.jpg  2000_b.jpg
#
# LANCER:
#   set CAM_INDEX=0
#   set CONF_THRESHOLD=0.60
#   python cv_bill_server.py
#
# INTEGRATION COTE DJANGO:
# - Django expose: POST /api/payment/insert-event/ avec header X-Api-Key
#   Body JSON: {"payment_id": <int>, "amount": 500|1000|2000, "event": "bill_cv"}
# - La page payment_insert poll ?json=1 (on l’a déjà mis en place).
# - Bouton "Scanner billet (caméra)" appelle POST /cv/stack {"payment_id": <id>}.

import os
import time
import cv2 # type: ignore
import numpy as np
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

# ========= CONFIG =========
CAM_INDEX       = int(os.getenv("CAM_INDEX", "0"))
FRAME_WIDTH     = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT    = int(os.getenv("FRAME_HEIGHT", "720"))
FPS             = int(os.getenv("FPS", "30"))

# Métriques OpenCV
FEATURES        = int(os.getenv("FEATURES", "3000"))
RATIO_TEST      = float(os.getenv("RATIO_TEST", "0.75"))   # Lowe ratio test
MIN_MATCHES     = int(os.getenv("MIN_MATCHES", "40"))      # min matches avant homographie
RANSAC_REPROJ   = float(os.getenv("RANSAC_REPROJ", "5.0"))
CONF_THRESHOLD  = float(os.getenv("CONF_THRESHOLD", "0.60"))  # seuil acceptation finale [0..1]

# Django API
DJANGO_API      = os.getenv("DJANGO_API", "http://127.0.0.1:8000/api/payment/insert-event/")
DJANGO_API_KEY  = os.getenv("DJANGO_API_KEY", "dev-secret")

# Montants autorisés
ALLOWED_AMOUNTS = [500, 1000, 2000]

# Multi-templates par valeur (ajoute autant d’images que tu veux)
TEMPLATES = {
    500:  ["templates/500_a.jpg",  "templates/500_b.jpg"],
    1000: ["templates/1000_a.jpg", "templates/1000_b.jpg"],
    2000: ["templates/2000_a.jpg", "templates/2000_b.jpg"],
}

# ========= INIT OPENCV (ORB par défaut / SIFT optionnel) =========
USE_SIFT = False
try:
    # Active SIFT si dispo (meilleure robustesse, nécessite opencv-contrib-python)
    if hasattr(cv2, "SIFT_create"):
        if os.getenv("USE_SIFT", "0") == "1":
            USE_SIFT = True
except Exception:
    USE_SIFT = False

if USE_SIFT:
    detector = cv2.SIFT_create(nfeatures=FEATURES)
    # pour SIFT, on match avec NORM_L2
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
else:
    detector = cv2.ORB_create(nfeatures=FEATURES)
    # pour ORB, on match avec NORM_HAMMING
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

def _load_img(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Template introuvable: {path}")
    return img

def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def _detect_and_compute(gray):
    kp, des = detector.detectAndCompute(gray, None)
    return kp, des

class TemplateBank:
    """Stocke plusieurs templates par montant et leurs features."""
    def __init__(self, paths_per_amount):
        self.bank = {}   # amount -> [ {path, gray, kp, des, shape}, ... ]
        for amt, paths in paths_per_amount.items():
            items = []
            for p in paths:
                img = _load_img(p)
                g = _gray(img)
                kp, des = _detect_and_compute(g)
                items.append({
                    "path": p,
                    "gray": g,
                    "kp": kp,
                    "des": des,
                    "shape": g.shape
                })
            self.bank[amt] = items

templates_bank = TemplateBank(TEMPLATES)

# ========= CAMERA =========
_cam = None
def get_cam():
    global _cam
    if _cam is None:
        # CAP_DSHOW = backend Windows plus stable
        _cam = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
        _cam.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        _cam.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        _cam.set(cv2.CAP_PROP_FPS, FPS)
    return _cam

def grab_frame():
    cam = get_cam()
    ok, frame = cam.read()
    if not ok:
        raise RuntimeError("Camera read failed")
    return frame

def preprocess(frame_bgr):
    gray = _gray(frame_bgr)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    return gray

# ========= SCORING =========
def score_against_template(frame_gray, tpl):
    # tpl: dict(path, gray, kp, des, shape)
    kp2, des2 = detector.detectAndCompute(frame_gray, None)
    if des2 is None or tpl["des"] is None or len(tpl["des"]) == 0:
        return 0.0, None

    matches = bf.knnMatch(tpl["des"], des2, k=2)
    good = []
    for m, n in matches:
        if m.distance < RATIO_TEST * n.distance:
            good.append(m)

    if len(good) < MIN_MATCHES:
        return 0.0, None

    src_pts = np.float32([tpl["kp"][m.queryIdx].pt for m in good]).reshape(-1,1,2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1,1,2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, RANSAC_REPROJ)
    if H is None or mask is None:
        return 0.0, None

    inliers = int(mask.sum())
    score = inliers / max(len(good), 1)
    return float(score), H

def classify_bill(frame_bgr):
    """
    Retourne (best_amount, best_score, best_template_path)
    Score d'un montant = max(score de ses templates).
    """
    frame_gray = preprocess(frame_bgr)

    best_amt, best_score, best_tpl_path = None, 0.0, None
    for amt, tpl_list in templates_bank.bank.items():
        local_best = 0.0
        local_path = None
        for tpl in tpl_list:
            s, _ = score_against_template(frame_gray, tpl)
            if s > local_best:
                local_best = s
                local_path = tpl["path"]
        if local_best > best_score:
            best_score, best_amt, best_tpl_path = local_best, amt, local_path

    return best_amt, best_score, best_tpl_path

# ========= DJANGO NOTIFY =========
def notify_django(payment_id, amount):
    r = requests.post(
        DJANGO_API,
        json={"payment_id": int(payment_id), "amount": int(amount), "event": "bill_cv"},
        headers={"X-Api-Key": DJANGO_API_KEY},
        timeout=4
    )
    r.raise_for_status()
    return r.json()

# ========= FLASK APP =========
app = Flask(__name__)
CORS(app)

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/cv/scan")
def cv_scan_get():
    """
    Capture l’image courante, classe le billet et renvoie {amount, confidence, template}.
    N’envoie rien à Django.
    """
    frame = grab_frame()
    amt, score, tpl = classify_bill(frame)
    if not amt:
        return jsonify({"ok": False, "amount": None, "confidence": 0.0, "template": None})
    return jsonify({"ok": True, "amount": int(amt), "confidence": float(score), "template": tpl})

@app.post("/cv/stack")
def cv_stack_post():
    """
    Body JSON: { "payment_id": 42 }
    1) Capture -> classification
    2) Si confidence >= CONF_THRESHOLD et amount ∈ ALLOWED_AMOUNTS -> notifie Django
    """
    data = request.get_json(silent=True) or {}
    payment_id = data.get("payment_id")
    if not isinstance(payment_id, int):
        return jsonify({"ok": False, "error": "payment_id (int) required"}), 400

    frame = grab_frame()
    amt, score, tpl = classify_bill(frame)

    if amt in ALLOWED_AMOUNTS and score >= CONF_THRESHOLD:
        try:
            dj = notify_django(payment_id, amt)
            return jsonify({
                "ok": True,
                "amount": int(amt),
                "confidence": float(score),
                "template": tpl,
                "forwarded": dj
            })
        except requests.RequestException as e:
            return jsonify({"ok": False, "error": f"django_api: {e}"}), 502
    else:
        return jsonify({
            "ok": False,
            "amount": int(amt) if amt else None,
            "confidence": float(score),
            "template": tpl
        }), 422

if __name__ == "__main__":
    host = os.getenv("CV_HOST", "127.0.0.1")
    port = int(os.getenv("CV_PORT", "9998"))
    print(f"[cv] Serving on http://{host}:{port} (SIFT={int(USE_SIFT)}, THRESH={CONF_THRESHOLD})")
    app.run(host=host, port=port, debug=False)
