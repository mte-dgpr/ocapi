from enum import Enum
from pydantic import BaseModel, ConfigDict, model_serializer


NodeId = str
OperationId = str

Content = str

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
    op_type: OperationType
    operand: str | None = None
    sub_target: str | None = None


OPERATION_EDGE_ATTRS = {"op_type", "operand", "sub_target"}


class OperationTrace(_BaseModelWithConfig):
    input: Content
    output: Content
    operation: OperationId