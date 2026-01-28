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
TODO : remplacer tout ce fichier par PY - arrete_utils quand la librairie sera prête.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypedDict
from uuid import uuid4

from langchain_core.documents import Document


@dataclass(frozen=True)
class FieldsImport:
    champ_10_siret: str
    champ_14_code_dechet: str
    """
    Format code déchet CED : 12 34 56
    """

    def __post_init__(self) -> None:
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


class DocumentMetadata(TypedDict, total=False):
    parent: str
    index_id: IndexId | None
    chunk_index: int
    content_type: str


def make_document_factory(
    content_type: ContentType,
    parent: DocumentId | None = None,
) -> Callable[[str, dict[str, Any] | None], Document]:
    chunk_index_counter = -1

    def _document_factory(
        page_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        nonlocal chunk_index_counter
        chunk_index_counter += 1
        document_id = _id_generator()

        if metadata and metadata.get("parent"):
            raise ValueError("Document shouldnt already have a parent")

        base_metadata: DocumentMetadata = {
            # Add the document ID to the metadata
            # so that when using langchain text splitters
            # it will be added to the metadata of each chunk.
            "parent": parent or document_id,
            "index_id": None,
            "chunk_index": chunk_index_counter,
            "content_type": content_type.value,
        }
        merged_metadata: dict[str, Any] = {**base_metadata, **(metadata or {})}

        return Document(id=document_id, page_content=page_content, metadata=merged_metadata)

    return _document_factory


def _id_generator() -> str:
    return str(uuid4())
