"""Connexion à la base de données.

En local : SQLite (aucune config).
Sur Render : Postgres (via la variable d'environnement DATABASE_URL).
"""
import os

from sqlalchemy import create_engine # type: ignore
from sqlalchemy.orm import declarative_base, sessionmaker # type: ignore

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./senior_shield.db")

# Render fournit une URL qui commence par "postgres://" alors que
# SQLAlchemy attend "postgresql://". On corrige automatiquement.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    # Le pooler Supabase (Supavisor) rejette parfois une connexion par intermittence
    # ("password authentication failed" transitoire). On réessaie à chaque ouverture
    # de connexion pour ne pas faire échouer la requête / le boot.
    import time

    import psycopg2  # type: ignore

    def _connect_with_retry(retries: int = 4, delay: float = 1.5):
        last_exc = None
        for _ in range(retries):
            try:
                return psycopg2.connect(DATABASE_URL)
            except psycopg2.OperationalError as exc:
                last_exc = exc
                time.sleep(delay)
        raise last_exc

    engine = create_engine(
        DATABASE_URL,
        creator=_connect_with_retry,
        pool_pre_ping=True,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : ouvre une session par requête, la ferme à la fin."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
