"""MS-1.7 (spec Ch. 24.5, Appendix B): the Phase-1 coverage audit.

- Every implemented rule type has a golden fixture dataset under
  tests/fixtures/rules/<type>/ that trips it, exercised end-to-end through
  ingestion (REQ-011, REQ-023, Ch. 24.5).
- Every implemented rule-type executor carries a docstring naming the
  failure modes it serves (Ch. 24.5).
- REQ-015 perf smoke: a 200-participant plan through the full 18-mode suite
  completes locally in well under 60 seconds.
"""

import time
from pathlib import Path

import pytest

from src.ingest.registration import RegistrationIndex, register_dataset
from src.rules import EXECUTORS, RuleDatasets, execute
from src.runner.run import run
from tests.conftest import REPO, load_seed_rules
from tests.datagen.mutators import apply_mutations
from tests.datagen.truth import build_truth
from tests.datagen.writer import write_dataset

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rules"
RUN_ID = "RUN-2026-07-05-0001"

# one golden tripping fixture per implemented rule type (Ch. 24.5)
TYPE_FIXTURES = [
    ("field_compare", "RULE-LOAN-BAL-001", "loans"),
    ("count_balance", "RULE-BAL-MT-001", "balances"),
    ("referential", "RULE-DUP-001", "participants"),
    ("derived_recompute", "RULE-VEST-PCT-001", "vesting"),
    ("encoding_check", "RULE-ENC-001", "participants"),
    ("sort_order_check", "RULE-SORT-001", "participants"),
]


@pytest.mark.parametrize("rule_type,rule_id,dataset", TYPE_FIXTURES)
def test_every_rule_type_has_a_tripping_fixture(rule_type, rule_id, dataset):
    """Golden fixture -> ingest -> execute -> the rule fires."""
    fixture_dir = FIXTURES / rule_type
    index = RegistrationIndex()
    for side in ("source", "target"):
        index.add(register_dataset(
            fixture_dir / f"{side}_{dataset}.csv",
            run_id=RUN_ID, side=side, dataset_name=dataset,
        ))
    rule = load_seed_rules()[rule_id]
    assert rule.type == rule_type
    assert index.missing_for_rule(rule) == []
    outcome = execute(rule, RuleDatasets.from_index(index))
    assert not outcome.passed, f"{rule_type} fixture must trip {rule_id}"
    assert outcome.records_affected >= 1


def test_fixture_coverage_matches_implemented_executors():
    """A new executor without a golden fixture fails this audit."""
    assert {t for t, _, _ in TYPE_FIXTURES} == set(EXECUTORS)


def test_every_executor_docstring_names_its_failure_modes():
    """Ch. 24.5: docstring names the failure mode(s) the rule type serves."""
    import src.rules.count_balance
    import src.rules.derived_recompute
    import src.rules.encoding_check
    import src.rules.field_compare
    import src.rules.referential
    import src.rules.sort_order_check

    for module in (src.rules.field_compare, src.rules.count_balance,
                   src.rules.referential, src.rules.derived_recompute,
                   src.rules.encoding_check, src.rules.sort_order_check):
        assert module.__doc__ and "FM-0" in module.__doc__, module.__name__


def test_perf_smoke_200_participants_under_60s(tmp_path):
    """REQ-015: 200-participant plan, full 18-mode suite, <= 60 s locally.
    Generation time is excluded — the envelope is about the run."""
    truth = build_truth("PLN-PERF-01", participants_n=200)
    import copy
    target = copy.deepcopy(truth)
    apply_mutations(target)
    source_dir, target_dir = tmp_path / "source", tmp_path / "target"
    for dataset, rows in truth.items():
        write_dataset(source_dir / f"{dataset}.csv", dataset, rows)
    for dataset, rows in target.items():
        write_dataset(target_dir / f"{dataset}.csv", dataset, rows)

    started = time.perf_counter()
    result = run(
        "omni-zos-to-omni-linux", source_dir, target_dir,
        fingerprint_dir=REPO / "data" / "fingerprints",
        runs_dir=tmp_path / "runs", run_id=RUN_ID,
    )
    elapsed = time.perf_counter() - started

    assert result.report.run.summary.rules_run == 23
    assert len(result.findings) == 21  # same manifest shape at 200 participants
    assert elapsed < 60, f"REQ-015 envelope exceeded: {elapsed:.1f}s"
