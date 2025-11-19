"""
Détermine le sub-target à partir d'un texte descriptif et d'un contexte HTML.

D'abord on teste des patterns regex simples pour détecter des sub-targets courants.
Si le fichier utils subtarget_detection ne suffit pas à détecter le sub-target,
utiliser un LLM pour une détection plus avancée.
"""

import re
from typing import Optional, Dict, Any
from permis.scripts.utils.subtarget_detection import detect_subtarget, SubTargetType, SubTarget
from permis.scripts.constants import FULL_SECTION
from permis.scripts.utils.llm_utils import query_llm_for_subtarget