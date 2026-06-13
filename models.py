"""Tables de la base de données."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text # type: ignore
from sqlalchemy.orm import relationship # type: ignore

from database import Base


class User(Base):
    """Le compte d'une personne âgée protégée (sa boîte mail simulée).

    Créé par un proche (le fils/la fille) qui donne ainsi accès au service.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    adresse = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    # Email du proche qui gère le compte (reçoit l'audit).
    guardian_email = Column(String, nullable=True)
    # L'abonnement payant débloque le rapport d'audit détaillé.
    subscription_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Connexion Gmail (OAuth2) ---
    # L'adresse Gmail réelle du senior, connectée via OAuth.
    gmail_address = Column(String, nullable=True)
    # Jetons OAuth Google. ON NE STOCKE JAMAIS LE MOT DE PASSE GMAIL.
    gmail_access_token = Column(String, nullable=True)
    gmail_refresh_token = Column(String, nullable=True)
    gmail_token_expiry = Column(DateTime, nullable=True)

    @property
    def gmail_connected(self) -> bool:
        return bool(self.gmail_refresh_token)

    emails = relationship(
        "Email", back_populates="user", cascade="all, delete-orphan"
    )


class Email(Base):
    """Un mail dans la boîte simulée. Peut être légitime ou un test de phishing."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    sender_name = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)  # HTML simple

    # True = c'est un faux mail de test envoyé par notre service.
    is_phishing = Column(Boolean, default=False, nullable=False)
    # Token unique du lien piège (sert à tracer le clic).
    link_token = Column(String, nullable=True, index=True)
    # ID du message dans la vraie boîte Gmail (si injecté via l'API Gmail).
    gmail_message_id = Column(String, nullable=True, index=True)

    opened = Column(Boolean, default=False, nullable=False)
    opened_at = Column(DateTime, nullable=True)
    # clicked = la personne est TOMBÉE dans le piège (a cliqué le lien).
    clicked = Column(Boolean, default=False, nullable=False)
    clicked_at = Column(DateTime, nullable=True)

    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="emails")
