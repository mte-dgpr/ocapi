from dataclasses import dataclass
from enum import Enum
from typing import Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, model_serializer, field_validator
import re


OperationId = str
ArreteId = str
ArticleId = str
Content = str
AiotId = str


@dataclass
class ArreteFile:
    """Représente un arrêté avec son ID et son contenu."""
    id: ArreteId
    aiot: AiotId
    filename: str
    soup: BeautifulSoup


class Permis(BaseModel):
    pass

class NodeId(BaseModel):
    """Identifiant unique d'un nœud composé de l'ID de l'arrêté et de l'ID de l'article"""
    model_config = ConfigDict(extra="forbid")
    
    arrete_id: ArreteId
    article_id: ArticleId
    
    @field_validator('article_id')
    @classmethod
    def validate_article_id_format(cls, v: str) -> str:
        """Valide que l'article_id est au format numérique (ex: '1.2', '3.1.4')"""
        if not re.match(r'^\d+(\.\d+)*$', v):
            raise ValueError(f"article_id doit être au format numérique (ex: '1.2', '3.1.4'), reçu: '{v}'")
        return v
    
    def __str__(self) -> str:
        return f"{self.arrete_id}#{self.article_id}"
    
    def __hash__(self) -> int:
        return hash((self.arrete_id, self.article_id))

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
    Base class for removing None values during serialization.
    """
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    @model_serializer
    def serialize_model(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


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
    COLONNE_TABLEAU = "COLONNE_TABLEAU" # Ligne et colonne à supprimer si mauvaise détection ? 
    COMPLEX = "COMPLEX"  # Nécessite LLM


class SubTarget(BaseModel):
    """Représente un sub-target parsé."""
    type: SubTargetType
    position: Optional[int] = None  # None = dernière, 1 = première, 2 = deuxième, etc.
    def __repr__(self):
        return f"SubTarget({self.type.value}, pos={self.position})"

class Operation(_BaseModelWithConfig):
    id: OperationId # TODO : conserver ref vers arrete source et index qui incrémente pour chaque tgt identique dans cet arrete
    source_id: NodeId
    target_id: NodeId
    operation_type: OperationType
    operand: str | None = None
    sub_target: SubTarget | None = None




