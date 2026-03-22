from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.CharField(pk=True, max_length=64)
    email = fields.CharField(max_length=255, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class TaskRun(Model):
    id = fields.CharField(pk=True, max_length=64)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="task_runs"
    )
    status = fields.CharField(max_length=40)
    payload = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "task_runs"


class AuditLog(Model):
    id = fields.CharField(pk=True, max_length=64)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="audit_logs"
    )
    tool_name = fields.CharField(max_length=120)
    tool_version = fields.CharField(max_length=40)
    action = fields.CharField(max_length=120)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "audit_logs"
