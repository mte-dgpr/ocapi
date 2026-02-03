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
from datetime import datetime
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
    filename: str
    soup: BeautifulSoup
    file_type: "FileType"
    status: bool = True


class Permis(BaseModel):
    header: str
    contenu: str
    other: str
    aiot: AiotId | None = None

    def to_html(self) -> str:
        """Concatène le header, le contenu et other pour générer le HTML complet du permis."""
        return (
            f'<!DOCTYPE html>\n<html lang="fr">\n'
            f"{self.header}\n{self.contenu}\n{self.other}\n</html>"
        )


class NodeId(BaseModel):
    """Identifiant unique d'un nœud composé de l'ID de l'arrêté et de l'ID de l'article"""

    model_config = ConfigDict(extra="forbid")

    arrete_id: ArreteId
    article_id: ArticleId

    @field_validator("article_id")
    @classmethod
    def validate_article_id_format(cls, v: str) -> str:
        """
        Valide que l'article_id est au format numérique (ex: '1.2', '3.1.4'),
        APPENDIX, ALL ou END
        """
        # Accepter les valeurs spéciales
        if v in ("ALL", "END") or v.startswith("APPENDIX") or v.startswith("NEW_ARTICLE:"):
            return v
        # Sinon, vérifier le format numérique
        if not re.match(r"^\d+(\.\d+)*$", v):
            msg = (
                "article_id doit être au format numérique (ex: '1.2', '3.1.4'), "
                f"APPENDIX, ALL, END ou NEW_ARTICLE:X, reçu: '{v}'"
            )
            raise ValueError(msg)
        return v

    @field_validator("arrete_id")
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        """Valide que l'arrete_id est au format YYYY-MM-DD"""
        parts = v.split("-")
        month, day = int(parts[1]), int(parts[2])
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


ArticlesContentMap = Dict[NodeId, Content]
ArticleHistory = Dict[NodeId, list[ArticleVersion]]


class FileType(Enum):
    """Types de fichiers d'arrêtés reconnus."""

    AP_AUTORISATION = "ap d'autorisation"
    AP_PRESCRIPTIONS_COMPLEMENTAIRES = "ap prescriptions complémentaires"
    ARRETE_PREFECTORAL = "arrêté préfectoral"
    AUTRE = "autre"


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


def parse_filename(filename: str) -> tuple[ArreteId, FileType]:
    """
    Parse le nom de fichier au format Arrêtify et extrait la date et le type de fichier.

    Format attendu: YYYY-MM-DD_type-fichier_nom.html

    Args:
        filename: Nom du fichier à parser

    Returns:
        Tuple (arrete_id, file_type) où arrete_id est au format YYYY-MM-DD
        et file_type est l'enum correspondant

    Raises:
        ValueError: Si le format du nom de fichier est invalide
    """
    # Retirer l'extension .html
    if not filename.endswith(".html"):
        raise ValueError(f"Le fichier doit avoir l'extension .html: {filename}")

    stem = filename[:-5]  # Retirer .html

    # Parser le format: YYYY-MM-DD_type-fichier_nom
    parts = stem.split("_")

    if len(parts) < 2:
        raise ValueError(
            f"Format invalide, attendu: YYYY-MM-DD_type-fichier_nom.html, reçu: {filename}"
        )

    # Extraire et valider la date (première partie)
    date_str = parts[0]
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"

    if not re.match(date_pattern, date_str):
        raise ValueError(f"Date invalide dans le nom de fichier (attendu: YYYY-MM-DD): {filename}")

    # Valider que c'est une date valide
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Date invalide dans le nom de fichier: {filename}") from e

    arrete_id = date_str

    # Extraire le type de fichier (deuxième partie)
    file_type_str = parts[1].lower().strip()

    # Mapper les variantes courantes
    file_type_mapping = {
        "ap d'autorisation": FileType.AP_AUTORISATION,
        "ap prescriptions complémentaires": FileType.AP_PRESCRIPTIONS_COMPLEMENTAIRES,
        "arrêté préfectoral": FileType.ARRETE_PREFECTORAL,
        "apc": FileType.AP_PRESCRIPTIONS_COMPLEMENTAIRES,
        "ap": FileType.ARRETE_PREFECTORAL,
    }

    # Chercher une correspondance exacte d'abord
    file_type = file_type_mapping.get(file_type_str)

    if file_type is None:
        # Essayer de trouver une correspondance partielle
        for key, value in file_type_mapping.items():
            if file_type_str.startswith(key):
                file_type = value
                break

    if file_type is None:
        file_type = FileType.AUTRE

    return arrete_id, file_type
