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
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, TypedDict

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, field_validator

OperationId = str
ArreteId = str
ArticleId = str
Content = str
AiotId = str
ImageMap = Dict[str, str]  # mapping token -> original src


@dataclass
class ArreteFile:
    """Représente un arrêté avec son ID et son contenu."""

    id: ArreteId
    aiot: AiotId
    ordered_index: int
    filename: str
    soup: BeautifulSoup
    status: bool = True


class Permis(BaseModel):
    header: str
    contenu: str
    other: str
    aiot: AiotId | None = None
    
    def to_html(self) -> str:
        """Concatène le header, le contenu et other pour générer le HTML complet du permis."""
        return f"<!DOCTYPE html>\n<html lang=\"fr\">\n{self.header}\n{self.contenu}\n{self.other}\n</html>"


class NodeId(BaseModel):
    """Identifiant unique d'un nœud composé de l'ID de l'arrêté et de l'ID de l'article"""

    model_config = ConfigDict(extra="forbid")

    arrete_id: ArreteId
    article_id: ArticleId

    @field_validator('article_id')
    @classmethod
    def validate_article_id_format(cls, v: str) -> str:
        """Valide que l'article_id est au format numérique (ex: '1.2', '3.1.4'), APPENDIX, ALL ou END"""
        # Accepter les valeurs spéciales
        if v in ("ALL", "END") or v.startswith("APPENDIX") or v.startswith("NEW_ARTICLE:"):
            return v
        # Sinon, vérifier le format numérique
        if not re.match(r'^\d+(\.\d+)*$', v):
            raise ValueError(f"article_id doit être au format numérique (ex: '1.2', '3.1.4'), APPENDIX, ALL, END ou NEW_ARTICLE:X, reçu: '{v}'")
        return v
    
    @field_validator('arrete_id')
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        """Valide que l'arrete_id est au format YYYY-MM-DD"""
        parts = v.split('-')
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError(f"Date invalide dans arrete_id: '{v}'")
        return v
    
    def __str__(self) -> str:
        return f"{self.arrete_id}#{self.article_id}"
    
    def __hash__(self) -> int:
        return hash((self.arrete_id, self.article_id))   

class ArticleVersion(TypedDict):
    version: int
    content: Content
    operation_id: str | None

ArticleHistory = Dict[NodeId, list[ArticleVersion]]


class OperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"


class RawOperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    AUTRE = "AUTRE"


class _BaseModelWithConfig(BaseModel):
    """
    Base class for models with strict extra handling.
    """

    model_config = ConfigDict(extra="forbid")


class RawOperation(_BaseModelWithConfig):
    operation_type: RawOperationType
    source_article: str | None = None
    target_arrete: str
    target_article: str | None = None
    sub_target: str | None = None
    new_content_start_marker: str | None = None
    new_content_end_marker: str | None = None
    failure_message: str | None = None


class SubTargetType(Enum):
    """Types de sub-targets détectables."""

    FULL_SECTION = "FULL_SECTION"
    TABLEAU = "TABLEAU"
    PHRASE = "PHRASE"
    ALINEA = "ALINEA"
    PARAGRAPHE = "PARAGRAPHE"
    LIGNE_TABLEAU = "LIGNE_TABLEAU"
    COLONNE_TABLEAU = "COLONNE_TABLEAU"  # Ligne et colonne à supprimer si mauvaise détection ?
    COMPLEX = "COMPLEX"  # Nécessite LLM


class SubTarget(_BaseModelWithConfig):
    """Représente un sub-target parsé."""

    type: SubTargetType
    position: Optional[int] = None  # 0 = dernière, 1 = première, 2 = deuxième, etc.
    description: Optional[str] = None  # Texte original du sub-target

    @field_validator("type", mode="before")
    @classmethod
    def _ensure_subtarget_type(cls, v: SubTargetType | str) -> SubTargetType:
        return v if isinstance(v, SubTargetType) else SubTargetType(v)

    def __repr__(self) -> str:
        type_val = self.type.value if isinstance(self.type, SubTargetType) else self.type
        return f"SubTarget({type_val}, pos={self.position})"


class Operation(_BaseModelWithConfig):
    # TODO : conserver ref vers arrete source et index qui incrémente
    # pour chaque tgt identique dans cet arrete
    id: OperationId
    source_id: NodeId
    target_id: NodeId
    operation_type: OperationType
    operand: str | None = None
    sub_target: SubTarget | None = None

    @field_validator("operation_type", mode="before")
    @classmethod
    def _ensure_operation_type(cls, v: OperationType | str) -> OperationType:
        return v if isinstance(v, OperationType) else OperationType(v)
