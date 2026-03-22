from pydantic import BaseModel


class UserEntity(BaseModel):
    id: str
    email: str


class TaskRunEntity(BaseModel):
    id: str
    user_id: str
    status: str


class AuditLogEntity(BaseModel):
    id: str
    user_id: str
    tool_name: str
    tool_version: str
    action: str
