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
    # Le pooler Supabase (Supavisor) peut rejeter une connexion par intermittence.
    # On réessaie UN PEU pour absorber un hoquet transitoire — MAIS si le disjoncteur
    # est ouvert (ECIRCUITBREAKER), on échoue tout de suite : marteler entretient le
    # disjoncteur et l'empêche de se réarmer.
    import time

    import psycopg2  # type: ignore

    def _connect_with_retry(retries: int = 2, delay: float = 2.0):
        last_exc = None
        for _ in range(retries):
            try:
                return psycopg2.connect(DATABASE_URL)
            except psycopg2.OperationalError as exc:
                last_exc = exc
                if "ECIRCUITBREAKER" in str(exc):
                    raise  # ne pas marteler le disjoncteur
                time.sleep(delay)
        raise last_exc

    # pool_size + recycle : on garde des connexions chaudes et réutilisées au lieu
    # d'en rouvrir une à chaque requête (réduit fortement le nombre d'auth → moins
    # de risque de déclencher le disjoncteur).
    engine = create_engine(
        DATABASE_URL,
        creator=_connect_with_retry,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=1800,
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
