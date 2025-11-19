from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, model_serializer, Field


NodeId = str
OperationId = str

Content = str

class NodeStatus(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class OperationType(Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"


class _BaseModelWithConfig(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="forbid")

    @model_serializer
    def serialize_model(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}

class Operation(_BaseModelWithConfig):
    id: OperationId
    source_uid: NodeId | None = None
    target_uid: NodeId | None = None
    result: str | None = None
    op_type: OperationType
    operand: str | None = None
    sub_target: str | None = None


OPERATION_EDGE_ATTRS = {"op_type", "operand", "sub_target"}


class OperationTrace(_BaseModelWithConfig):
    input: Content
    output: Content
    operations: list[OperationId]

class SectionNode(BaseModel):
    """
    Un nœud de l'arbre représentant une section d'arrêté.
    Peut contenir des sous-sections (children).
    """
    model_config = ConfigDict(extra="forbid")
    
    uid: NodeId
    display_num: str | None = None  # ex: "1.2.3"
    titre: str | None = None
    type: str | None = None  # "titre", "chapitre", "article"
    
    # Contenu
    html: Content | None = None
    
    # Métadonnées
    status: NodeStatus = NodeStatus.ACTIVE
    parent_uid: NodeId | None = None
    
    # Historique
    trace: List[OperationTrace] = Field(default_factory=list)
    
    # Structure hiérarchique
    children: List["SectionNode"] = Field(default_factory=list)
    
    def to_dict(self):
        """Convertit en dict pour JSON (compatible avec ton format actuel)"""
        return self.model_dump(exclude_none=True, mode='json')
    
    @classmethod
    def from_dict(cls, data: dict):
        """Charge depuis un dict JSON"""
        return cls.model_validate(data)



class ArretDocument(BaseModel):
    """Document complet d'un arrêté avec son arbre de sections"""
    model_config = ConfigDict(extra="forbid")
    
    file: str
    doc_id: NodeId
    status: NodeStatus = NodeStatus.ACTIVE
    sections: List[SectionNode]  # racines de l'arbre

    
    def to_dict(self):
        return self.model_dump(exclude_none=True, mode='json')
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls.model_validate(data)

