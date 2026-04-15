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
from typing_extensions import NotRequired

from .config import SUPPORTED_ARRETIFY_VERSION, SUPPORTED_ARRETIFY_VERSION_PATTERN, settings
from .exceptions import InvalidArreteIdError, InvalidArticleIdError, InvalidFileFormatError

OperationId = str
ArreteId = str
ArticleId = str
Content = str
AiotId = str
ImageMap = Dict[str, str]  # mapping token -> original src


_NUMERIC_ID_PATTERN = re.compile(r"^\d+(\.\d+)*$")


def parse_article_id(article_id: str) -> str:
    """Validate that an article_id is in a valid format for NodeId.

    Returns
    -------
    str
        The validated article_id.

    Raises
    ------
    InvalidArticleIdError
        If the format is invalid.
    """
    if article_id in ("ALL", "END", "APPENDIX"):
        return article_id
    if article_id.startswith("APPENDIX:"):
        suffix = article_id[len("APPENDIX:") :]
        if _NUMERIC_ID_PATTERN.match(suffix):
            return article_id
    elif article_id.startswith("NEW_ARTICLE:"):
        suffix = article_id[len("NEW_ARTICLE:") :]
        if _NUMERIC_ID_PATTERN.match(suffix):
            return article_id
    elif _NUMERIC_ID_PATTERN.match(article_id):
        return article_id
    raise InvalidArticleIdError(
        "article_id must be in numeric format (e.g. '1.2', '3.1.4'), "
        f"APPENDIX, ALL, END or NEW_ARTICLE:X, got: '{article_id}'"
    )


def article_display_number(article_id: str) -> str:
    """Return the dotted article number for DOM ``data-number`` (strips ``NEW_ARTICLE:``)."""
    if article_id.startswith("NEW_ARTICLE:"):
        return article_id[len("NEW_ARTICLE:") :]
    return article_id


def article_id_sort_tuple(article_id: str) -> tuple[int, ...]:
    """Lexicographic order key for dotted article ids (e.g. ``4.1`` < ``4.2`` < ``10``)."""
    s = article_display_number(article_id)
    return tuple(int(x) for x in s.split("."))


def parse_arrete_id(v: str) -> str:
    """Validate that an arrete_id is in YYYY-MM-DD format.

    Returns
    -------
    str
        The validated arrete_id.

    Raises
    ------
    InvalidArreteIdError
        If the format is invalid.
    """
    date_parts = v.split("-")
    if len(date_parts) != 3:
        raise InvalidArreteIdError(f"Invalid date: expected format YYYY-MM-DD, got: {v}")
    try:
        year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
    except (ValueError, IndexError) as e:
        raise InvalidArreteIdError(f"Invalid date: expected format YYYY-MM-DD, got: {v}") from e
    if not (1900 <= year <= 2100):
        raise InvalidArreteIdError(
            f"Invalid date: year must be between 1900 and 2100, got: {year} in {v}"
        )
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise InvalidArreteIdError(f"Invalid date: month or day out of range in {v}")
    return v


@dataclass
class ArreteFile:
    """Represents an arrêté with its ID and content."""

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
        """Render the permit using the fixed HTML template."""
        template_path = settings.paths.permis_template_path
        template = template_path.read_text(encoding="utf-8")
        required_tokens = ("{{HEADER}}", "{{CONTENT}}", "{{OTHER}}")
        if not all(token in template for token in required_tokens):
            raise ValueError(
                "Invalid consolidated permit HTML template: "
                "placeholders {{HEADER}}, {{CONTENT}} and {{OTHER}} are required."
            )
        return (
            template.replace("{{HEADER}}", self.header)
            .replace("{{CONTENT}}", self.contenu)
            .replace("{{OTHER}}", self.other)
        )


class NodeId(BaseModel):
    """Unique node identifier made up of the arrêté ID and the article ID."""

    model_config = ConfigDict(extra="forbid")

    arrete_id: ArreteId
    article_id: ArticleId

    @field_validator("article_id")
    @classmethod
    def validate_article_id_format(cls, v: str) -> str:
        """Validate that article_id is in numeric format (e.g. '1.2', '3.1.4'),
        APPENDIX, ALL or END."""
        return parse_article_id(v)

    @field_validator("arrete_id")
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        """Validate that arrete_id is in YYYY-MM-DD format."""
        return parse_arrete_id(v)

    def __str__(self) -> str:
        return f"{self.arrete_id}#{self.article_id}"

    def __hash__(self) -> int:
        return hash((self.arrete_id, self.article_id))


class StatusCode(str, Enum):
    RESOLVED = "resolved"
    ERROR_EXTRACTING_OPERAND = "error_extracting_operand"
    ERROR_FINDING_SUBTARGET = "error_finding_subtarget"
    # Sub-target requires LLM consolidation; must not block later operations as an error.
    COMPLEX_SUBTARGET = "complex_subtarget"
    ERROR_EXTRACTING_TARGET = "error_extracting_target"
    PROPAGATED_ERROR = "propagated_error"


class ArticleVersion(TypedDict):
    version: int
    content: Content
    operation_id: str | None
    status_code: NotRequired[StatusCode]


ArticleHistory = Dict[NodeId, list[ArticleVersion]]


class OperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"


STATUS_CODE_MESSAGES: dict[StatusCode, str] = {
    StatusCode.ERROR_EXTRACTING_OPERAND: (
        "Le contenu de l'opération n'a pas pu être extrait de l'arrêté modificatif"
    ),
    StatusCode.ERROR_EXTRACTING_TARGET: (
        "L'article cible de l'opération n'a pas pu être extrait de l'arrêté concerné"
    ),
    StatusCode.ERROR_FINDING_SUBTARGET: (
        "La sous-cible de l'opération n'a pas pu être trouvée dans l'article cible"
    ),
    StatusCode.COMPLEX_SUBTARGET: (
        "La sous-cible de l'opération est trop complexe pour être résolue automatiquement"
    ),
    StatusCode.PROPAGATED_ERROR: (
        "Une erreur sur une opération précédente empêche l'application de cette opération"
    ),
}

DEFAULT_STATUS_CODE_MESSAGE = "Opération non résolue automatiquement"


def status_code_reason(status_code: "StatusCode | None") -> str | None:
    """Return the human-readable reason for a non-resolved *status_code*.

    Returns ``None`` for ``RESOLVED`` or ``None`` inputs (no error to display).
    """
    if status_code is None or status_code == StatusCode.RESOLVED:
        return None
    return STATUS_CODE_MESSAGES.get(status_code, DEFAULT_STATUS_CODE_MESSAGE)


def operation_type_label(operation_type: "OperationType") -> str:
    """Return a French label for the given operation type."""
    if operation_type == OperationType.REPLACE:
        return "modification"
    if operation_type == OperationType.REMOVE:
        return "abrogation"
    return "ajout"


class RawOperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    AUTRE = "AUTRE"


class FileType(Enum):
    """Arrete file type."""

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
    """Consolidated permit title with a unique AIOT code."""

    aiot_code: AiotId | None


class PermitSourceSpec(_BaseModelWithConfig):
    """Source used in the permit (date + arrêté title)."""

    arrete_id: ArreteId
    arrete_title: str
    status: bool = True

    @field_validator("arrete_id")
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        return parse_arrete_id(v)


class PermitSources(_BaseModelWithConfig):
    """List of source arrêtés sorted chronologically."""

    sources: list[PermitSourceSpec]


class PermitVisaEntry(_BaseModelWithConfig):
    """Visas extracted for a given arrêté."""

    arrete_id: ArreteId
    visas: list[str]

    @field_validator("arrete_id")
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        return parse_arrete_id(v)


class PermitVisa(_BaseModelWithConfig):
    """Consolidated visas, grouped by arrêté in chronological order."""

    entries: list[PermitVisaEntry]


class PermitMotifEntry(_BaseModelWithConfig):
    """Grounds extracted for a given arrêté."""

    arrete_id: ArreteId
    motifs: list[str]

    @field_validator("arrete_id")
    @classmethod
    def validate_arrete_id_format(cls, v: str) -> str:
        return parse_arrete_id(v)


class PermitMotif(_BaseModelWithConfig):
    """Consolidated grounds, grouped by arrêté in chronological order."""

    entries: list[PermitMotifEntry]


class SectionVersionSpec(_BaseModelWithConfig):
    """Consolidated version of a section with modification metadata."""

    article_id: ArticleId
    is_modified: bool
    date_version: ArreteId
    content: str

    @field_validator("article_id")
    @classmethod
    def validate_article_id_format(cls, v: str) -> str:
        return parse_article_id(v)

    @field_validator("date_version")
    @classmethod
    def validate_date_version_format(cls, v: str) -> str:
        return parse_arrete_id(v)


class PermitComplements(_BaseModelWithConfig):
    """Main content of non-consolidated specific APs."""

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
    confidence_score: int | None = None


class SubTargetType(Enum):
    """Detectable sub-target types."""

    FULL_SECTION = "FULL_SECTION"
    TABLEAU = "TABLEAU"
    PHRASE = "PHRASE"
    ALINEA = "ALINEA"
    PARAGRAPHE = "PARAGRAPHE"
    LIGNE_TABLEAU = "LIGNE_TABLEAU"
    COLONNE_TABLEAU = "COLONNE_TABLEAU"  # Row and column to remove if detection is wrong?
    COMPLEX = "COMPLEX"  # Requires LLM


class SubTarget(_BaseModelWithConfig):
    """Represents a parsed sub-target."""

    type: SubTargetType
    position: Optional[int] = None  # -1 = last, 1 = first, 2 = second, etc.
    description: Optional[str] = None  # Original sub-target text

    @field_validator("type", mode="before")
    @classmethod
    def _ensure_subtarget_type(cls, v: SubTargetType | str) -> SubTargetType:
        return v if isinstance(v, SubTargetType) else SubTargetType(v)

    def __repr__(self) -> str:
        type_val = self.type.value if isinstance(self.type, SubTargetType) else self.type
        return f"SubTarget({type_val}, pos={self.position})"


class Operation(_BaseModelWithConfig):
    # TODO: keep a reference to source arrêté and an incrementing index
    # for each identical target in that arrêté
    id: OperationId
    source_id: NodeId
    target_id: NodeId
    operation_type: OperationType
    operand: str | None = None
    sub_target: SubTarget | None = None
    status_code: StatusCode | None = None
    confidence_score: int | None = None

    @field_validator("operation_type", mode="before")
    @classmethod
    def _ensure_operation_type(cls, v: OperationType | str) -> OperationType:
        return v if isinstance(v, OperationType) else OperationType(v)


def categorize_arrete(filename: str) -> FileType:
    """Categorise an arrêté file based on its filename.

    Parameters
    ----------
    filename : str
        Filename in the format YYYY-MM-DD_type_description.html.

    Returns
    -------
    FileType
        The corresponding file type.
    """
    # Normalize filename to lowercase for comparison
    filename_lower = filename.lower()

    # File type mapping (order matters: most specific first)
    file_type_mapping = {
        "ap d'autorisation": FileType.AP_AUTORISATION,
        "ap enregistrement": FileType.AP_AUTORISATION,
        "ap autorisation temporaire": FileType.AP_AUTORISATION,
        "ap prescriptions complémentaires": FileType.AP_COMPLEMENTAIRE,
        "ap servitude d'utilité publique": FileType.ARRETE_PREFECTORAL,
        "arrêté préfectoral": FileType.ARRETE_PREFECTORAL,
    }

    # Find the longest (most specific) match first
    for pattern in sorted(file_type_mapping.keys(), key=len, reverse=True):
        if pattern in filename_lower:
            return file_type_mapping[pattern]

    # Default to AUTRE if no match found
    return FileType.AUTRE


def parse_filename(filename: str) -> tuple[ArreteId, FileType]:
    """Parse an arrêté filename and return the arrêté ID and its type.

    Accepted formats:
    - ``YYYY-MM-DD.html`` – date-only, type defaults to :attr:`FileType.AUTRE`
    - ``YYYY-MM-DD_type_description.html`` – date + type

    Parameters
    ----------
    filename : str
        Filename to parse.

    Returns
    -------
    tuple[ArreteId, FileType]
        A (arrete_id, file_type) tuple.

    Raises
    ------
    InvalidFileFormatError
        If the filename format is invalid.
    """
    # Check .html extension
    if not filename.endswith(".html"):
        raise InvalidFileFormatError(f"File must have .html extension: {filename}")

    # Split by underscore
    parts = filename.split("_")
    if len(parts) < 2:
        # Accept date-only format: YYYY-MM-DD.html
        stem = filename[:-5]  # strip .html
        try:
            arrete_id = parse_arrete_id(stem)
        except InvalidArreteIdError as e:
            raise InvalidFileFormatError(
                f"Invalid format: filename must contain at least a date: {filename}"
            ) from e
        return arrete_id, FileType.AUTRE

    # Extract and validate the date (first part)
    try:
        arrete_id = parse_arrete_id(parts[0])
    except InvalidArreteIdError as e:
        raise InvalidFileFormatError(str(e)) from e

    # Categorize the file
    file_type = categorize_arrete(filename)

    return arrete_id, file_type


def validate_arretify_version(soup: BeautifulSoup, filename: str = "") -> None:
    """Validate that the Arrêtify version of an HTML document is supported.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML document.
    filename : str
        Filename used in error messages.

    Raises
    ------
    InvalidFileFormatError
        If the Arrêtify version is missing or not supported.
    """
    body = soup.find("body")
    if not body:
        raise InvalidFileFormatError(f"Invalid HTML document (missing <body> tag): {filename}")

    arretify_version = body.get("data-arretify_version")

    if not arretify_version:
        raise InvalidFileFormatError(
            f"Missing Arrêtify version in HTML document: {filename}\n"
            f"The 'data-arretify_version' attribute must be present on the <body> tag."
        )

    if not re.match(SUPPORTED_ARRETIFY_VERSION_PATTERN, str(arretify_version)):
        raise InvalidFileFormatError(
            f"Unsupported Arrêtify version: {arretify_version} (file: {filename})\n"
            f"OCAPI supports only versions {SUPPORTED_ARRETIFY_VERSION}\n"
            f"Detected version: {arretify_version}"
        )

    # Valid version - nothing to return
