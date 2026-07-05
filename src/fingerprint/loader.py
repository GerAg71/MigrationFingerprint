"""Fingerprint loading and version selection (MS-1.2; spec §5.2).

POC storage layout: data/fingerprints/{pair_id}/{version}/fingerprint.json.
Loading always schema-validates; invalid files are rejected with pathed
pydantic errors (REQ-010) — never silently skipped or partially loaded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.fingerprint.models import Fingerprint

DEFAULT_FINGERPRINT_DIR = Path("data") / "fingerprints"
FINGERPRINT_FILENAME = "fingerprint.json"

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class FingerprintDirectoryError(Exception):
    """Consistency fault in the fingerprint store: wrong directory layout,
    pair/version disagreement between file and path, or no published version.

    Distinct from pydantic ValidationError (schema faults inside a file);
    both are validation-gate refusals (CLI exit 3)."""


def _semver_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def list_versions(
    pair_id: str, fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR
) -> list[str]:
    """All version directories for a pair, ascending by semver (not lexically:
    1.10.0 sorts above 1.9.0)."""
    pair_dir = Path(fingerprint_dir) / pair_id
    if not pair_dir.is_dir():
        raise FileNotFoundError(
            f"no fingerprints for pair {pair_id!r} under {fingerprint_dir}"
        )
    versions = sorted(
        (d.name for d in pair_dir.iterdir() if d.is_dir() and _SEMVER_RE.match(d.name)),
        key=_semver_key,
    )
    if not versions:
        raise FileNotFoundError(
            f"pair {pair_id!r} has no version directories under {pair_dir}"
        )
    return versions


def load_file(path: Path | str) -> Fingerprint:
    """Schema-validate one fingerprint file. Raises FileNotFoundError,
    json.JSONDecodeError, or pydantic.ValidationError (pathed, REQ-010)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"fingerprint file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Fingerprint.model_validate(payload)


def _file_status(path: Path) -> str | None:
    """Peek a fingerprint file's lifecycle status without full validation."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = payload.get("status")
    return status if isinstance(status, str) else None


def load(
    pair_id: str,
    version: str | None = None,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
) -> Fingerprint:
    """Load a pair's fingerprint, defaulting to the highest published version.

    An explicit version pin loads that version regardless of lifecycle status
    (runs may pin drafts or superseded versions; spec §14.5 keeps them loadable
    forever). The file's fingerprint_id and version must agree with its
    directory path — disagreement is a store fault, raised loudly.
    """
    fingerprint_dir = Path(fingerprint_dir)
    if version is None:
        published = [
            v
            for v in list_versions(pair_id, fingerprint_dir)
            if (fingerprint_dir / pair_id / v / FINGERPRINT_FILENAME).is_file()
            and _file_status(fingerprint_dir / pair_id / v / FINGERPRINT_FILENAME)
            == "published"
        ]
        if not published:
            raise FingerprintDirectoryError(
                f"pair {pair_id!r} has no published fingerprint version; "
                "pass an explicit version to load a draft"
            )
        version = published[-1]

    path = fingerprint_dir / pair_id / version / FINGERPRINT_FILENAME
    fingerprint = load_file(path)

    if fingerprint.fingerprint_id != pair_id:
        raise FingerprintDirectoryError(
            f"{path}: fingerprint_id {fingerprint.fingerprint_id!r} does not match "
            f"pair directory {pair_id!r}"
        )
    if fingerprint.version != version:
        raise FingerprintDirectoryError(
            f"{path}: file version {fingerprint.version!r} does not match "
            f"version directory {version!r}"
        )
    return fingerprint
