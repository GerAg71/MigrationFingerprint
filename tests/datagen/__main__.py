"""Regenerate data/samples deterministically: python -m tests.datagen"""

from pathlib import Path

from tests.datagen.writer import write_samples

if __name__ == "__main__":
    samples = Path(__file__).resolve().parents[2] / "data" / "samples"
    write_samples(samples)
    print(f"regenerated {samples}")
