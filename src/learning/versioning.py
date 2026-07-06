"""Fingerprint versioning (MS-2.4; spec §14.4–14.6, REQ-028).

Semver policy: patch = probability/history write-backs; minor = added modes
or rules; major = schema or incompatible rule changes. Published versions
are immutable — publish writes a NEW version directory and never touches
prior ones; superseded versions remain loadable forever (REQ-028).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.fingerprint.loader import DEFAULT_FINGERPRINT_DIR, load, load_file
from src.fingerprint.models import DetectionRuleAdapter, FailureMode, Fingerprint
from src.learning.writeback import bump_version, draft_path, _dump_json_bytes


class PublishError(Exception):
    pass


def diff_fingerprints(old: Fingerprint, new: Fingerprint) -> dict:
    """Mode-level diff (spec §14.5): added/removed modes and rules,
    probability deltas, counter and remediation changes."""
    old_modes = {m.id: m for m in old.failure_modes}
    new_modes = {m.id: m for m in new.failure_modes}
    old_rules = {r.rule_id for r in old.detection_rules}
    new_rules = {r.rule_id for r in new.detection_rules}

    changed = []
    for fm_id in sorted(set(old_modes) & set(new_modes)):
        before, after = old_modes[fm_id], new_modes[fm_id]
        entry: dict = {"fm_id": fm_id}
        if before.probability != after.probability:
            entry["probability"] = {
                "before": before.probability, "after": after.probability,
                "delta": round(after.probability - before.probability, 3),
            }
        if before.history != after.history:
            entry["counters"] = {
                "before": before.history.model_dump(),
                "after": after.history.model_dump(),
            }
        rules_added = sorted(set(after.detection_rules) - set(before.detection_rules))
        rules_removed = sorted(set(before.detection_rules) - set(after.detection_rules))
        if rules_added:
            entry["rules_added"] = rules_added
        if rules_removed:
            entry["rules_removed"] = rules_removed
        if before.remediation != after.remediation:
            entry["remediation_changed"] = True
        if len(entry) > 1:
            changed.append(entry)

    return {
        "modes_added": sorted(set(new_modes) - set(old_modes)),
        "modes_removed": sorted(set(old_modes) - set(new_modes)),
        "rules_added": sorted(new_rules - old_rules),
        "rules_removed": sorted(old_rules - new_rules),
        "modes_changed": changed,
    }


@dataclass
class PublishResult:
    old_version: str
    new_version: str
    diff: dict
    path: Path


def publish_draft(
    pair_id: str,
    bump: str,
    *,
    changelog: str | None = None,
    publisher: str = "site_admin",
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
    now: datetime | None = None,
) -> PublishResult:
    """Finalize the pair's draft into a new immutable published version
    (spec §14.5–14.6). The draft directory is consumed; prior versions are
    never modified (REQ-028)."""
    fingerprint_dir = Path(fingerprint_dir)
    path = draft_path(pair_id, fingerprint_dir)
    if not path.is_file():
        raise PublishError(
            f"pair {pair_id!r} has no draft to publish — reviews and "
            f"author-mode create one"
        )
    draft = load_file(path)
    base = load(pair_id, fingerprint_dir=fingerprint_dir)  # latest published
    new_version = bump_version(base.version, bump)

    draft.version = new_version
    draft.status = "published"
    draft.updated_at = now or datetime.now(timezone.utc)
    draft.updated_by = publisher
    if changelog:
        draft.changelog = changelog

    published = Fingerprint.model_validate(draft.model_dump(mode="json"))
    target = fingerprint_dir / pair_id / new_version / "fingerprint.json"
    if target.exists():
        raise PublishError(f"version {new_version} already exists at {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_dump_json_bytes(published.model_dump(mode="json")))

    path.unlink()
    try:
        path.parent.rmdir()
    except OSError:
        pass  # leftover files in draft dir are fine to keep

    return PublishResult(
        old_version=base.version, new_version=new_version,
        diff=diff_fingerprints(base, published), path=target,
    )


def diff_versions(
    pair_id: str, version_from: str, version_to: str,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
) -> dict:
    old = load(pair_id, version_from, fingerprint_dir)
    new = load(pair_id, version_to, fingerprint_dir)
    return diff_fingerprints(old, new)


def next_fm_id(fingerprint: Fingerprint) -> str:
    highest = max(int(m.id.split("-")[1]) for m in fingerprint.failure_modes)
    return f"FM-{highest + 1:03d}"


def author_failure_mode(
    pair_id: str,
    *,
    name: str,
    category: str,
    description: str,
    data_domains: list[str],
    impact: float,
    remediation: str,
    rule_payload: dict,
    probability: float = 0.30,
    fingerprint_dir: Path | str = DEFAULT_FINGERPRINT_DIR,
) -> FailureMode:
    """Append a new failure mode + rule to the pair's draft (spec §14.4).
    Learned modes default to probability 0.30; the whole draft is
    schema-validated before it is written (REQ-010)."""
    from src.learning.writeback import load_or_create_draft, save_draft

    draft = load_or_create_draft(pair_id, fingerprint_dir)
    fm_id = next_fm_id(draft)
    rule = DetectionRuleAdapter.validate_python(
        {**rule_payload, "failure_mode": fm_id})
    mode = FailureMode(
        id=fm_id, name=name, category=category, description=description,
        probability=probability, impact=impact,
        data_domains=data_domains, detection_rules=[rule.rule_id],
        remediation=remediation, origin="learned",
        seed_probability=probability,
    )
    draft.failure_modes.append(mode)
    draft.detection_rules.append(rule)
    validated = Fingerprint.model_validate(draft.model_dump(mode="json"))
    save_draft(validated, pair_id, fingerprint_dir)
    return mode
