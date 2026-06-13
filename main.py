"""API Senior Shield — simulation de phishing pour protéger les personnes âgées.

Flux :
1. Un proche crée le compte de la personne âgée (POST /register).
2. Le service dépose de faux mails de phishing dans la boîte (POST /phishing/send).
   Gratuit : 3 tests. Au-delà : abonnement requis.
3. La personne consulte sa boîte (GET /inbox, GET /emails/{id}).
4. Si elle clique le lien piège (GET /track/click/{token}), c'est tracé.
5. Le proche consulte l'audit (GET /audit). Détails réservés aux abonnés.
"""
import os
from datetime import datetime

from dotenv import load_dotenv

# Charge le fichier .env AVANT que les autres modules ne lisent les variables.
load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

import gmail_client
import mailer
import phishing
from database import Base, engine, get_db
from models import Email, User
from schemas import (
    AuditOut,
    AuthUrlOut,
    EmailInboxOut,
    GmailStatusOut,
    LoginIn,
    PhishingSendIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from security import create_token, decode_token, hash_password, verify_password

# Nombre de tests de phishing offerts avant de devoir s'abonner.
FREE_PHISHING_LIMIT = 3
# URL publique du backend (pour construire les liens pièges). À régler sur Render.
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
# URL du front Lovable (redirection après connexion Gmail réussie).
FRONT_URL = os.getenv("FRONT_URL", BASE_URL)

def _init_db(retries: int = 5, delay: float = 3.0):
    """Crée les tables au démarrage. Le pooler Supabase rejette parfois la 1re
    connexion (hoquet transitoire) : on réessaie au lieu de planter le boot.
    """
    import time

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:
            if attempt == retries:
                raise
            print(f"[init_db] tentative {attempt}/{retries} échouée ({exc}); retry…")
            time.sleep(delay)


_init_db()

app = FastAPI(title="Senior Shield API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # front Lovable
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Authentification ----------
def get_current_user(
    authorization: str = Header(None), db: Session = Depends(get_db)
) -> User:
    """Lit le jeton 'Authorization: Bearer <token>' et renvoie l'utilisateur."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Jeton manquant")
    user_id = decode_token(authorization.split(" ", 1)[1])
    if user_id is None:
        raise HTTPException(status_code=401, detail="Jeton invalide ou expiré")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


@app.get("/")
def root():
    return {"service": "Senior Shield API", "status": "ok"}


@app.post("/register", response_model=TokenOut)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    user = User(
        nom=data.nom,
        prenom=data.prenom,
        adresse=data.adresse,
        email=data.email,
        password_hash=hash_password(data.password),
        guardian_email=data.guardian_email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # On dépose quelques mails légitimes pour que la boîte ait l'air vivante.
    for legit in phishing.LEGIT_EMAILS:
        db.add(Email(user_id=user.id, is_phishing=False, **legit))
    db.commit()

    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@app.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------- Connexion du vrai Gmail (OAuth2) ----------
@app.get("/gmail/connect", response_model=AuthUrlOut)
def gmail_connect(user: User = Depends(get_current_user)):
    """Renvoie l'URL de consentement Google. Le front l'ouvre dans le navigateur.

    On encode l'id utilisateur dans le 'state' (jeton signé) pour le retrouver
    au moment du callback.
    """
    state = create_token(user.id)
    return AuthUrlOut(auth_url=gmail_client.build_auth_url(state))


@app.get("/gmail/callback")
def gmail_callback(
    code: str = "", state: str = "", db: Session = Depends(get_db)
):
    """Google redirige ici après autorisation. On échange le code contre les jetons."""
    user_id = decode_token(state)
    if user_id is None:
        raise HTTPException(status_code=400, detail="State invalide")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    tokens = gmail_client.exchange_code(code)
    user.gmail_address = tokens["gmail_address"]
    user.gmail_access_token = tokens["access_token"]
    # Le refresh_token n'est renvoyé qu'à la 1re autorisation : on le garde s'il manque.
    if tokens["refresh_token"]:
        user.gmail_refresh_token = tokens["refresh_token"]
    user.gmail_token_expiry = tokens["expiry"]
    db.commit()

    # Retour vers le front Lovable.
    return RedirectResponse(url=f"{FRONT_URL}?gmail=connected")


@app.get("/gmail/status", response_model=GmailStatusOut)
def gmail_status(user: User = Depends(get_current_user)):
    return GmailStatusOut(
        connected=user.gmail_connected, gmail_address=user.gmail_address
    )


# ---------- Boîte mail (vue par la personne âgée) ----------
@app.get("/inbox", response_model=list[EmailInboxOut])
def inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Liste les mails, du plus récent au plus ancien.

    Si le Gmail est connecté -> vrais mails (via l'API Gmail).
    Sinon -> mode simulé (mails stockés en base).
    Ne révèle JAMAIS quels mails sont des tests de phishing.
    """
    if user.gmail_connected:
        return gmail_client.list_inbox(user, db)

    rows = (
        db.query(Email)
        .filter(Email.user_id == user.id)
        .order_by(Email.received_at.desc())
        .all()
    )
    return [
        {
            "id": str(e.id),
            "sender_name": e.sender_name,
            "sender_email": e.sender_email,
            "subject": e.subject,
            "body": e.body,
            "opened": e.opened,
            "received_at": e.received_at,
        }
        for e in rows
    ]


@app.get("/emails/{email_id}", response_model=EmailInboxOut)
def read_email(
    email_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ouvre un mail (le marque comme lu)."""
    if user.gmail_connected:
        return gmail_client.get_message(user, db, email_id)

    email = (
        db.query(Email)
        .filter(Email.id == int(email_id), Email.user_id == user.id)
        .first()
    )
    if not email:
        raise HTTPException(status_code=404, detail="Mail introuvable")
    if not email.opened:
        email.opened = True
        email.opened_at = datetime.utcnow()
        db.commit()
        db.refresh(email)
    return {
        "id": str(email.id),
        "sender_name": email.sender_name,
        "sender_email": email.sender_email,
        "subject": email.subject,
        "body": email.body,
        "opened": email.opened,
        "received_at": email.received_at,
    }


# ---------- Envoi d'un test de phishing ----------
@app.post("/phishing/send")
def send_phishing(
    data: PhishingSendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Génère un faux mail de phishing et l'ENVOIE par email au senior à piéger.

    Le destinataire est `guardian_email` (l'adresse du senior renseignée à l'inscription).
    Si le senior clique le lien piège, ça remonte en alerte dans /audit.
    """
    # L'adresse du senior à piéger est obligatoire pour envoyer le test.
    if not user.guardian_email:
        raise HTTPException(
            status_code=400,
            detail="Aucune adresse de senior à piéger (guardian_email manquant).",
        )

    sent_count = (
        db.query(Email)
        .filter(Email.user_id == user.id, Email.is_phishing.is_(True))
        .count()
    )
    if sent_count >= FREE_PHISHING_LIMIT and not user.subscription_active:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Limite gratuite atteinte ({FREE_PHISHING_LIMIT} tests). "
                "Abonnez-vous pour continuer la protection."
            ),
        )

    generated = phishing.generate_phishing_email(user.prenom, user.nom, data.scenario)

    # Lien piège unique, basé sur un token aléatoire.
    token = os.urandom(16).hex()
    trap_link = f'<a href="{BASE_URL}/track/click/{token}">Cliquez ici</a>'
    body = generated["body"].replace("{{LINK}}", trap_link)

    # On garde une trace en base (pour l'audit et le suivi des clics).
    email = Email(
        user_id=user.id,
        sender_name=generated["sender_name"],
        sender_email=generated["sender_email"],
        subject=generated["subject"],
        body=body,
        is_phishing=True,
        link_token=token,
    )
    db.add(email)
    db.commit()
    db.refresh(email)

    # Envoi du VRAI email au senior. Si l'envoi échoue, on annule la trace en base
    # pour ne pas fausser le compteur de tests / l'audit.
    try:
        mailer.send_email(
            to_email=user.guardian_email,
            subject=generated["subject"],
            html_body=body,
            sender_name=generated["sender_name"],
        )
    except Exception as exc:
        db.delete(email)
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Échec de l'envoi de l'email : {exc}",
        )

    return {
        "id": email.id,
        "subject": email.subject,
        "sent_to": user.guardian_email,
        "tests_used": sent_count + 1,
        "free_limit": FREE_PHISHING_LIMIT,
        "message": f"Test de phishing envoyé à {user.guardian_email}.",
    }


# ---------- Traçage du clic (le lien piège) ----------
@app.get("/track/click/{token}", response_class=HTMLResponse)
def track_click(token: str, db: Session = Depends(get_db)):
    """Page atteinte quand la personne clique le lien piège.

    On enregistre qu'elle est tombée dans le piège, puis on affiche un
    message de sensibilisation (au lieu de voler ses données).
    """
    email = db.query(Email).filter(Email.link_token == token).first()
    if email and not email.clicked:
        email.clicked = True
        email.clicked_at = datetime.utcnow()
        db.commit()

    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="utf-8"><title>Attention - Test de phishing</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto;
                 text-align: center; color: #222;">
        <div style="font-size: 64px;">&#9888;&#65039;</div>
        <h1 style="color: #d32f2f;">C'était un test de phishing !</h1>
        <p style="font-size: 18px;">Vous venez de cliquer sur un lien piège.
        Heureusement, c'était un exercice organisé par vos proches pour vous protéger.</p>
        <h3>Comment reconnaître une arnaque ?</h3>
        <ul style="text-align: left; display: inline-block; font-size: 16px;">
            <li>Un message <strong>urgent</strong> qui vous met la pression.</li>
            <li>Une demande d'<strong>argent</strong> ou de <strong>coordonnées bancaires</strong>.</li>
            <li>Une adresse d'expéditeur <strong>bizarre</strong>.</li>
            <li>Un <strong>lien</strong> sur lequel on vous presse de cliquer.</li>
        </ul>
        <p style="margin-top: 30px; color: #666;">En cas de doute, ne cliquez pas
        et demandez à un proche.</p>
    </body>
    </html>
    """


# ---------- Audit (réservé au proche / à l'abonné) ----------
@app.get("/audit", response_model=AuditOut)
def audit(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Rapport : sur combien de pièges la personne est tombée.

    Les chiffres globaux sont visibles par tous ; le détail mail par mail
    est réservé aux abonnés (c'est le produit payant).
    """
    phishing_emails = (
        db.query(Email)
        .filter(Email.user_id == user.id, Email.is_phishing.is_(True))
        .order_by(Email.received_at.desc())
        .all()
    )

    # En mode Gmail, on lit l'état "lu/non lu" en direct depuis Gmail.
    for e in phishing_emails:
        if user.gmail_connected and e.gmail_message_id and not e.opened:
            try:
                if gmail_client.is_opened(user, db, e.gmail_message_id):
                    e.opened = True
                    e.opened_at = datetime.utcnow()
            except Exception:
                pass  # mail supprimé / erreur API : on garde l'état connu
    db.commit()

    sent = len(phishing_emails)
    opened = sum(1 for e in phishing_emails if e.opened)
    clicked = sum(1 for e in phishing_emails if e.clicked)
    risk_score = round((clicked / sent) * 100) if sent else 0

    if user.subscription_active:
        details = phishing_emails
        message = f"{clicked} piège(s) sur {sent} ont fonctionné. Rapport détaillé ci-dessous."
    else:
        details = None
        message = (
            f"Votre proche est tombé dans {clicked} piège(s). "
            "Abonnez-vous pour voir le rapport détaillé et continuer la protection."
        )

    return AuditOut(
        phishing_sent=sent,
        phishing_opened=opened,
        phishing_clicked=clicked,
        risk_score=risk_score,
        subscription_active=user.subscription_active,
        details=details,
        message=message,
    )


@app.post("/subscribe", response_model=UserOut)
def subscribe(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Active l'abonnement (stub — pas de paiement réel pour le hackathon)."""
    user.subscription_active = True
    db.commit()
    db.refresh(user)
    return user
