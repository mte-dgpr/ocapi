import json
from pathlib import Path
from typing import Any


def read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

