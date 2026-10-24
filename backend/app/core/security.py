from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

# Security utilities for password hashing and JWT token management
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# convert plain password to hashed password and verify hashed password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

#  Verify if the provided plain password matches the hashed password
def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

# Create and decode JWT access tokens for authentication and authorization
def create_access_token(*, subject: str, role: str, secret_key: str, algorithm: str, expires_minutes: int) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "role": role, "exp": expire_at}
    return jwt.encode(payload, secret_key, algorithm=algorithm)

# Decode JWT access token and return the payload
def decode_access_token(token: str, secret_key: str, algorithm: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=[algorithm])