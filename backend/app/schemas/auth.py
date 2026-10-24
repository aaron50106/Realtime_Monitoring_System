"""Authentication schemas for the application."""

from typing import Literal # Used for defining literal types for roles
from pydantic import BaseModel, ConfigDict, EmailStr, Field # Used for defining Pydantic models and field constraints

# Define roles that can be self-registered by users
SelfRegisterRole = Literal["user", "viewer", "admin"]

# Request schema for user registration
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: SelfRegisterRole = "user"


# Request schema for user login
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

# Response schema for access token after successful authentication
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Public user information schema
class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str


# Response schema for the currently authenticated user
class CurrentUserResponse(UserPublic):
    pass