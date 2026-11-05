"""Numerical comparison with the original H5, optional TFLite and optional compiled C++."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tflite", action="store_true")
    p.add_argument("--cpp", type=Path, help="Compiled tests/host_engine.cpp executable")
    p.add_argument("--out", type=Path, default=ROOT / "docs/model_verification.json")
    a = p.parse_args()
    import numpy as np
    from export_model import export_h5
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        h5 = export_h5(ROOT / "models/TinyML.h5", Path(tmp))
    exported = json.loads((ROOT / "models/exported/model.json").read_text())
    if h5 != exported:
        raise AssertionError("Export differs from supplied H5")
    hex_bytes = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", (ROOT / "models/TinyML.h").read_text()))
    assert hex_bytes == (ROOT / "models/TinyML.tflite").read_bytes()
    X = np.stack([np.tile(np.arange(-40, 81, 5), 21), np.repeat(np.arange(0, 101, 5), 25)], axis=1).astype(np.float32)
    def infer(x):
        z = np.maximum(x @ np.array(exported["w1"], np.float32) + np.array(exported["b1"], np.float32), 0)
        z = z @ np.array(exported["w2"], np.float32) + np.float32(exported["b2"])
        return 1 / (1 + np.exp(-np.clip(z, -80, 80)))
    expected = infer(X)
    report = dict(model_id=exported["id"], h5_sha256=exported["source_sha256"],
                  tflite_sha256=hashlib.sha256(hex_bytes).hexdigest(),
                  h_matches_tflite=True, exported_weights_match_h5=True, numerical_inputs=len(X))
    if a.cpp:
        proc = subprocess.run([str(a.cpp.resolve()), "--predict"],
                              input="".join(f"{t} {h}\n" for t, h in X), text=True, capture_output=True, check=True)
        actual = np.array([float(s) for s in proc.stdout.split()])
        error = float(np.max(abs(actual - expected)))
        assert len(actual) == len(X) and error < 1e-5, error
        report["cpp_max_absolute_error"] = error
    if a.tflite:
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
        lite = Interpreter(model_path=str(ROOT / "models/TinyML.tflite"))
        lite.allocate_tensors()
        inputs, outputs = lite.get_input_details()[0], lite.get_output_details()[0]
        assert inputs["dtype"] == np.float32 and list(inputs["shape"]) == [1, 2]
        actual = []
        for x in X:
            lite.set_tensor(inputs["index"], x.reshape(1, 2))
            lite.invoke()
            actual.append(float(lite.get_tensor(outputs["index"])[0, 0]))
        error = float(np.max(abs(np.array(actual) - expected)))
        assert error < 1e-5, error
        report["tflite_max_absolute_error"] = error
    # These are reference-file checks, NOT unseen test accuracy.
    reference = {}
    for f in sorted((ROOT / "data/reference").glob("*.csv")):
        rows = np.array(list(csv.reader(f.open())), dtype=float)
        scores = infer(rows[:, :2].astype(np.float32))
        reference[f.name] = dict(rows=len(rows), exact_duplicate_rows=len(rows)-len(np.unique(rows, axis=0)),
                                correct_at_05=int(((scores >= .5) == rows[:, 2]).sum()),
                                correct_at_08=int(((scores >= .8) == rows[:, 2]).sum()))
    report["reference_data_only"] = reference
    report["note"] = "Numerical equivalence checks, not hardware validation or real fire-detection accuracy."
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
