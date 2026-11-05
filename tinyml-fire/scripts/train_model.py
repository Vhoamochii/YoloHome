"""Optional retraining on labeled real sessions; never automatically replaces the demo."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("models/retrained"))
    p.add_argument("--epochs", type=int, default=100)
    a = p.parse_args()
    if a.epochs <= 0:
        p.error("--epochs must be positive")
    import numpy as np
    import tensorflow as tf
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.metrics import confusion_matrix, classification_report
    from export_model import write_model
    tf.keras.utils.set_random_seed(42)
    with a.csv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    required = {"temperature", "humidity", "label", "session_id"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("CSV needs temperature,humidity,label,session_id; legacy CSV lacks sessions")
    # Exact duplicate readings within one session are removed before the grouped split.
    unique = list(dict.fromkeys((float(r["temperature"]), float(r["humidity"]),
                                 int(r["label"]), r["session_id"].strip()) for r in rows))
    X = np.array([r[:2] for r in unique], dtype=np.float32)
    y = np.array([r[2] for r in unique], dtype=np.int32)
    groups = np.array([r[3] for r in unique])
    if (not np.isfinite(X).all() or not np.isin(y, [0, 1]).all() or (groups == "").any()
            or (X[:, 0] < -40).any() or (X[:, 0] > 80).any()
            or (X[:, 1] < 0).any() or (X[:, 1] > 100).any()):
        raise ValueError("Invalid values, labels or session ids")
    if len(set(groups)) < 6 or any(len(set(groups[y == c])) < 3 for c in [0, 1]):
        raise ValueError("Need >=6 independent sessions, >=3 sessions represented per class")
    chosen = None
    for seed in range(42, 142):
        trval, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(X, y, groups))
        tr, val = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed).split(X[trval], y[trval], groups[trval]))
        train, val = trval[tr], trval[val]
        if all(set(y[idx]) == {0, 1} for idx in [train, val, test]):
            chosen = train, val, test
            break
    if chosen is None:
        raise ValueError("Cannot make independent splits with both classes. Collect more sessions.")
    train, val, test = chosen
    mean = X[train].mean(axis=0)
    scale = X[train].std(axis=0)
    scale[scale < 1e-6] = 1
    Z = (X - mean) / scale
    model = tf.keras.Sequential([tf.keras.layers.Input(shape=(2,)),
                                 tf.keras.layers.Dense(8, activation="relu"),
                                 tf.keras.layers.Dense(1, activation="sigmoid")])
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    model.fit(Z[train], y[train], validation_data=(Z[val], y[val]), epochs=a.epochs,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=12, restore_best_weights=True)], verbose=2)
    a.out.mkdir(parents=True, exist_ok=True)
    model.save(a.out / "trained.keras")
    tflite = tf.lite.TFLiteConverter.from_keras_model(model).convert()
    tflite_path = a.out / "trained.tflite"
    tflite_path.write_bytes(tflite)
    # Model identity includes preprocessing as well as the learned weights.
    identity_path = a.out / "identity.json"
    identity_path.write_text(json.dumps(dict(tflite_sha256=hashlib.sha256(tflite).hexdigest(),
                                              mean=mean.tolist(), scale=scale.tolist())), encoding="utf-8")
    write_model(*model.get_weights(), source=identity_path, out=a.out,
                mean=mean.tolist(), scale=scale.tolist())
    score = model.predict(Z[test], verbose=0).reshape(-1)
    report = dict(dataset_sha256=hashlib.sha256(a.csv.read_bytes()).hexdigest(),
                  raw_rows=len(rows), unique_rows=len(unique), seed=seed,
                  sessions={name: sorted(set(groups[idx])) for name, idx in
                            [("train", train), ("validation", val), ("test", test)]},
                  threshold_05=classification_report(y[test], score >= .5, output_dict=True, zero_division=0),
                  confusion_05=confusion_matrix(y[test], score >= .5).tolist(),
                  confusion_08=confusion_matrix(y[test], score >= .8).tolist(),
                  note="Held-out sessions; labels reflect your experiments, not proof of real fire detection.")
    (a.out / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Saved outputs. Review training_report.json before manually copying model_weights.h to firmware/include/.")


if __name__ == "__main__":
    main()
