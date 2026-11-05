"""Check the supplied backend event parser and compare untouched files against its ZIP."""
import argparse
import ast
import dataclasses
import datetime
import hashlib
import json
from pathlib import Path
import typing
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--original-zip", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("docs/backend_verification.json"))
    a = p.parse_args()
    original = {}
    with zipfile.ZipFile(a.original_zip) as z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            rel = Path(*Path(n).parts[1:])
            if ".." in rel.parts:
                raise ValueError("Unsafe original ZIP path")
            original[str(rel)] = hashlib.sha256(z.read(n)).hexdigest()
            current = a.repo / rel
            if not current.is_file() or hashlib.sha256(current.read_bytes()).hexdigest() != original[str(rel)]:
                raise AssertionError("Original file changed: " + str(rel))
    source = a.repo / "backend/adafruit_mqtt.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    # Exercise the real parser definition without starting networking or importing DB modules.
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
             and n.name in {"Backlog", "parse_event"}]
    ns = dict(dataclass=dataclasses.dataclass, Optional=typing.Optional,
              datetime=datetime.datetime, timezone=datetime.timezone)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), ns)
    events = ["TINYML:OK:0.001", "TINYML:ALERT:0.824", "TINYML:SENSOR_ERROR:-1.000"]
    for event in events:
        assert ns["parse_event"](event) == ("TINYML", event.split(":", 1)[1])
    result = dict(original_files_compared=len(original), original_files_unchanged=True,
                  backend_parser_accepts=events, live_broker_or_database_test=False,
                  original_zip_sha256=hashlib.sha256(a.original_zip.read_bytes()).hexdigest())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
