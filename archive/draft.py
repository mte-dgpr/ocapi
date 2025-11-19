import json
from pathlib import Path
input_dir = Path(__file__).resolve().parents[1] / "archive" 



path = input_dir / "modifications_detectees_articles.json"
ops = json.loads(path.read_text(encoding="utf-8"))
for op in ops:
    print(op.get("target_element"))