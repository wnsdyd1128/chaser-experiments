#!/usr/bin/env python3
"""Predict scheduling architecture with the RTEMS ML saved model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LABEL_NAMES = {0: "Global", 1: "Clustered", 2: "Partitioned"}
FEATURES = [
    "ca_mean", "ca_std", "ca_min", "ca_max", "ca_median",
    "u_mean", "u_std", "u_min", "u_max", "u_median", "u_sum",
]


def feature_row(tasks: list[dict]) -> dict[str, float]:
    import numpy as np

    ca_values = np.array([task["CA"] for task in tasks], dtype=float)
    u_values = np.array([task["U"] for task in tasks], dtype=float)
    return {
        "ca_mean": float(np.mean(ca_values)),
        "ca_std": float(np.std(ca_values)),
        "ca_min": float(np.min(ca_values)),
        "ca_max": float(np.max(ca_values)),
        "ca_median": float(np.median(ca_values)),
        "u_mean": float(np.mean(u_values)),
        "u_std": float(np.std(u_values)),
        "u_min": float(np.min(u_values)),
        "u_max": float(np.max(u_values)),
        "u_median": float(np.median(u_values)),
        "u_sum": float(np.sum(u_values)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="JSON from build_ml_dataset.py")
    parser.add_argument("--framework",
                        default="/workspace/caas/MEM_RD_IR/rtems-ml-framework")
    parser.add_argument("--model", choices=["randomforest", "xgboost"],
                        default="randomforest")
    args = parser.parse_args()

    framework = Path(args.framework)
    sys.path.insert(0, str(framework))

    import joblib
    import pandas as pd

    model_path = framework / "examples" / "saved_models" / f"{args.model}_model.pkl"
    model = joblib.load(model_path)
    samples = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    rows = [feature_row(sample["tasks"]) for sample in samples]
    predictions = model.predict(pd.DataFrame(rows, columns=FEATURES))

    for idx, pred in enumerate(predictions):
        label = int(pred)
        print(f"PREDICT,index={idx},label={label},architecture={LABEL_NAMES[label]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
