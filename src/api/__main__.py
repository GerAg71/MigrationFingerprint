"""Generate the OpenAPI companion artifact (spec §18.2):
python -m src.api  ->  docs/openapi.json"""

import json
from pathlib import Path

from src.api.app import create_app

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app().openapi()
    target.write_bytes(
        (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"wrote {target} ({len(schema['paths'])} paths)")
