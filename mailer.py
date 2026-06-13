"""Envoi d'emails réels via SMTP (Gmail).

On envoie le faux mail de phishing à l'adresse du senior à piéger (guardian_email).
Identifiants attendus dans l'environnement :
- SMTP_EMAIL    : l'adresse Gmail qui envoie (ex. moncompte@gmail.com)
- SMTP_PASSWORD : un "mot de passe d'application" Google (16 caractères, PAS le mot de
                  passe habituel). Voir https://myaccount.google.com/apppasswords
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def is_configured() -> bool:
    return bool(SMTP_EMAIL and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, html_body: str, sender_name: str = None) -> None:
    """Envoie un email HTML. Lève une exception si l'envoi échoue."""
    if not is_configured():
        raise RuntimeError(
            "SMTP non configuré : renseigne SMTP_EMAIL et SMTP_PASSWORD."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    # Gmail impose l'adresse d'envoi = le compte authentifié ; on ne garde que le nom
    # d'affichage de l'expéditeur usurpé (l'adresse reste la nôtre).
    msg["From"] = f"{sender_name} <{SMTP_EMAIL}>" if sender_name else SMTP_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())
