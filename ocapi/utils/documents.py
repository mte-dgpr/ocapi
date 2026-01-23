"""
TODO : remplacer tout ce fichier par PY - arrete_utils quand la librairie sera prête.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Callable, TypedDict
from uuid import uuid4

from langchain_core.documents import Document


@dataclass(frozen=True)
class FieldsImport:
    champ_10_siret: str
    champ_14_code_dechet: str
    """
    Format code déchet CED : 12 34 56
    """

    def __post_init__(self):
        if not re.match(
            r"^\d\d \d\d \d\d$",
            self.champ_14_code_dechet,
        ):
            raise ValueError(f"Invalid code dechet format: {self.champ_14_code_dechet}")


@dataclass(frozen=True)
class FieldsExport:
    pass


class ContentType(Enum):
    PLAIN_TEXT = "plain_text"
    HTML = "html"
    MARKDOWN = "markdown"


IndexId = str
DocumentId = str


class DocumentMetadata(TypedDict):
    parent: str
    index_id: IndexId | None
    chunk_index: int
    content_type: ContentType


def make_document_factory(
    content_type: ContentType,
    parent: DocumentId | None = None,
) -> Callable[[str, dict | None], Document]:
    chunk_index_counter = -1

    def _document_factory(
        page_content: str,
        metadata: dict | None = None,
    ) -> Document:
        nonlocal chunk_index_counter
        chunk_index_counter += 1
        document_id = _id_generator()

        if metadata and metadata.get("parent"):
            raise ValueError(
                "Document shouldnt already have a parent"
            )

        return Document(
            id=document_id,
            page_content=page_content,
            metadata=DocumentMetadata(
                # Add the document ID to the metadata
                # so that when using langchain text splitters
                # it will be added to the metadata of each chunk.
                parent=parent or document_id,
                index_id=None,
                chunk_index=chunk_index_counter,
                content_type=content_type.value,
                **(metadata or {}),
            ),
        )

    return _document_factory

def _id_generator():
    return str(uuid4())
