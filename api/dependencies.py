# api/dependencies.py

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.schemas.auth import TokenPayload
from db.models import User
from db.session import async_session_maker

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to provide async database sessions."""
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db_session), token: str = Depends(oauth2_scheme)
) -> User:
    """Validates JWT and returns the current active User object."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # FIX: Uppercase settings attributes matching config.py
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id)
    except JWTError as e:
        # FIX (Ruff B904): Explicit exception chaining
        raise credentials_exception from e

    if not token_data.sub:
        raise credentials_exception

    # FIX: Explicit UUID cast for strict type matching in Postgres
    stmt = select(User).where(User.id == uuid.UUID(token_data.sub))
    result = await db.execute(stmt)

    # Now Pyright automatically knows this is `User | None` due to Mapped models
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception

    return user


async def get_current_tenant(current_user: User = Depends(get_current_user)) -> str:
    """
    Extracts tenant_id from the current authenticated user.
    Crucial for data isolation.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID missing for user"
        )
    return str(current_user.tenant_id)
