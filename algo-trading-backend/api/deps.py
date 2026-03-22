"""
deps.py - Reusable FastAPI dependency annotations.

Import ``DBSession`` in route functions for a clean, type-annotated
database dependency that avoids repeating the ``Depends(get_db)`` boilerplate.

Usage::

    from api.deps import DBSession

    @router.get("/trades")
    async def list_trades(db: DBSession):
        ...
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db

# Annotated type alias — use this in route function signatures.
DBSession = Annotated[AsyncSession, Depends(get_db)]
