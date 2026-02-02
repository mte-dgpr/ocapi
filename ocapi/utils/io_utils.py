import json
from pathlib import Path
from typing import Any, cast


def read_json(p: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))
