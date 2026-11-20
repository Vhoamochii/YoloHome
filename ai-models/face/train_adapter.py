"""Train adapter: mạng MLP dư nhỏ đặt sau SFace — phần mô hình nhóm tự train.

    python train_adapter.py --variant generic   # chỉ LFW (thí nghiệm E4); thêm người không cần train lại
    python train_adapter.py --variant home      # LFW + ảnh nhóm buổi 1 (thí nghiệm E5)

Loss: batch-hard triplet trên khoảng cách cosine. Mỗi batch gồm P người × K vector, mỗi người có
ít nhất một mặt không khẩu trang và một mặt đeo khẩu trang. Dừng sớm theo FRR@FAR=1% của cặp
(không khẩu trang, khẩu trang) trên những người LFW để riêng cho validation.

Kết quả: out/adapter_<variant>.npz — chỉ xuất khi thắng SFace gốc trên validation (hoặc --force)
         out/train_<variant>.json — cấu hình, số liệu từng epoch, để đưa vào báo cáo
"""
import argparse
import copy
import json
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from common import (LFW_FEATURES, MASKED, OUT, SEED, TEAM_FEATURES, face_engine, frr_at_far,
                    lfw_val_people, load_features, select)

MIN_GAIN = 0.005          # export only if masked FRR drops by at least 0.5 percentage points
PLAIN_SLACK = 0.01        # ... and bare-face FRR rises by at most 1 point


class AdapterNet(nn.Module):
    """y = normalize(x + W2 relu(W1 x + b1) + b2). Must match face_engine.apply_adapter.
    W2 and b2 start at zero, so the untrained adapter is exactly raw SFace."""

    def __init__(self, dim=face_engine.EMBED_DIM, hidden=256):
        super().__init__()
        self.fc1 = nn.Linear(dim, hidden)
        self.fc2 = nn.Linear(hidden, dim)
        nn.init.zeros_(self.fc2.weight)
        nn.init.zeros_(self.fc2.bias)

    def forward(self, x):
        return F.normalize(x + self.fc2(F.relu(self.fc1(x))), dim=-1)

    def export(self, path, meta):
        p = {k: v.detach().numpy() for k, v in self.state_dict().items()}
        np.savez(path, w1=p["fc1.weight"], b1=p["fc1.bias"], w2=p["fc2.weight"], b2=p["fc2.bias"],
                 meta=np.array(json.dumps(meta)))


def batch_hard_triplet(z, labels, margin):
    """For each vector: its farthest same-person vector vs its nearest other-person vector."""
    d = 1 - z @ z.T
    same = labels[:, None] == labels[None, :]
    pos = same & ~torch.eye(len(z), dtype=torch.bool)
    hardest_pos = torch.where(pos, d, torch.zeros_like(d)).max(1).values
    hardest_neg = torch.where(same, torch.full_like(d, 4.0), d).min(1).values
    losses = F.relu(hardest_pos - hardest_neg + margin)[pos.any(1)]
    return losses.mean(), float((losses > 0).float().mean())


class Sampler:
    def __init__(self, person, condition, always, p, k, rng):
        masked = np.isin(condition, MASKED)
        groups = {}
        for i, name in enumerate(person):
            groups.setdefault(name, []).append(i)
        self.groups = {n: (np.array([i for i in ix if not masked[i]]), np.array([i for i in ix if masked[i]]),
                           np.array(ix)) for n, ix in groups.items()}
        self.label = {n: j for j, n in enumerate(sorted(groups))}
        self.always = list(always)                 # team people: in every batch
        self.others = [n for n in sorted(groups) if n not in set(always)]
        if len(self.always) >= p:
            raise SystemExit(f"Nhiều người trong nhóm hơn --people {p}")
        self.p, self.k, self.rng = p, k, rng

    def batch(self):
        names = self.always + list(self.rng.choice(self.others, self.p - len(self.always), replace=False))
        idx, lab = [], []
        for n in names:
            plain, masked, every = self.groups[n]
            pick = [self.rng.choice(g) for g in (plain, masked) if len(g)]
            pick += list(self.rng.choice(every, self.k - len(pick)))
            idx += pick
            lab += [self.label[n]] * self.k
        return np.array(idx), torch.tensor(lab)


def val_pairs(f, rng, n):
    """Genuine pairs: two different photos of one person. Impostor pairs: two people.
    'plain' compares two bare faces, 'mask' compares a bare face with a masked one."""
    cond, person, iid = f["condition"], f["person"], f["image_id"]
    plain = np.flatnonzero(cond == "plain")
    masks_of, photos = {}, {}
    for i in np.flatnonzero(cond == "synthetic_mask"):
        masks_of.setdefault(iid[i], []).append(i)
    for i in plain:
        photos.setdefault(person[i], []).append(i)
    multi = [v for v in photos.values() if len(v) >= 2]
    gen, imp = {"plain": [], "mask": []}, {"plain": [], "mask": []}
    for _ in range(n):
        a, b = rng.choice(multi[rng.integers(len(multi))], 2, replace=False)
        gen["plain"].append((a, b))
        gen["mask"].append((a, rng.choice(masks_of[iid[b]])))
        a, b = rng.choice(plain, 2)
        while person[a] == person[b]:
            b = rng.choice(plain)
        imp["plain"].append((a, b))
        imp["mask"].append((a, rng.choice(masks_of[iid[b]])))
    return {k: np.array(gen[k]) for k in gen}, {k: np.array(imp[k]) for k in imp}


def val_metrics(z, pairs):
    gen, imp = pairs
    out = {}
    for kind in ("plain", "mask"):
        g = (z[gen[kind][:, 0]] * z[gen[kind][:, 1]]).sum(1)
        i = (z[imp[kind][:, 0]] * z[imp[kind][:, 1]]).sum(1)
        frr, thr = frr_at_far(g, i)
        out[kind] = {"frr_at_far1": round(frr, 4), "threshold": round(thr, 4)}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--variant", required=True, choices=("generic", "home"))
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--steps", type=int, default=200, help="batch mỗi epoch")
    p.add_argument("--people", type=int, default=32, help="P: số người mỗi batch")
    p.add_argument("--per-person", type=int, default=4, help="K: số vector mỗi người")
    p.add_argument("--margin", type=float, default=0.2)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--patience", type=int, default=8)
    p.add_argument("--val-pairs", type=int, default=20000)
    p.add_argument("--force", action="store_true", help="xuất adapter dù không thắng SFace gốc")
    a = p.parse_args()
    t0 = time.time()
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    lfw = load_features(LFW_FEATURES)
    is_val = np.isin(lfw["person"], sorted(lfw_val_people(lfw["person"])))
    train, val = select(lfw, ~is_val), select(lfw, is_val)
    team_people = []
    if a.variant == "home":
        team = load_features(TEAM_FEATURES)
        s1 = select(team, team["session"] == 1)
        if not len(s1["emb"]):
            raise SystemExit("Chưa có ảnh buổi 1 trong features_team.npz")
        s1["person"] = np.char.add("team:", s1["person"])
        team_people = sorted(set(s1["person"]))
        train = {k: np.concatenate([train[k], s1[k]]) for k in ("emb", "person", "condition")}

    x_train = torch.from_numpy(train["emb"])
    x_val = torch.from_numpy(val["emb"])
    sampler = Sampler(train["person"], train["condition"], team_people, a.people, a.per_person, rng)
    pairs = val_pairs(val, np.random.default_rng(SEED + 1), a.val_pairs)
    baseline = val_metrics(val["emb"], pairs)
    print(f"Train: {len(x_train)} vector / {len(sampler.groups)} người ({len(team_people)} người nhóm); "
          f"validation: {len(x_val)} vector / {len(set(val['person']))} người LFW")
    print(f"SFace gốc   FRR@FAR1%  plain {baseline['plain']['frr_at_far1']:.3f}  "
          f"mask {baseline['mask']['frr_at_far1']:.3f}")

    model = AdapterNet()
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=a.weight_decay)
    plain_limit = baseline["plain"]["frr_at_far1"] + PLAIN_SLACK
    best, best_state, best_epoch, history, stale = None, None, 0, [], 0
    for epoch in range(1, a.epochs + 1):
        model.train()
        losses, active = [], []
        for _ in range(a.steps):
            idx, lab = sampler.batch()
            loss, act = batch_hard_triplet(model(x_train[idx]), lab, a.margin)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss))
            active.append(act)
        model.eval()
        with torch.no_grad():
            m = val_metrics(model(x_val).numpy(), pairs)
        history.append({"epoch": epoch, "loss": round(float(np.mean(losses)), 5),
                        "active_triplets": round(float(np.mean(active)), 3), **m})
        print(f"epoch {epoch:3d}  loss {np.mean(losses):.4f}  active {np.mean(active):.2f}  "
              f"FRR@FAR1%  plain {m['plain']['frr_at_far1']:.3f}  mask {m['mask']['frr_at_far1']:.3f}")
        if m["plain"]["frr_at_far1"] <= plain_limit and (
                best is None or m["mask"]["frr_at_far1"] < best["mask"]["frr_at_far1"]):
            best, best_state, best_epoch, stale = m, copy.deepcopy(model.state_dict()), epoch, 0
        else:
            stale += 1
            if stale >= a.patience:
                break

    gain = baseline["mask"]["frr_at_far1"] - best["mask"]["frr_at_far1"] if best else 0.0
    improved = best is not None and gain >= MIN_GAIN
    log = {"variant": a.variant, "config": vars(a), "seconds": round(time.time() - t0, 1),
           "data": {"train_vectors": len(x_train), "train_people": len(sampler.groups),
                    "team_people": [n[5:] for n in team_people], "val_vectors": len(x_val),
                    "val_people": len(set(val["person"])), "val_pairs_each": a.val_pairs},
           "baseline_sface": baseline, "best": best, "best_epoch": best_epoch,
           "masked_frr_gain": round(gain, 4), "improved": improved, "exported": False, "history": history}

    path = OUT / f"adapter_{a.variant}.npz"
    if best is not None and (improved or a.force):
        model.load_state_dict(best_state)
        model.export(path, {"variant": a.variant, "best_epoch": best_epoch, "model": face_engine.MODEL_TAG})
        with torch.no_grad():
            ref = model(x_val[:1000]).numpy()
        got = face_engine.apply_adapter(face_engine.load_adapter(path), val["emb"][:1000])
        diff = float(np.abs(ref - got).max())
        if diff > 1e-5:
            path.unlink()
            raise SystemExit(f"numpy và PyTorch lệch nhau {diff:.2e}: adapter đã bị xoá")
        log.update(exported=True, parity_max_diff=diff)
        print(f"Epoch tốt nhất {best_epoch}: FRR khẩu trang giảm {gain * 100:.1f} điểm % → {path}")
    else:
        print("Adapter không thắng SFace gốc trên validation: không xuất (--force để xuất thử). "
              "Vẫn ghi kết quả này vào báo cáo.")
    (OUT / f"train_{a.variant}.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
