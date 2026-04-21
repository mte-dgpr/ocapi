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
"""Shared helpers for tests."""

from typing import Any, cast

from bs4 import BeautifulSoup

from ocapi.types import (
    ArreteFile,
    ArticleVersion,
    FileType,
    NodeId,
    Operation,
    OperationType,
    RawOperation,
    RawOperationType,
    SubTarget,
)


def assert_html_equal(minified_html1: str, minified_html2: str) -> None:
    """Compare HTML fragments after normalising whitespace."""
    soup1 = BeautifulSoup(minified_html1, "html.parser")
    soup2 = BeautifulSoup(minified_html2, "html.parser")
    assert soup1.prettify() == soup2.prettify()


def normalize_html(html: str) -> str:
    """Normalize trailing whitespace so stored snapshots match pipeline output."""
    lines = [line.rstrip() for line in html.splitlines()]
    return "\n".join(lines).strip() + "\n"


def make_arrete(
    arrete_id: str,
    html: str | None = None,
    *,
    aiot: str = "0001",
    filename: str | None = None,
    status: bool = True,
    file_type: FileType | None = None,
) -> ArreteFile:
    if html is None:
        html = f"""
    <html><body data-arretify_version="0.2.0">
     <main data-spec="main">
      <section data-spec="section" data-number="1"><p>{arrete_id}</p></section>
     </main>
    </body></html>
    """
    return ArreteFile(
        id=arrete_id,
        aiot=aiot,
        filename=filename if filename is not None else f"{arrete_id}.html",
        soup=BeautifulSoup(html, "html.parser"),
        status=status,
        file_type=file_type,
    )


def make_raw_op(
    score: int | None, source: str = "1", target: str = "2", target_arrete: str = "2021-01-01"
) -> RawOperation:
    return RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_article=source,
        target_arrete=target_arrete,
        target_article=target,
        confidence_score=score,
    )


def make_op(
    op_type: OperationType,
    sub_target: SubTarget | None = None,
    *,
    operation_id: str = "x",
    operand: str = "content",
    source_arrete: str = "1981-01-01",
    source_article: str = "2",
    target_arrete: str = "1980-01-01",
    target_article: str = "1",
) -> Operation:
    return Operation(
        id=operation_id,
        source_id=NodeId(arrete_id=source_arrete, article_id=source_article),
        target_id=NodeId(arrete_id=target_arrete, article_id=target_article),
        operation_type=op_type,
        operand=operand,
        sub_target=sub_target,
    )


def make_article_version(
    operation_id: str | None,
    *,
    version: int = 1,
    content: str = "",
) -> ArticleVersion:
    return cast(
        ArticleVersion,
        {"version": version, "content": content, "operation_id": operation_id},
    )
