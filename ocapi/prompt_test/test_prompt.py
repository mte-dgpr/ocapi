#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import json
from pathlib import Path

from langchain_core.documents import Document

from ocapi.constants import DEFAULT_LLM_MODEL
from ocapi.prompt_test.working_prompt import working_prompt
from ocapi.types import ArreteId, ImageMap
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, parse_llm_json_list_response


def get_llm_output(html_block: Document, modele: str) -> list[dict]:
    """Retourne la sortie brute du LLM (liste de dicts), sans validation."""
    cfg = config_model_llm(modele)
    raw = call_llm_api(cfg, working_prompt(html_block))
    raw_list = parse_llm_json_list_response(raw)
    return raw_list  # Retourner tel quel, pas de validation


if __name__ == "__main__":
    input_dir = Path(__file__).resolve().parents[2] / "ocapi" / "prompt_test" / "blocs_test"
    output_dir = Path(__file__).resolve().parents[2] / "ocapi" / "prompt_test" / "llm_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("🚀 Test du prompt sur tous les blocs...")

    for html_file in sorted(input_dir.glob("**/*.html")):
        print(f"\n📄 {html_file.relative_to(input_dir)}")

        with html_file.open("r", encoding="utf-8") as f:
            html_content = f.read()

        doc = Document(page_content=html_content)

        try:
            raw_ops = get_llm_output(doc, DEFAULT_LLM_MODEL)
            print(f"   ✓ {len(raw_ops)} opérations détectées")

            # Sauvegarder la sortie brute
            output_path = output_dir / f"{html_file.stem}_llm_output.json"
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(raw_ops, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            continue

    print(f"\n✅ Sorties LLM sauvegardées dans {output_dir}")
