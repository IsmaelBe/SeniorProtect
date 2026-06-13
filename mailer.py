"""Envoi d'emails via l'API HTTP de Mailjet.

Render (plan gratuit) bloque les ports SMTP sortants : on passe donc par l'API
HTTPS de Mailjet (port 443) au lieu de smtplib.

Variables d'environnement attendues :
- MAILJET_API_KEY      : clé API publique (Mailjet → Account → API Key Management)
- MAILJET_SECRET_KEY   : clé secrète
- MAILJET_SENDER_EMAIL : adresse expéditrice VALIDÉE dans Mailjet (Senders)
- MAILJET_SENDER_NAME  : nom d'affichage par défaut (optionnel)
"""
import os

import requests  # type: ignore

MAILJET_API_KEY = os.getenv("MAILJET_API_KEY", "")
MAILJET_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY", "")
MAILJET_SENDER_EMAIL = os.getenv("MAILJET_SENDER_EMAIL", "")
MAILJET_SENDER_NAME = os.getenv("MAILJET_SENDER_NAME", "Senior Shield")
MAILJET_URL = "https://api.mailjet.com/v3.1/send"


def is_configured() -> bool:
    return bool(MAILJET_API_KEY and MAILJET_SECRET_KEY and MAILJET_SENDER_EMAIL)


def send_email(to_email: str, subject: str, html_body: str, sender_name: str = None) -> None:
    """Envoie un email HTML via Mailjet. Lève une exception si l'envoi échoue.

    `sender_name` = nom d'affichage usurpé (ex. "Sécurité Banque Postale"). L'adresse
    expéditrice reste MAILJET_SENDER_EMAIL (la seule validée).
    """
    if not is_configured():
        raise RuntimeError(
            "Mailjet non configuré : renseigne MAILJET_API_KEY, MAILJET_SECRET_KEY "
            "et MAILJET_SENDER_EMAIL."
        )

    payload = {
        "Messages": [
            {
                "From": {
                    "Email": MAILJET_SENDER_EMAIL,
                    "Name": sender_name or MAILJET_SENDER_NAME,
                },
                "To": [{"Email": to_email}],
                "Subject": subject,
                "HTMLPart": html_body,
            }
        ]
    }
    resp = requests.post(
        MAILJET_URL,
        json=payload,
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        timeout=15,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Mailjet a refusé l'envoi ({resp.status_code}) : {resp.text}")
