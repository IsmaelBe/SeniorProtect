"""Connexion à la base de données.

En local : SQLite (aucune config).
Sur Render : Postgres (via la variable d'environnement DATABASE_URL).
"""
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Ordre de priorité pour choisir la base :
# 1. DATABASE_URL (fournie par Render en prod) — gagne toujours.
# 2. Postgres local construit depuis USER + MDP_BDD (dev avec Postgres).
# 3. SQLite par défaut (dev sans rien configurer).
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("MDP_BDD"):
        user = quote_plus(os.environ["USER"])
        mdp = quote_plus(os.environ["MDP_BDD"])  # encode les caractères spéciaux du mot de passe
        DATABASE_URL = f"postgresql://{user}:{mdp}@localhost/ProtectNet"
    else:
        DATABASE_URL = "sqlite:///./senior_shield.db"

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
