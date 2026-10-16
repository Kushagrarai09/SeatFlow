"""Administrator-only account role management."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import User
from app.schemas_auth import UserRead

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])
DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["attendee", "organizer"]


class ActiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


@router.patch("/users/{user_id}/role", response_model=UserRead)
def update_user_role(user_id: int, payload: RoleUpdate, db: DbSession, admin: AdminUser) -> User:
    """Promote/demote accounts between attendee and organizer; admin assignment is intentionally excluded."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=409, detail="Administrator roles are managed out of band")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/active", response_model=UserRead)
def update_user_active(user_id: int, payload: ActiveUpdate, db: DbSession, admin: AdminUser) -> User:
    """Activate or deactivate a user account. Deactivation prevents new authenticated requests."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own administrator account")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
