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


from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, Operation


def has_no_ops(arrete_file: ArreteFile, operations: list[Operation]) -> bool:
    for op in operations:
        if op.source_id.arrete_id == arrete_file.id:
            return False
    return True


def detect_additional_prescriptions(arrete_files: list[ArreteFile]) -> str:
    # TODO : refaire des appels LLM pour détecter les prescriptions
    # additionnelles non modificatives ? à voir.
    return ""


def extract_main(soup: BeautifulSoup) -> str:
    main = soup.find("main")
    if main is None:
        return ""
    return str(main)


def make_other_permis(arrete_files: list[ArreteFile], operations: list[Operation]) -> str:
    other_str = ""
    for i, arrete_file in enumerate(arrete_files):
        if i > 0:  # Skip first file (AP initial)
            if arrete_file.status and has_no_ops(arrete_file, operations):
                main_content = extract_main(arrete_file.soup)
                other_str += (
                    f"Contenu de l'arrêté complémentaire {arrete_file.id} : " f"{main_content}"
                )
    return other_str
