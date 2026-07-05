"""Shared helpers for the rule-engine tests (MS-1.4)."""

import json
from pathlib import Path

import pandas as pd

from src.fingerprint.models import DetectionRuleAdapter, Fingerprint
from src.rules.engine import RuleDatasets

REPO = Path(__file__).resolve().parents[1]
SEED_FILE = REPO / "data" / "fingerprints" / "omni-zos-to-omni-linux" / "1.0.0" / "fingerprint.json"


def make_rule(payload: dict):
    return DetectionRuleAdapter.validate_python(payload)


def make_datasets(dataset_name: str, source_rows: list[dict],
                  target_rows: list[dict]) -> RuleDatasets:
    return RuleDatasets(
        source={dataset_name: pd.DataFrame(source_rows, dtype=object)},
        target={dataset_name: pd.DataFrame(target_rows, dtype=object)},
    )


def load_seed_rules() -> dict:
    fp = Fingerprint.model_validate(json.loads(SEED_FILE.read_text(encoding="utf-8")))
    return {r.rule_id: r for r in fp.detection_rules}
