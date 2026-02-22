from pydantic import BaseModel


class TaskRecord(BaseModel):
    task_id: str
    user_id: str
    status: str
