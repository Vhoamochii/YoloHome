"""Face ID routes with a fake engine: no ONNX models needed, so this runs on CI."""
import base64

import cv2
import numpy as np
import pytest

import face_engine
import main
from routes import auth

if not hasattr(cv2, "imencode"):             # conftest stubs cv2 when OpenCV is not installed
    pytest.skip("needs OpenCV to encode test images", allow_module_level=True)


def frame(person=1, variant=0, faces=1):
    """A tiny PNG whose first pixel tells the fake engine what it shows."""
    img = np.zeros((4, 4, 3), np.uint8)
    img[0, 0] = (person, variant, faces)
    return base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode()


class FakeEngine:
    """Person p's face is the unit vector e_p, nudged a little by the variant so frames differ."""
    thresholds = dict(face_engine.DEFAULT_THRESHOLDS)

    def probe(self, img, strict=False):
        person, variant, faces = (int(v) for v in img[0, 0])
        if faces == 0:
            return face_engine.Probe(reason="Không thấy khuôn mặt")
        if faces > 1:
            return face_engine.Probe(reason="Có nhiều hơn một khuôn mặt")
        v = np.zeros(face_engine.EMBED_DIM, np.float32)
        v[person] = 1.0
        v[64 + variant % 64] = 0.2
        return face_engine.Probe(v / np.linalg.norm(v), None, img)

    def masked_vectors(self, aligned, n, rng):
        return [self.probe(aligned).vector] * n

    def adapt(self, x):
        return x


@pytest.fixture()
def fake_engine():
    main.app.dependency_overrides[auth.get_face_engine] = FakeEngine
    yield
    main.app.dependency_overrides.pop(auth.get_face_engine, None)


def account(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "1234"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def enroll(client, headers, person, kind="plain", n=3):
    return client.post("/api/auth/face/enroll", headers=headers,
                       json={"kind": kind, "images": [frame(person, i) for i in range(n)]})


def test_enroll_needs_login(client, fake_engine):
    assert client.post("/api/auth/face/enroll", json={"kind": "plain", "images": [frame()]}).status_code == 401


def test_enroll_reports_rejected_frames_and_adds_synthetic_masks(client, fake_engine):
    h = account(client, "an@x.vn")
    r = client.post("/api/auth/face/enroll", headers=h,
                    json={"kind": "plain", "images": [frame(1, 0), frame(1, 1, faces=0), frame(1, 2, faces=2)]})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 1
    assert body["rejected"] == [{"index": 1, "reason": "Không thấy khuôn mặt"},
                                {"index": 2, "reason": "Có nhiều hơn một khuôn mặt"}]
    assert body["counts"] == {"plain": 1, "mask": 0, "synthetic_mask": 2}
    assert client.get("/api/auth/me", headers=h).json()["has_face"] is True


def test_enroll_with_no_usable_frame_is_an_error(client, fake_engine):
    h = account(client, "an@x.vn")
    r = client.post("/api/auth/face/enroll", headers=h, json={"kind": "mask", "images": [frame(faces=0)]})
    assert r.status_code == 400
    assert "Không thấy khuôn mặt" in r.json()["detail"]
    assert client.get("/api/auth/face/status", headers=h).json()["has_face"] is False


def test_each_kind_keeps_the_newest_twenty(client, fake_engine):
    h = account(client, "an@x.vn")
    for _ in range(2):
        assert enroll(client, h, 1, n=12).status_code == 200
    assert client.get("/api/auth/face/status", headers=h).json()["counts"] == \
        {"plain": 20, "mask": 0, "synthetic_mask": 20}


def test_face_login_picks_the_right_account(client, fake_engine):
    enroll(client, account(client, "an@x.vn"), person=1)
    enroll(client, account(client, "binh@x.vn"), person=2)
    r = client.post("/api/auth/face-login", json={"images": [frame(2, 7), frame(2, 8), frame(2, 9)]})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "binh@x.vn"
    assert r.json()["matched_kind"] == "plain"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["email"] == "binh@x.vn"


def test_face_login_needs_at_least_two_frames(client, fake_engine):
    enroll(client, account(client, "an@x.vn"), person=1)
    assert client.post("/api/auth/face-login", json={"images": [frame(1, 5)]}).status_code == 400


def test_face_login_rejects_a_stranger(client, fake_engine):
    enroll(client, account(client, "an@x.vn"), person=1)
    r = client.post("/api/auth/face-login", json={"images": [frame(9, 1), frame(9, 2)]})
    assert r.status_code == 401
    assert r.json()["detail"] == auth.LOGIN_REJECTED["no_match"]


def test_face_login_rejects_two_accounts_with_the_same_face(client, fake_engine):
    enroll(client, account(client, "an@x.vn"), person=1)
    enroll(client, account(client, "an2@x.vn"), person=1)
    r = client.post("/api/auth/face-login", json={"images": [frame(1, 5), frame(1, 6)]})
    assert r.status_code == 401
    assert r.json()["detail"] == auth.LOGIN_REJECTED["ambiguous"]


def test_face_login_needs_two_frames_with_a_face(client, fake_engine):
    enroll(client, account(client, "an@x.vn"), person=1)
    r = client.post("/api/auth/face-login", json={"images": [frame(1, 5), frame(faces=0), frame(faces=0)]})
    assert r.status_code == 400
    assert "Không thấy khuôn mặt" in r.json()["detail"]


def test_face_login_without_any_enrollment(client, fake_engine):
    assert client.post("/api/auth/face-login", json={"images": [frame(), frame()]}).status_code == 404


def test_old_register_face_by_email_is_gone(client, fake_engine):
    account(client, "an@x.vn")
    r = client.post("/api/auth/register-face", json={"image": frame(), "email": "an@x.vn"})
    assert r.status_code in (404, 405)
    assert client.post("/api/auth/face-login", json={"images": [frame(), frame()]}).status_code == 404


def test_delete_removes_own_templates_only(client, fake_engine):
    h1, h2 = account(client, "an@x.vn"), account(client, "binh@x.vn")
    enroll(client, h1, 1)
    enroll(client, h2, 2)
    assert client.delete("/api/auth/face", headers=h1).json() == {"deleted": 9}
    assert client.get("/api/auth/face/status", headers=h1).json()["has_face"] is False
    assert client.get("/api/auth/face/status", headers=h2).json()["has_face"] is True


def test_missing_models_give_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(face_engine, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(auth, "_engine", None)
    r = client.post("/api/auth/face-login", json={"images": [frame(), frame()]})
    assert r.status_code == 503


def test_match_uses_the_threshold_of_the_best_template_kind():
    plain, mask = np.eye(4, dtype=np.float32)[:2]
    users, kinds, templates = np.array([1, 1]), np.array(["plain", "mask"]), np.stack([plain, mask])
    probe = 0.33 * mask + np.sqrt(1 - 0.33 ** 2) * np.eye(4, dtype=np.float32)[3]   # cosine 0.33 to mask
    t = {"plain": 0.363, "mask": 0.30, "margin": 0.05}
    assert face_engine.match(probe[None], users, kinds, templates, t) == \
        {"user_id": 1, "score": pytest.approx(0.33), "second": -1.0, "kind": "mask", "reason": None}
    t["mask"] = 0.363
    assert face_engine.match(probe[None], users, kinds, templates, t)["reason"] == "no_match"
