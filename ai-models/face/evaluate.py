"""Đánh giá E0–E5 trên ảnh nhóm: mẫu đăng ký và chọn ngưỡng lấy từ buổi 1, kiểm tra trên buổi 2.

    python evaluate.py
    python evaluate.py --no-e0          # bỏ qua dlib (chậm; cần thư viện face_recognition)

E0  dlib hiện tại, 1 ảnh không khẩu trang (giống hệ thống đang chạy)
E1  SFace, N ảnh không khẩu trang
E2  E1 + khẩu trang giả lập từ chính các ảnh đó
E3  E1 + N ảnh đeo khẩu trang thật
E4  E3 + adapter chung        (out/adapter_generic.npz)
E5  E3 + adapter riêng cho nhà (out/adapter_home.npz)

Người lạ: ảnh của các người LFW để riêng (không dùng khi train), cộng với chính các thành viên khi
coi như chưa đăng ký (leave-one-out). Quyết định chấp nhận giống backend: ngưỡng theo loại mẫu khớp
nhất (plain / mask) và khoảng cách tối thiểu với người khớp nhì.

Kết quả: out/report.json, out/thresholds_E*.json (ngưỡng chọn trên buổi 1), out/roc.png
"""
import argparse
import json
from datetime import datetime

import cv2
import numpy as np

from common import (CONDITIONS, LFW_FEATURES, OUT, SEED, TEAM_DIR, TEAM_FEATURES, face_engine,
                    frr_at_far, lfw_val_people, load_features, select, threshold_at_far)

EXPERIMENTS = {
    "E1": ("SFace, chỉ mẫu không khẩu trang", ("plain",), None),
    "E2": ("SFace + khẩu trang giả lập", ("plain", "synthetic_mask"), None),
    "E3": ("SFace + khẩu trang thật", ("plain", "mask"), None),
    "E4": ("SFace + adapter chung + khẩu trang thật", ("plain", "mask"), "generic"),
    "E5": ("SFace + adapter riêng cho nhà + khẩu trang thật", ("plain", "mask"), "home"),
}
MIN_IMPOSTORS = 100            # fewer impostor attempts cannot measure FAR = 1%
DLIB_THRESHOLD = 0.55          # MATCH_THRESHOLD in backend/routes/auth.py


def evenly(ix, n):
    return ix[np.unique(np.linspace(0, len(ix) - 1, min(n, len(ix))).round().astype(int))] if len(ix) else ix


def pick_templates(team, people, n):
    """Session-1 enrollment: n bare and n masked photos per person spread over the recording,
    plus the synthetic masks drawn on those bare photos."""
    chosen = np.zeros(len(team["emb"]), bool)
    for p in people:
        for cond in ("plain", "mask"):
            ix = np.flatnonzero((team["person"] == p) & (team["session"] == 1) & (team["condition"] == cond))
            chosen[evenly(ix[np.argsort(team["path"][ix])], n)] = True
    plain_ids = team["image_id"][chosen & (team["condition"] == "plain")]
    synth = (team["condition"] == "synthetic_mask") & np.isin(team["image_id"], plain_ids)
    return chosen | synth


def score(probes, gallery, gal_pid, gal_masked, n_people):
    """Per probe and person: best cosine over that person's templates, and whether that
    template is a masked one."""
    s = probes @ gallery.T
    rows = np.arange(len(probes))
    best = np.full((len(probes), n_people), -np.inf, np.float32)
    masked = np.zeros((len(probes), n_people), bool)
    for j in range(n_people):
        cols = np.flatnonzero(gal_pid == j)
        if len(cols):
            a = s[:, cols].argmax(1)
            best[:, j] = s[rows, cols[a]]
            masked[:, j] = gal_masked[cols[a]]
    return best, masked


def _top2(best, masked):
    rows = np.arange(len(best))
    order = np.argsort(-best, axis=1)
    second = best[rows, order[:, 1]] if best.shape[1] > 1 else np.full(len(best), -np.inf)
    return dict(top=best[rows, order[:, 0]], second=second, masked=masked[rows, order[:, 0]]), order[:, 0]


def attempts(best, masked, true_pid):
    """Genuine attempts: team probes. Impostor attempts: team probes with their own column removed
    (leave-one-out) and strangers (true_pid -1) against everyone."""
    team = true_pid >= 0
    gen, top = _top2(best[team], masked[team])
    gen["correct"] = top == true_pid[team]
    gen["score"] = np.where(gen["correct"], gen["top"], -np.inf)
    others = best.copy()
    others[np.flatnonzero(team), true_pid[team]] = -np.inf
    imp, _ = _top2(others, masked)
    return gen, imp


def accept(att, thr):
    t = np.where(att["masked"], thr["mask"], thr["plain"])
    with np.errstate(invalid="ignore"):
        return (att["top"] >= t) & (att["top"] - att["second"] >= thr["margin"])


def calibrate(imp):
    """One threshold per template kind, each at FAR = 1% on session 1 (+ calibration strangers)."""
    found, counts, notes = {}, {}, []
    for group, sel in (("plain", ~imp["masked"]), ("mask", imp["masked"])):
        counts[group] = int(sel.sum())
        if counts[group] >= MIN_IMPOSTORS:
            found[group] = threshold_at_far(imp["top"][sel])
    thr = dict(face_engine.DEFAULT_THRESHOLDS)
    for group in ("plain", "mask"):
        other = "mask" if group == "plain" else "plain"
        if group in found:
            thr[group] = found[group]
        elif counts[group]:
            thr[group] = found.get(other, thr[group])
            notes.append(f"chỉ {counts[group]} lượt người lạ khớp mẫu {group} (cần {MIN_IMPOSTORS}): "
                         f"dùng {'ngưỡng nhóm ' + other if other in found else 'ngưỡng mặc định'}")
        thr[group] = round(thr[group], 4)
    return thr, notes


def condition_metrics(gen, imp, thr):
    frr1, thr1 = frr_at_far(gen["score"], imp["top"])
    return {"genuine": int(len(gen["top"])), "impostors": int(len(imp["top"])),
            "few_impostors": bool(len(imp["top"]) < MIN_IMPOSTORS),
            "rank1": round(float(gen["correct"].mean()), 4),
            "frr_at_far1": round(frr1, 4), "threshold_at_far1": round(thr1, 4),
            "deployed_far": round(float(accept(imp, thr).mean()), 4),
            "deployed_frr": round(1 - float((accept(gen, thr) & gen["correct"]).mean()), 4)}


def condition_rows(cond, team_cond, true_pid):
    """Team probes of this condition, plus strangers: bare LFW faces for 'plain', synthetic masks
    for both masked conditions."""
    stranger_cond = "plain" if cond == "plain" else "mask"
    return np.flatnonzero(np.where(true_pid >= 0, team_cond == cond, team_cond == stranger_cond))


def run_sface(name, kinds, adapter, data, curves):
    params = None
    if adapter:
        path = OUT / f"adapter_{adapter}.npz"
        if not path.exists():
            print(f"{name}: bỏ qua, chưa có {path.name} (chạy train_adapter.py --variant {adapter})")
            return None
        params = face_engine.load_adapter(path)
    g = data["gallery"]
    sel = np.isin(g["condition"], kinds)
    gal = face_engine.apply_adapter(params, g["emb"][sel])
    gal_pid, gal_masked = g["pid"][sel], g["condition"][sel] != "plain"

    def run(split):
        p = data[split]
        best, masked = score(face_engine.apply_adapter(params, p["emb"]), gal, gal_pid, gal_masked,
                             len(data["people"]))
        return best, masked, p["pid"], p["condition"]

    best, masked, pid, _ = run("calib")
    thr, notes = calibrate(attempts(best, masked, pid)[1])
    best, masked, pid, cond = run("test")
    result = {"thresholds": thr, "calibration_notes": notes, "conditions": {}}
    for c in CONDITIONS:
        rows = condition_rows(c, cond, pid)
        if not (pid[rows] >= 0).any():
            continue
        gen, imp = attempts(best[rows], masked[rows], pid[rows])
        result["conditions"][c] = condition_metrics(gen, imp, thr)
        curves.setdefault(c, {})[name] = (gen["score"], imp["top"])
    return result


def run_dlib(team, people, limit, curves):
    try:
        import face_recognition
    except ImportError:
        print("E0: bỏ qua, chưa cài face_recognition (dlib)")
        return None

    def encode(rel):
        img = cv2.imread(str(TEAM_DIR / rel))
        if img is None:
            return None
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb)
        if not locs:
            return None
        loc = max(locs, key=lambda l: (l[2] - l[0]) * (l[1] - l[3]))
        return face_recognition.face_encodings(rgb, [loc])[0]

    real = np.isin(team["condition"], CONDITIONS)
    templates = {}
    for j, p in enumerate(people):
        ix = np.flatnonzero((team["person"] == p) & (team["session"] == 1) & (team["condition"] == "plain"))
        for rel in sorted(team["path"][ix])[:5]:          # first usable bare photo, like enrolling once
            enc = encode(rel)
            if enc is not None:
                templates[j] = enc
                break
    probes, pids, conds = [], [], []
    for j, p in enumerate(people):
        for c in CONDITIONS:
            ix = np.flatnonzero((team["person"] == p) & (team["session"] == 2) & (team["condition"] == c) & real)
            for rel in team["path"][evenly(ix[np.argsort(team["path"][ix])], limit)]:
                probes.append(encode(rel))
                pids.append(j)
                conds.append(c)
    print(f"E0: dlib mã hoá {len(probes)} ảnh buổi 2, {sum(e is None for e in probes)} ảnh không tìm thấy mặt")
    best = np.full((len(probes), len(people)), -np.inf, np.float32)
    known = sorted(templates)
    for i, enc in enumerate(probes):
        if enc is not None and known:
            best[i, known] = -face_recognition.face_distance([templates[k] for k in known], enc)
    masked = np.zeros(best.shape, bool)
    pids, conds = np.array(pids), np.array(conds)
    thr = {"plain": -DLIB_THRESHOLD, "mask": -DLIB_THRESHOLD, "margin": -np.inf}
    result = {"thresholds": {"distance": DLIB_THRESHOLD}, "conditions": {},
              "calibration_notes": ["không có người lạ LFW; điểm = -khoảng cách dlib"]}
    for c in CONDITIONS:
        rows = np.flatnonzero(conds == c)
        if len(rows):
            gen, imp = attempts(best[rows], masked[rows], pids[rows])
            result["conditions"][c] = condition_metrics(gen, imp, thr)
            curves.setdefault(c, {})["E0"] = (gen["score"], imp["top"])
    return result


def load_data(templates_per_kind, n_strangers):
    team = load_features(TEAM_FEATURES)
    people = sorted(set(team["person"]))
    team["pid"] = np.array([people.index(p) for p in team["person"]])
    missing = [p for p in people if not ((team["person"] == p) & (team["session"] == 2)).any()]
    if missing:
        print(f"Chưa có ảnh buổi 2 của: {', '.join(missing)} (chỉ dùng làm mẫu đăng ký)")
    if not (team["session"] == 2).any():
        raise SystemExit("Chưa có ảnh buổi 2: thu bằng collect.py --session 2 vào một ngày khác")
    tmpl = pick_templates(team, people, templates_per_kind)
    real = np.isin(team["condition"], CONDITIONS)
    data = {"people": people, "gallery": select(team, tmpl),
            "calib": select(team, (team["session"] == 1) & real & ~tmpl),
            "test": select(team, (team["session"] == 2) & real)}

    n_str = {"calib": 0, "test": 0}
    if n_strangers and LFW_FEATURES.exists():
        lfw = load_features(LFW_FEATURES)
        val = np.isin(lfw["person"], sorted(lfw_val_people(lfw["person"])))
        rng = np.random.default_rng(SEED)
        for cond, label in (("plain", "plain"), ("synthetic_mask", "mask")):
            ix = rng.permutation(np.flatnonzero(val & (lfw["condition"] == cond)))[:2 * n_strangers]
            for split, part in (("calib", ix[0::2]), ("test", ix[1::2])):
                d = data[split]
                d["emb"] = np.concatenate([d["emb"], lfw["emb"][part]])
                d["pid"] = np.concatenate([d["pid"], np.full(len(part), -1)])
                d["condition"] = np.concatenate([d["condition"], np.full(len(part), label)])
                n_str[split] += len(part)
    else:
        print("Không có người lạ LFW (chưa chạy extract_features.py lfw): FAR chỉ dựa trên leave-one-out")
    return team, data, n_str


def plot(curves, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    titles = {"plain": "Không khẩu trang", "mask": "Đeo khẩu trang", "mask_glasses": "Khẩu trang + kính"}
    conds = [c for c in CONDITIONS if c in curves]
    fig, axes = plt.subplots(1, len(conds), figsize=(5 * len(conds), 4), squeeze=False)
    for ax, c in zip(axes[0], conds):
        for name, (gen, imp) in sorted(curves[c].items()):
            gen_s, imp_s = np.sort(gen), np.sort(imp)
            t = np.unique(np.concatenate([gen_s[np.isfinite(gen_s)], imp_s[np.isfinite(imp_s)]]))
            far = 1 - np.searchsorted(imp_s, t, "left") / len(imp_s)
            frr = np.searchsorted(gen_s, t, "left") / len(gen_s)
            keep = far > 0
            ax.plot(far[keep], frr[keep], label=name)
        ax.set_xscale("log")
        ax.set_xlim(1e-3, 1)
        ax.set_ylim(0, 1)
        ax.axvline(0.01, color="gray", lw=0.5, ls="--")
        ax.set_title(titles[c])
        ax.set_xlabel("FAR (nhận nhầm người lạ)")
        ax.set_ylabel("FRR (từ chối nhầm người nhà)")
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--templates", type=int, default=10, help="số ảnh mẫu mỗi loại mỗi người (buổi 1)")
    p.add_argument("--strangers", type=int, default=1000, help="số ảnh người lạ LFW mỗi loại mỗi phần")
    p.add_argument("--no-e0", action="store_true")
    p.add_argument("--e0-limit", type=int, default=40, help="E0: số ảnh buổi 2 mỗi người mỗi điều kiện")
    a = p.parse_args()

    team, data, n_str = load_data(a.templates, a.strangers)
    curves, results = {}, {}
    if not a.no_e0:
        results["E0"] = run_dlib(team, data["people"], a.e0_limit, curves)
    for name, (desc, kinds, adapter) in EXPERIMENTS.items():
        results[name] = run_sface(name, kinds, adapter, data, curves)
    results = {k: v for k, v in results.items() if v is not None}
    descriptions = {"E0": "dlib hiện tại, 1 ảnh không khẩu trang", **{k: v[0] for k, v in EXPERIMENTS.items()}}

    OUT.mkdir(exist_ok=True)
    for name, r in results.items():
        r["description"] = descriptions[name]
        if name != "E0":
            (OUT / f"thresholds_{name}.json").write_text(json.dumps(
                {**r["thresholds"], "experiment": name, "calibrated_on": "session 1"}, indent=2))
    report = {"created": datetime.now().isoformat(timespec="seconds"),
              "templates_per_kind": a.templates,
              "data": {"people": len(data["people"]),
                       "calibration_probes": int((data["calib"]["pid"] >= 0).sum()),
                       "test_probes": {c: int(((data["test"]["pid"] >= 0) & (data["test"]["condition"] == c)).sum())
                                       for c in CONDITIONS},
                       "lfw_strangers": n_str},
              "experiments": results}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    plot(curves, OUT / "roc.png")

    print(f"\n{'':4}" + "".join(f"{c:>27}" for c in CONDITIONS))
    print(f"{'':4}" + f"{'rank1':>11}{'FRR@1%':>8}{'FRR*':>8}" * len(CONDITIONS))
    for name, r in results.items():
        cells = []
        for c in CONDITIONS:
            m = r["conditions"].get(c)
            cells.append(f"{m['rank1']:11.3f}{m['frr_at_far1']:8.3f}{m['deployed_frr']:8.3f}" if m else f"{'—':>27}")
        print(f"{name:4}" + "".join(cells))
    print("FRR@1%: FRR khi FAR = 1% trên buổi 2.  FRR*: FRR ở ngưỡng đã chọn trên buổi 1 (thresholds_E*.json).")
    print("Xem 'few_impostors' trong report.json: ít hơn 100 lượt người lạ thì FAR 1% không đo chính xác được.")
    print(f"→ {OUT / 'report.json'}, {OUT / 'roc.png'}")


if __name__ == "__main__":
    main()
