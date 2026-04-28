#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
"""Mock LLM for snapshot tests (no real API calls)."""


def _extract_target_content_from_prompt(prompt: str) -> str:
    """Return the article HTML block embedded in a sub-target LLM prompt."""
    if "Dans le texte suivant :" not in prompt:
        return prompt
    after_header = prompt.split("Dans le texte suivant :", 1)[1]
    parts = after_header.split("\n\n")
    return parts[1].strip() if len(parts) > 1 else after_header.strip()


def mock_call_llm_api_for_subtarget(cfg: object, prompt: str) -> str:
    """Mock LLM for snapshot tests: returns ``target_content`` unchanged (no real API).

    For COMPLEX sub-targets the production pipeline does not call the LLM yet;
    when this mock is used, it still returns the embedded ``target_content`` only.
    """
    return _extract_target_content_from_prompt(prompt)
