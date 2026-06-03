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
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, TypedDict

from arretify.parsing_utils.numbering import ROMAN_NUMERALS_PATTERN_S, str_to_levels
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator
from typing_extensions import NotRequired

from ocapi.utils.logging_utils import get_logger

from .config import SUPPORTED_ARRETIFY_VERSION, SUPPORTED_ARRETIFY_VERSION_PATTERN
from .exceptions import InvalidArreteIdError, InvalidArticleIdError, InvalidFileFormatError

_LOGGER = get_logger(__name__)

OperationId = str
ArreteId = str
ArticleId = str
Content = str
AiotId = str
ImageMap = Dict[str, str]  # mapping token -> original src


# Article ids can mix roman numerals (I, IV, XII…), single letters (A, b…) and
# numbers at each level, separated by "." or "-" (e.g. "1.2", "I.1", "A-3", "4-1").
_ARTICLE_LEVEL_PATTERN_S = rf"({ROMAN_NUMERALS_PATTERN_S}|[A-Za-z]|\d+)"
_ARTICLE_ID_PATTERN = re.compile(rf"^{_ARTICLE_LEVEL_PATTERN_S}([.\-]{_ARTICLE_LEVEL_PATTERN_S})*$")


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
        if _ARTICLE_ID_PATTERN.match(suffix):
            return article_id
    elif article_id.startswith("NEW_ARTICLE:"):
        suffix = article_id[len("NEW_ARTICLE:") :]
        if _ARTICLE_ID_PATTERN.match(suffix):
            return article_id
    elif _ARTICLE_ID_PATTERN.match(article_id):
        return article_id
    raise InvalidArticleIdError(
        "article_id must be a dotted/dashed numbering (e.g. '1.2', 'I.1', 'A-3'), "
        f"APPENDIX, ALL, END or NEW_ARTICLE:X, got: '{article_id}'"
    )


def article_display_number(article_id: str) -> str:
    """Return the dotted article number for DOM ``data-number`` (strips ``NEW_ARTICLE:``)."""
    if article_id.startswith("NEW_ARTICLE:"):
        return article_id[len("NEW_ARTICLE:") :]
    return article_id


def _numbering_fragment_for_sort(article_id: str) -> str:
    s = article_display_number(article_id)
    if s.startswith("APPENDIX:"):
        return s[len("APPENDIX:") :]
    return s


def article_id_sort_tuple(article_id: str) -> tuple[int, ...]:
    """Lexicographic order key for dotted article ids (e.g. ``4.1`` < ``4.2`` < ``10``)."""
    fragment = _numbering_fragment_for_sort(article_id).strip()
    if not fragment:
        return (999_999,)
    try:
        levels = str_to_levels(fragment)
    except ValueError:
        return (999_999,)
    if levels is None:
        return (999_999,)
    return tuple(levels)


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
    principal: bool = False


class Permis(BaseModel):
    header: str
    contenu: str
    other: str
    aiot: AiotId | None = None


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


class ErrorCode(str, Enum):
    ERROR_EXTRACTING_OPERAND = "error_extracting_operand"
    ERROR_FINDING_SUBTARGET = "error_finding_subtarget"
    # Sub-target requires LLM consolidation; must not block later operations as an error.
    COMPLEX_SUBTARGET = "complex_subtarget"
    ERROR_EXTRACTING_TARGET = "error_extracting_target"
    ERROR_EXTRACTING_SOURCE = "error_extracting_source"
    PROPAGATED_ERROR = "propagated_error"
    DISABLED_LLM_CALL = "disabled_llm_call"
    # ADD targeting an entire arrêté without a real sub-target
    # (e.g. "cet arrêté complète l'arrêté XXX"): nothing to consolidate.
    NOT_AN_OPERATION = "not_an_operation"
    # Full removal that conflicts with other (more specific) operations from the
    # same source towards the same target: the abrogation is most likely a
    # detection mistake and is dropped in favor of the narrower operations.
    LESS_IMPORTANT = "less_important"
    # Full removal targeting an arrêté that isn't part of the consolidated permit
    # (e.g. an older arrêté missing from the file set).
    MISSING_ARRETE = "missing_arrete"


class ErrorSeverity(Enum):
    """Severity level for operation error codes.

    HIGH errors indicate structurally invalid operations that cannot be resolved
    and should be counted as genuine failures.
    LOW errors indicate operations that are structurally plausible but irrelevant
    in the current corpus context (e.g. targeting a missing arrêté); these can be
    excluded before computing detection metrics to avoid inflating false positives.
    """

    HIGH = "high"
    LOW = "low"


ERROR_CODE_SEVERITY: dict[ErrorCode, ErrorSeverity] = {
    ErrorCode.ERROR_EXTRACTING_OPERAND: ErrorSeverity.HIGH,
    ErrorCode.ERROR_EXTRACTING_TARGET: ErrorSeverity.HIGH,
    ErrorCode.ERROR_EXTRACTING_SOURCE: ErrorSeverity.LOW,
    ErrorCode.ERROR_FINDING_SUBTARGET: ErrorSeverity.HIGH,
    ErrorCode.COMPLEX_SUBTARGET: ErrorSeverity.HIGH,
    ErrorCode.PROPAGATED_ERROR: ErrorSeverity.HIGH,
    ErrorCode.DISABLED_LLM_CALL: ErrorSeverity.HIGH,
    ErrorCode.NOT_AN_OPERATION: ErrorSeverity.LOW,
    ErrorCode.LESS_IMPORTANT: ErrorSeverity.LOW,
    ErrorCode.MISSING_ARRETE: ErrorSeverity.LOW,
}


class ArticleVersion(TypedDict):
    version: int
    title: Content
    content: Content
    operation_id: str | None
    error_codes: NotRequired[frozenset[ErrorCode]]


ArticleHistory = Dict[NodeId, list[ArticleVersion]]


class OperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"


ERROR_CODE_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.ERROR_EXTRACTING_OPERAND: (
        "Le contenu de l'opération n'a pas pu être extrait de l'arrêté modificatif"
    ),
    ErrorCode.ERROR_EXTRACTING_TARGET: (
        "L'article cible de l'opération n'a pas pu être extrait de l'arrêté concerné"
    ),
    ErrorCode.ERROR_EXTRACTING_SOURCE: (
        "L'article source de l'opération n'a pas pu être extrait de l'arrêté concerné"
    ),
    ErrorCode.ERROR_FINDING_SUBTARGET: (
        "La sous-cible de l'opération n'a pas pu être trouvée dans l'article cible"
    ),
    ErrorCode.COMPLEX_SUBTARGET: (
        "La sous-cible de l'opération est trop complexe pour être résolue automatiquement"
    ),
    ErrorCode.PROPAGATED_ERROR: (
        "Une erreur sur une opération précédente empêche l'application de cette opération"
    ),
    ErrorCode.DISABLED_LLM_CALL: ("La résolution des opérations complexes par IA est désactivée"),
    ErrorCode.NOT_AN_OPERATION: ("Il n'y a pas d'opération de consolidation à réaliser"),
    ErrorCode.LESS_IMPORTANT: (
        "L'arrêté présente d'autres opérations qui rendent celle-ci caduque"
    ),
    ErrorCode.MISSING_ARRETE: ("L'arrêté cible n'est pas présent dans le permis consolidé"),
}

DEFAULT_ERROR_CODE_MESSAGE = "Opération non résolue automatiquement"


def error_codes_reason(error_codes: "frozenset[ErrorCode] | None") -> str | None:
    """Return the human-readable reason(s) for a set of error codes.

    Joins all error messages with " ; ". Returns ``None`` when the set is
    empty or ``None`` (no error to display).
    """
    if not error_codes:
        return None
    reasons = [
        ERROR_CODE_MESSAGES.get(code, DEFAULT_ERROR_CODE_MESSAGE)
        for code in sorted(error_codes, key=lambda c: c.value)
    ]
    return " ; ".join(reasons)


def operation_type_label(operation_type: "OperationType") -> str:
    """Return a French label for the given operation type."""
    if operation_type == OperationType.REPLACE:
        return "modification"
    if operation_type == OperationType.REMOVE:
        return "abrogation"
    return "ajout"


class RawOperationType(Enum):
    ADD = "add"
    REMOVE = "delete"
    REPLACE = "replace"
    AUTRE = "autre"

    @classmethod
    def _missing_(cls, value: object) -> "RawOperationType | None":
        # Accept the legacy uppercase names ("ADD", "REMOVE", "REPLACE", "AUTRE")
        # used by the LLM prompt and older operations.json fixtures, so callers
        # can construct the enum from either the canonical lowercase value or
        # the member name.
        if isinstance(value, str):
            try:
                return cls[value.upper()]
            except KeyError:
                return None
        return None


# Maps the tag-level enum (lowercase, mirrors arretify's OperationType) to the
# pipeline-level enum used downstream. AUTRE has no equivalent and is filtered
# out before reaching this mapping.
_RAW_TO_OPERATION_TYPE: "dict[RawOperationType, OperationType]" = {
    RawOperationType.ADD: OperationType.ADD,
    RawOperationType.REMOVE: OperationType.REMOVE,
    RawOperationType.REPLACE: OperationType.REPLACE,
}


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
    source_arrete: ArreteId
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
    id: OperationId
    source_id: NodeId
    target_id: NodeId
    operation_type: OperationType
    operand: str | None = None
    sub_target: SubTarget | None = None
    error_codes: frozenset[ErrorCode] = frozenset()
    confidence_score: int | None = None

    @field_validator("operation_type", mode="before")
    @classmethod
    def _ensure_operation_type(cls, v: OperationType | str) -> OperationType:
        return v if isinstance(v, OperationType) else OperationType(v)

    @field_serializer("error_codes", when_used="json")
    def _serialize_error_codes(self, codes: frozenset[ErrorCode]) -> list[str]:
        return sorted(c.value for c in codes)

    @model_validator(mode="after")
    def _derive_detection_error_codes(self) -> "Operation":
        """Derive error codes from the operation shape.

        - target_article=ALL with a sub-target other than FULL_SECTION is
          incoherent (the LLM tried to target something specific inside
          "all articles") → ``ERROR_EXTRACTING_OPERAND``.
        - ADD targeting an entire arrêté (target_article=ALL) without a
          real sub-target (e.g. "cet arrêté complète l'arrêté XXX") is
          not a consolidation operation → ``NOT_AN_OPERATION``.
        """
        if (
            ErrorCode.ERROR_EXTRACTING_OPERAND not in self.error_codes
            and self.target_id.article_id == "ALL"
            and self.sub_target is not None
            and self.sub_target.type != SubTargetType.FULL_SECTION
        ):
            _LOGGER.warning(
                f"Operation {self.id}: target_article=ALL with "
                f"sub_target={self.sub_target.type} is not fully defined "
                f"(target_arrete={self.target_id.arrete_id})"
            )
            self.error_codes = self.error_codes | {ErrorCode.ERROR_EXTRACTING_OPERAND}

        if (
            self.operation_type == OperationType.ADD
            and self.target_id.article_id == "ALL"
            and (self.sub_target is None or self.sub_target.type == SubTargetType.FULL_SECTION)
        ):
            _LOGGER.info(
                f"Operation {self.id}: ADD targeting target_article=ALL without a "
                f"specific sub-target (target_arrete={self.target_id.arrete_id}); "
                f"likely just signals a complementary arrêté rather than a "
                f"consolidation operation"
            )
            self.error_codes = self.error_codes | {ErrorCode.NOT_AN_OPERATION}

        return self

    @classmethod
    def from_raw_detection(
        cls,
        raw_operation: RawOperation,
        operation_id: OperationId,
        operand: str | None,
        sub_target: "SubTarget | None",
    ) -> "Operation":
        """Build an ``Operation`` from a validated raw detection and its extracted operand.

        Caller is expected to have validated ``raw_operation.source_article`` and
        ``raw_operation.target_article`` and to pass the already-extracted ``operand``
        and ``sub_target``. This method handles operation-type coercion and the
        ``REPLACE ALL`` → ``REMOVE`` conversion before instantiation.
        """
        assert raw_operation.source_article is not None
        assert raw_operation.target_article is not None

        op_type = _RAW_TO_OPERATION_TYPE[raw_operation.operation_type]

        # A full-arrêté REPLACE (target_article=ALL) is in practice an abrogation.
        if op_type == OperationType.REPLACE and raw_operation.target_article == "ALL":
            _LOGGER.info(
                f"Operation {operation_id}: REPLACE ALL converted to REMOVE "
                f"(target_arrete={raw_operation.target_arrete})"
            )
            op_type = OperationType.REMOVE
            operand = None

        return cls(
            id=operation_id,
            source_id=NodeId(
                arrete_id=raw_operation.source_arrete,
                article_id=raw_operation.source_article,
            ),
            target_id=NodeId(
                arrete_id=raw_operation.target_arrete,
                article_id=raw_operation.target_article,
            ),
            operation_type=op_type,
            operand=operand,
            sub_target=sub_target,
            confidence_score=raw_operation.confidence_score,
        )


def is_resolved_op(operation: "Operation") -> bool:
    """Return True when no error is attached to *operation*."""
    return not operation.error_codes


def is_low_severity_op(operation: "Operation") -> bool:
    """Return True when *operation* carries only LOW-severity error codes."""
    if not operation.error_codes:
        return False
    return all(
        ERROR_CODE_SEVERITY.get(code, ErrorSeverity.HIGH) == ErrorSeverity.LOW
        for code in operation.error_codes
    )


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
    if not isinstance(body, Tag):
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
