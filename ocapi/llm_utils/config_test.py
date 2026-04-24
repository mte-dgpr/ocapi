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
from unittest.mock import patch

from ocapi.llm_utils import config_model_llm


def test_config_model_llm_uses_primary_and_secondary_keys() -> None:
    models_cfg = {
        "primary_model_key": "openai_primary",
        "secondary_model_key": "mistral_secondary",
        "models": {
            "openai_primary": {"provider": "openai", "model_id": "gpt-5"},
            "mistral_secondary": {
                "provider": "mte-piag",
                "model_id": "mte-api-piag-mistral-medium-latest",
            },
        },
    }

    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=models_cfg):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            side_effect=[
                ("openai-key", "https://openai.example"),
                ("piag-key", "https://piag.example"),
            ],
        ):
            primary = config_model_llm()
            secondary = config_model_llm("secondary")

    assert primary.provider == "openai"
    assert primary.model_name == "gpt-5"
    assert secondary.provider == "mte-piag"
    assert secondary.model_name == "mte-api-piag-mistral-medium-latest"
