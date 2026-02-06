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
"""
Module de catégorisation des arrêtés préfectoraux.

La catégorisation est basée sur le nom du fichier et suit les règles suivantes:

Catégories et correspondances:

    AP_AUTORISATION:
        - "ap d'autorisation"
        - "ap enregistrement"
        - "ap autorisation temporaire"

    ARRETE_PREFECTORAL:
        - "arrêté préfectoral"
        - "ap servitude d'utilité publique"

    AP_COMPLEMENTAIRE:
        - "ap prescriptions complémentaires"

    AUTRE:
        - Tout autre type non reconnu

Utilisation:
    >>> from ocapi.types import parse_filename, categorize_arrete, FileType
    >>>
    >>> # Parser un nom de fichier complet
    >>> arrete_id, file_type = parse_filename("2009-12-08_ap d'autorisation_details.html")
    >>> print(arrete_id)  # "2009-12-08"
    >>> print(file_type)  # FileType.AP_AUTORISATION
    >>>
    >>> # Catégoriser directement un fichier
    >>> file_type = categorize_arrete("2014-01-09_ap prescriptions complémentaires_mod.html")
    >>> print(file_type)  # FileType.AP_COMPLEMENTAIRE

Notes:
    - La fonction parse_filename() valide également le format de la date et l'extension .html
    - La catégorisation est insensible à la casse
    - L'ordre de matching est du plus spécifique au plus général pour éviter les faux positifs
"""

from .types import FileType, categorize_arrete, parse_filename

__all__ = ["FileType", "categorize_arrete", "parse_filename"]
