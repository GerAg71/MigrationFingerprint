"""Deterministic synthetic sample-data generator (MS-1.6; spec Ch. 25).

Absolute rule (REQ-031): no real participant data — fake SSNs (900-xx range),
fake names, small plans. Fixed RNG seed in the repo; regeneration is
byte-identical, which the test suite asserts against the committed files.
"""

from tests.datagen.truth import SEED, build_truth
from tests.datagen.mutators import SEEDED_DEFECTS, apply_mutations
from tests.datagen.writer import write_pair

__all__ = ["SEED", "SEEDED_DEFECTS", "apply_mutations", "build_truth", "write_pair"]
