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
from ocapi.llm_utils.config import (
    ConfidenceScoreConfig,
    ResolvedLLMModel,
    config_model_llm,
    get_confidence_score_config,
)
from ocapi.llm_utils.core import (
    TokenUsage,
    call_llm_api,
    get_accumulated_usage,
    reset_accumulated_usage,
)
from ocapi.llm_utils.prompts import (
    parse_llm_json_list_response,
    prompt_detection,
    query_llm_for_subtarget,
)

__all__ = [
    "ConfidenceScoreConfig",
    "ResolvedLLMModel",
    "TokenUsage",
    "call_llm_api",
    "config_model_llm",
    "get_accumulated_usage",
    "get_confidence_score_config",
    "parse_llm_json_list_response",
    "prompt_detection",
    "query_llm_for_subtarget",
    "reset_accumulated_usage",
]
