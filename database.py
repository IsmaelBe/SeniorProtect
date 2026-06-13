"""Connexion à la base de données.

En local : SQLite (aucune config).
Sur Render : Postgres (via la variable d'environnement DATABASE_URL).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./senior_shield.db")

# Render fournit une URL qui commence par "postgres://" alors que
# SQLAlchemy attend "postgresql://". On corrige automatiquement.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : ouvre une session par requête, la ferme à la fin."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
