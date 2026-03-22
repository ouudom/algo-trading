"""
base.py - Shared SQLAlchemy DeclarativeBase for all ORM models.

All models in this package inherit from ``Base`` so Alembic can auto-detect
schema changes and so SQLAlchemy knows which tables belong to the same
metadata graph.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Application-wide SQLAlchemy declarative base.

    Inherit from this class to register an ORM model with the shared metadata::

        class MyModel(Base):
            __tablename__ = "my_model"
            ...
    """
    pass
