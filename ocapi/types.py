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
from typing import Dict, Literal, Optional, TypedDict

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, field_validator
from typing_extensions import NotRequired

from .config import SUPPORTED_ARRETIFY_VERSION, SUPPORTED_ARRETIFY_VERSION_PATTERN, settings

OperationId = str
ArreteId = str
ArticleId = str
Content = str
AiotId = str
ImageMap = Dict[str, str]  # mapping token -> original src


def is_valid_article_id(article_id: str) -> bool:
    """Vérifie si un article_id est au format valide pour NodeId."""
    if (
        article_id in ("ALL", "END")
        or article_id.startswith("APPENDIX")
        or article_id.startswith("NEW_ARTICLE:")
    ):
        return True
    return bool(re.match(r"^\d+(\.\d+)*$", article_id))


@dataclass
class ArreteFile:
    """Représente un arrêté avec son ID et son contenu."""

    id: ArreteId
    aiot: AiotId
    filename: str
    soup: BeautifulSoup
    file_type: "FileType | None" = None
    status: bool = True


class Permis(BaseModel):
    header: str
    contenu: str
    other: str
    aiot: AiotId | None = None

    def to_html(self) -> str:
        """Rend le permis dans le template HTML fixe."""
        template_path = settings.paths.permis_template_path
        template = template_path.read_text(encoding="utf-8")
        required_tokens = ("{{HEADER}}", "{{CONTENT}}", "{{OTHER}}")
        if not all(token in template for token in required_tokens):
            raise ValueError(
                "Template HTML du permis consolidé invalide: "
                "placeholders {{HEADER}}, {{CONTENT}} et {{OTHER}} requis."
            )
        return (
            template.replace("{{HEADER}}", self.header)
            .replace("{{CONTENT}}", self.contenu)
            .replace("{{OTHER}}", self.other)
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
        if not is_valid_article_id(v):
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
    status_code: NotRequired[Literal["RESOLVED", "ERROR_EXTRACTING_CONTENT"]]


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


class FileType(Enum):
    """Type de fichier d'arrêté préfectoral."""

    AP_AUTORISATION = "ap d'autorisation"
    AP_COMPLEMENTAIRE = "ap prescriptions complémentaires"
    ARRETE_PREFECTORAL = "arrêté préfectoral"
    AUTRE = "autre"


class _BaseModelWithConfig(BaseModel):
    """
    Base class for models with strict extra handling.
    """

    model_config = ConfigDict(extra="forbid")


class PermitTitleSpec(_BaseModelWithConfig):
    """Titre du permis consolidé avec un unique code AIOT."""

    aiot_code: AiotId | None


class PermitSourceSpec(_BaseModelWithConfig):
    """Source utilisée dans le permis (date + titre d'arrêté)."""

    arrete_id: ArreteId
    arrete_title: str
    status: bool = True


class PermitSources(_BaseModelWithConfig):
    """Liste des arrêtés sources triés chronologiquement."""

    sources: list[PermitSourceSpec]


class PermitVisa(_BaseModelWithConfig):
    """Ensemble ordonné des VisaSpec consolidés sans doublon."""

    visas: list[str]


class PermitMotifEntry(_BaseModelWithConfig):
    """Motifs extraits pour un arrêté donné."""

    arrete_id: ArreteId
    motifs: list[str]


class PermitMotif(_BaseModelWithConfig):
    """Motifs consolidés, groupés par arrêté en ordre chronologique."""

    entries: list[PermitMotifEntry]


class SectionVersionSpec(_BaseModelWithConfig):
    """Version consolidée d'une section avec métadonnées de modification."""

    article_id: ArticleId
    is_modified: bool
    date_version: ArreteId
    content: str


class PermitComplements(_BaseModelWithConfig):
    """Mains des AP spécifiques non consolidés."""

    complements: list[str]


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
    extractable_content: bool = True

    @field_validator("operation_type", mode="before")
    @classmethod
    def _ensure_operation_type(cls, v: OperationType | str) -> OperationType:
        return v if isinstance(v, OperationType) else OperationType(v)


def categorize_arrete(filename: str) -> FileType:
    """
    Catégorise un fichier d'arrêté en fonction de son nom.

    Args:
        filename: Le nom du fichier (format: YYYY-MM-DD_type_description.html)

    Returns:
        Le type de fichier correspondant
    """
    # Normaliser le filename en minuscules pour la comparaison
    filename_lower = filename.lower()

    # Mapping des types de fichiers (ordre important : du plus spécifique au plus général)
    file_type_mapping = {
        "ap d'autorisation": FileType.AP_AUTORISATION,
        "ap enregistrement": FileType.AP_AUTORISATION,
        "ap autorisation temporaire": FileType.AP_AUTORISATION,
        "ap prescriptions complémentaires": FileType.AP_COMPLEMENTAIRE,
        "ap servitude d'utilité publique": FileType.ARRETE_PREFECTORAL,
        "arrêté préfectoral": FileType.ARRETE_PREFECTORAL,
    }

    # Chercher la correspondance la plus longue (plus spécifique) en premier
    for pattern in sorted(file_type_mapping.keys(), key=len, reverse=True):
        if pattern in filename_lower:
            return file_type_mapping[pattern]

    # Par défaut, retourner AUTRE si aucune correspondance
    return FileType.AUTRE


def parse_filename(filename: str) -> tuple[ArreteId, FileType]:
    """
    Parse un nom de fichier d'arrêté et retourne l'ID de l'arrêté et son type.

    Format attendu: YYYY-MM-DD_type_description.html

    Args:
        filename: Le nom du fichier à parser

    Returns:
        Un tuple (arrete_id, file_type)

    Raises:
        ValueError: Si le format du fichier est invalide
    """
    # Vérifier l'extension .html
    if not filename.endswith(".html"):
        raise ValueError(f"Le fichier doit avoir l'extension .html: {filename}")

    # Séparer par underscore
    parts = filename.split("_")
    if len(parts) < 2:
        raise ValueError(
            f"Format invalide: le fichier doit contenir au moins une date "
            f"et un type séparés par '_': {filename}"
        )

    # Extraire la date (première partie)
    arrete_id = parts[0]

    # Valider le format de la date
    date_parts = arrete_id.split("-")
    if len(date_parts) != 3:
        raise ValueError(f"Date invalide: format attendu YYYY-MM-DD, reçu: {arrete_id}")

    try:
        year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
        if not (1900 <= year <= 2100):
            raise ValueError(
                f"Année invalide: doit être entre 1900 et 2100, reçu: {year} dans {arrete_id}"
            )
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError(f"Date invalide: mois ou jour hors limites dans {arrete_id}")
    except (ValueError, IndexError) as e:
        raise ValueError(f"Date invalide: format attendu YYYY-MM-DD, reçu: {arrete_id}") from e

    # Catégoriser le fichier
    file_type = categorize_arrete(filename)

    return arrete_id, file_type


def validate_arretify_version(soup: BeautifulSoup, filename: str = "") -> None:
    """
    Valide que la version Arrêtify du document HTML est supportée.

    Args:
        soup: Document HTML parsé par BeautifulSoup
        filename: Nom du fichier (pour les messages d'erreur)

    Raises:
        ValueError: Si la version Arrêtify est absente ou non supportée
    """
    body = soup.find("body")
    if not body:
        raise ValueError(f"Document HTML invalide (pas de balise <body>): {filename}")

    arretify_version = body.get("data-arretify_version")

    if not arretify_version:
        raise ValueError(
            f"Version Arrêtify manquante dans le document HTML: {filename}\n"
            f"L'attribut 'data-arretify_version' doit être présent sur la balise <body>."
        )

    if not re.match(SUPPORTED_ARRETIFY_VERSION_PATTERN, str(arretify_version)):
        raise ValueError(
            f"Version Arrêtify non supportée: {arretify_version} (fichier: {filename})\n"
            f"OCAPI supporte uniquement les versions {SUPPORTED_ARRETIFY_VERSION}\n"
            f"Version détectée: {arretify_version}"
        )

    # Version valide - rien à retourner
