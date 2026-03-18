from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from models import AuditLog
import json

async def log_audit(db: AsyncSession, user_id: str, action: str, resource_type: str, resource_id: str, before: dict = None, after: dict = None, ip_address: str = None):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_snapshot=before,
        after_snapshot=after,
        ip_address=ip_address
    )
    db.add(audit)
    await db.commit()
