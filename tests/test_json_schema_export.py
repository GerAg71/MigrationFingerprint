"""MS-1.1 done-when: JSON Schema export works for every entity."""

import json

from src.fingerprint.models import export_json_schemas, write_json_schemas

EXPECTED = {
    "PlatformPair", "Fingerprint", "FailureMode", "DetectionRule",
    "ConversionRun", "SuiteItem", "PrioritizedSuiteEntry", "Finding",
    "FindingsReport", "LayoutSpec",
}


def test_export_covers_all_entities():
    schemas = export_json_schemas()
    assert set(schemas) == EXPECTED


def test_schemas_are_json_serializable_objects():
    for name, schema in export_json_schemas().items():
        text = json.dumps(schema)  # must not raise
        assert isinstance(schema, dict), name
        assert text


def test_detection_rule_schema_is_discriminated_union():
    schema = export_json_schemas()["DetectionRule"]
    assert "discriminator" in schema or "oneOf" in schema or "anyOf" in schema
    defs = schema.get("$defs", {})
    assert {"FieldCompareRule", "CountBalanceRule", "ReferentialRule",
            "DerivedRecomputeRule", "EncodingCheckRule", "SortOrderCheckRule"} <= set(defs)


def test_fingerprint_schema_mentions_extensions():
    """The CLI_SPEC schema extensions must be visible in the exported schema."""
    defs = export_json_schemas()["Fingerprint"]["$defs"]
    assert "sample_defect" in defs["FailureMode"]["properties"]
    assert "gte_field" in defs["ValidityCheck"]["properties"]
    assert "custom_set" in defs["EncodingCheckParams"]["properties"]


def test_write_json_schemas(tmp_path):
    written = write_json_schemas(tmp_path / "schemas")
    assert len(written) == len(EXPECTED)
    for path in written:
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))
