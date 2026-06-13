"""Schémas Pydantic : validation des entrées et formatage des sorties."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


# ---------- Authentification ----------
class RegisterIn(BaseModel):
    nom: str
    prenom: str
    adresse: str
    email: EmailStr
    password: str
    guardian_email: Optional[EmailStr] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    nom: str
    prenom: str
    adresse: str
    email: EmailStr
    guardian_email: Optional[EmailStr] = None
    subscription_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Boîte mail (vue par la personne âgée) ----------
# IMPORTANT : ne révèle PAS is_phishing, sinon le test n'a aucun sens.
# id est une chaîne : ID Gmail (mode réel) ou id DB (mode simulé).
class EmailInboxOut(BaseModel):
    id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    opened: bool
    received_at: datetime


# ---------- Connexion Gmail ----------
class GmailStatusOut(BaseModel):
    connected: bool
    gmail_address: Optional[str] = None


class AuthUrlOut(BaseModel):
    auth_url: str


# ---------- Envoi d'un test de phishing ----------
class PhishingSendIn(BaseModel):
    # Scénario optionnel (banque, colis, impots...). Sinon choisi au hasard.
    scenario: Optional[str] = None


# ---------- Audit (réservé au proche / à l'abonné) ----------
class AuditEmailDetail(BaseModel):
    id: int
    sender_name: str
    subject: str
    received_at: datetime
    opened: bool
    clicked: bool  # est tombé dans le piège

    class Config:
        from_attributes = True


class AuditOut(BaseModel):
    phishing_sent: int
    phishing_opened: int
    phishing_clicked: int  # nombre de pièges où la personne est tombée
    risk_score: int  # 0 à 100
    subscription_active: bool
    # Détail par mail : uniquement si abonné.
    details: Optional[List[AuditEmailDetail]] = None
    message: str
