"""Authentication API endpoints for the application."""

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ and __package__.startswith("app."):
    from ..config import Settings
    from ..core.security import (
        create_access_token,
        decode_access_token,
        hash_password,
        verify_password,
    )
    from ..database import get_db
    from ..models.user import User, UserRole
    from ..schemas.auth import (
        CurrentUserResponse,
        LoginRequest,
        RegisterRequest,
        TokenResponse,
        UserPublic,
    )
else:
    from config import Settings
    from core.security import (
        create_access_token,
        decode_access_token,
        hash_password,
        verify_password,
    )
    from database import get_db
    from models.user import User, UserRole
    from schemas.auth import (
        CurrentUserResponse,
        LoginRequest,
        RegisterRequest,
        TokenResponse,
        UserPublic,
    )

router = APIRouter(prefix="/auth", tags=["auth"])
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def _unauthorized(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

# Dependency to get the current authenticated user from the access token
# Raises HTTP 401 if the token is invalid or the user is not found
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    settings = Settings()
    try:
        payload = decode_access_token(
            token=token,
            secret_key=settings.jwt_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
    except jwt.PyJWTError:
        raise _unauthorized() from None

    subject = payload.get("sub")
    if subject is None:
        raise _unauthorized()

    try:
        user_id = int(subject)
    except ValueError:
        raise _unauthorized() from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _unauthorized("User not found")
    return user

def require_role(*allowed_roles: str):
    async def dependency(
        current_user: Annotated[User, Depends(get_current_user)], # get the current authenticated user's role and details
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Do not have the permission to access this resource")
        return current_user

    return dependency


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPublic:
    # 禁止公開註冊 admin
    if payload.role == UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin registration is not allowed")

    exists = await db.execute(
        select(User).where(
            or_(User.username == payload.username, User.email == payload.email)
        )
    )
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
    )

async def _issue_token_from_credentials(
    *,
    username: str,
    password: str,
    db: AsyncSession,
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    settings = Settings()
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        secret_key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return TokenResponse(access_token=token)

# User login endpoint
@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await _issue_token_from_credentials(
        username=payload.username,
        password=payload.password,
        db=db,
    )
    
@router.post("/token", response_model=TokenResponse)
async def token_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await _issue_token_from_credentials(
        username=form_data.username,
        password=form_data.password,
        db=db,
    )

@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )