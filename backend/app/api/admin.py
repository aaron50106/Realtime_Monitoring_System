from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ and __package__.startswith("app."):
    from ..core.security import hash_password
    from ..database import get_db
    from ..models.user import User, UserRole
    from ..schemas.admin import (
        AdminUserRead,
        AdminUserRoleUpdateRequest,
        AdminUsersListResponse,
        BootstrapAdminRequest,
    )
    from .auth import get_current_user, require_role
else:
    from core.security import hash_password
    from database import get_db
    from models.user import User, UserRole
    from schemas.admin import (
        AdminUserRead,
        AdminUserRoleUpdateRequest,
        AdminUsersListResponse,
        BootstrapAdminRequest,
    )
    from api.auth import get_current_user, require_role

router = APIRouter(prefix="/admin", tags=["admin"])
SYSTEM_BOT_USERNAME = "system_bot"


@router.post("/bootstrap", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(
    payload: BootstrapAdminRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserRead:
    existing_admin = await db.execute(
        select(User).where(
            User.role == UserRole.ADMIN.value,
            User.username != SYSTEM_BOT_USERNAME,
        ).limit(1)
    )
    if existing_admin.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Admin user already exists")

    existing_user = await db.execute(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserRead.model_validate(user)


@router.get("/users", response_model=AdminUsersListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN.value))],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> AdminUsersListResponse:
    _ = current_user
    filters = [User.username != SYSTEM_BOT_USERNAME]
    if role is not None:
        filters.append(User.role == role)
    if keyword is not None:
        like_keyword = f"%{keyword}%"
        filters.append(or_(User.username.like(like_keyword), User.email.like(like_keyword)))

    count_stmt = select(func.count()).select_from(User)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(User)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)

    result = await db.execute(stmt)
    users = result.scalars().all()

    total_pages = (total + size - 1) // size if total > 0 else 0
    return AdminUsersListResponse(
        items=[AdminUserRead.model_validate(user) for user in users],
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserRead)
async def update_user_role(
    user_id: int,
    payload: AdminUserRoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN.value))],
) -> AdminUserRead:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.username != SYSTEM_BOT_USERNAME,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id == user_id and payload.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=400, detail="Admin cannot remove own admin role")

    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    return AdminUserRead.model_validate(user)


@router.get("/users/{user_id}", response_model=AdminUserRead)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN.value))],
) -> AdminUserRead:
    _ = current_user
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.username != SYSTEM_BOT_USERNAME,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserRead.model_validate(user)
