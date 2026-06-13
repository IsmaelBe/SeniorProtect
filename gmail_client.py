"""Intégration Gmail via l'API officielle + OAuth2.

On ne stocke JAMAIS le mot de passe Gmail : seulement les jetons OAuth.

Scopes :
- gmail.readonly : lire les vrais mails reçus
- gmail.insert   : déposer nos faux mails de phishing dans la vraie boîte
                   (messages.insert n'envoie rien, ça évite les filtres anti-spam)
"""
import base64
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import parseaddr, parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
REDIRECT_URI = f"{BASE_URL}/gmail/callback"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.insert",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [REDIRECT_URI],
        }
    }


# ---------- Flux OAuth ----------
def build_auth_url(state: str) -> str:
    """URL de l'écran de consentement Google à ouvrir côté front."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(
        access_type="offline",      # pour obtenir un refresh_token
        include_granted_scopes="true",
        prompt="consent",           # force le refresh_token à chaque fois
        state=state,
    )
    return auth_url


def exchange_code(code: str) -> dict:
    """Échange le 'code' renvoyé par Google contre les jetons + l'adresse Gmail."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Récupère l'adresse Gmail connectée.
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()

    return {
        "gmail_address": profile["emailAddress"],
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry,
    }


# ---------- Service authentifié ----------
def _service_for_user(user, db):
    """Construit un client Gmail pour un user, en rafraîchissant le jeton si besoin."""
    creds = Credentials(
        token=user.gmail_access_token,
        refresh_token=user.gmail_refresh_token,
        token_uri=TOKEN_URI,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    if not creds.valid:
        creds.refresh(Request())
        # Persiste le nouveau jeton d'accès.
        user.gmail_access_token = creds.token
        user.gmail_token_expiry = creds.expiry
        db.commit()
    return build("gmail", "v1", credentials=creds)


# ---------- Lecture des vrais mails ----------
def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "ignore")


def _extract_body(payload: dict) -> str:
    """Extrait le corps (HTML de préférence, sinon texte) d'un message Gmail."""
    if payload.get("mimeType", "").startswith("text/") and payload.get("body", {}).get("data"):
        return _decode_part(payload["body"]["data"])

    html, text = None, None
    for part in payload.get("parts", []) or []:
        mime = part.get("mimeType", "")
        if mime == "text/html" and part.get("body", {}).get("data"):
            html = _decode_part(part["body"]["data"])
        elif mime == "text/plain" and part.get("body", {}).get("data"):
            text = _decode_part(part["body"]["data"])
        elif part.get("parts"):  # multipart imbriqué
            nested = _extract_body(part)
            if nested:
                html = html or nested
    return html or text or ""


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def list_inbox(user, db, max_results: int = 20) -> list:
    """Renvoie les derniers mails de la boîte de réception (réels)."""
    service = _service_for_user(user, db)
    resp = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=max_results)
        .execute()
    )
    out = []
    for ref in resp.get("messages", []):
        out.append(get_message(user, db, ref["id"], _service=service))
    return out


def get_message(user, db, message_id: str, _service=None) -> dict:
    """Renvoie un mail formaté à partir de son ID Gmail."""
    service = _service or _service_for_user(user, db)
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = msg["payload"].get("headers", [])
    from_name, from_email = parseaddr(_header(headers, "From"))
    try:
        received = parsedate_to_datetime(_header(headers, "Date"))
    except Exception:
        received = datetime.utcfromtimestamp(int(msg["internalDate"]) / 1000)

    return {
        "id": message_id,
        "sender_name": from_name or from_email,
        "sender_email": from_email,
        "subject": _header(headers, "Subject"),
        "body": _extract_body(msg["payload"]) or msg.get("snippet", ""),
        "opened": "UNREAD" not in msg.get("labelIds", []),
        "received_at": received,
    }


def is_opened(user, db, message_id: str) -> bool:
    """True si le message a été lu (label UNREAD absent)."""
    service = _service_for_user(user, db)
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata")
        .execute()
    )
    return "UNREAD" not in msg.get("labelIds", [])


# ---------- Injection d'un test de phishing dans la vraie boîte ----------
def insert_phishing(user, db, sender_name, sender_email, subject, html_body) -> str:
    """Dépose un mail dans la boîte Gmail SANS l'envoyer. Renvoie l'ID Gmail créé."""
    service = _service_for_user(user, db)

    mime = MIMEText(html_body, "html", "utf-8")
    mime["To"] = user.gmail_address
    mime["From"] = f"{sender_name} <{sender_email}>"
    mime["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")

    result = (
        service.users()
        .messages()
        .insert(userId="me", body={"raw": raw, "labelIds": ["INBOX", "UNREAD"]})
        .execute()
    )
    return result["id"]
