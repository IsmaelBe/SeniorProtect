# Senior Shield — API

Backend d'un service qui **protège les personnes âgées du phishing** en leur envoyant
de faux mails de test dans une boîte mail simulée. Si la personne tombe dans le piège,
le proche peut s'abonner pour obtenir un audit détaillé.

## Lancer en local

```bash
cd senior_shield
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # renseigne les identifiants OAuth Google
uvicorn main:app --reload
```

Sans `DATABASE_URL`, la base est un fichier SQLite local (`senior_shield.db`).
Les faux mails de phishing proviennent de modèles statiques (`phishing.py`, pas d'IA).

Doc interactive : http://localhost:8000/docs

## Contrat API (pour le front Lovable)

Toutes les réponses sont en JSON. Les routes protégées attendent l'en-tête
`Authorization: Bearer <access_token>` (renvoyé par /register et /login).

| Méthode | Route | Auth | Description |
|---------|-------|------|-------------|
| POST | `/register` | non | Crée le compte de la personne âgée. Renvoie un token. |
| POST | `/login` | non | Connexion. Renvoie un token. |
| GET | `/me` | oui | Infos du compte connecté. |
| GET | `/inbox` | oui | Liste des mails (ne dit PAS lesquels sont des tests). |
| GET | `/emails/{id}` | oui | Ouvre un mail (le marque comme lu). |
| POST | `/phishing/send` | oui | Dépose un faux mail de phishing. Gratuit jusqu'à 3. |
| GET | `/track/click/{token}` | non | Lien piège : trace le clic + page de sensibilisation. |
| GET | `/audit` | oui | Bilan : sur combien de pièges la personne est tombée. Détail = abonnés. |
| POST | `/subscribe` | oui | Active l'abonnement (stub, sans paiement). |

### Exemples

**Inscription**
```json
POST /register
{
  "nom": "Dupont",
  "prenom": "Jeanne",
  "adresse": "12 rue des Lilas, Lyon",
  "email": "jeanne.dupont@example.com",
  "password": "motdepasse",
  "guardian_email": "marie.dupont@gmail.com"
}
```
Réponse :
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "nom": "Dupont", "subscription_active": false, ... }
}
```

**Envoyer un test de phishing**
```json
POST /phishing/send       (Authorization: Bearer <token>)
{ "scenario": null }      // ou un thème précis, ex "Colis La Poste..."
```

**Audit**
```json
GET /audit                (Authorization: Bearer <token>)
{
  "phishing_sent": 3,
  "phishing_opened": 2,
  "phishing_clicked": 1,
  "risk_score": 33,
  "subscription_active": false,
  "details": null,
  "message": "Votre proche est tombé dans 1 piège(s). Abonnez-vous pour..."
}
```

## Connecter un vrai Gmail (OAuth2)

Le service lit les **vrais mails** du senior et y **dépose les tests de phishing**
(via `messages.insert`, sans envoi réel donc sans filtre anti-spam).

### Config Google Cloud (une seule fois)
1. https://console.cloud.google.com → crée un projet.
2. **API & Services → Bibliothèque** → active **Gmail API**.
3. **API & Services → Écran de consentement OAuth** :
   - Type **Externe**, reste en mode **« Testing »**.
   - Ajoute le(s) Gmail de test dans **Test users** (jusqu'à 100, pas de vérification requise).
4. **API & Services → Identifiants → Créer → ID client OAuth → type Application Web** :
   - URI de redirection autorisée : `{BASE_URL}/gmail/callback`
     (ex `https://senior-shield-api.onrender.com/gmail/callback`).
   - Récupère le **Client ID** et le **Client Secret** → variables `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### Flux côté front (Lovable)
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/gmail/connect` | (auth) renvoie `{auth_url}` → ouvre cette URL pour lancer le consentement Google. |
| GET | `/gmail/callback` | Google y redirige après autorisation (géré par le backend, puis renvoie vers `FRONT_URL`). |
| GET | `/gmail/status` | (auth) `{connected, gmail_address}`. |

Une fois connecté : `/inbox`, `/emails/{id}` lisent le **vrai** Gmail, et `/phishing/send`
injecte le test dans la **vraie** boîte. Tant que Gmail n'est pas connecté, le mode
**simulé** (mails en base) reste actif — pratique pour démonter sans config.

## Déploiement Render

Le `render.yaml` crée automatiquement une base Postgres + le service web.
Après déploiement, renseigne dans le dashboard Render :
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` : identifiants OAuth Google.
- `BASE_URL` : l'URL publique du service (ex `https://senior-shield-api.onrender.com`).
- `FRONT_URL` : l'URL du front Lovable.

## Modèle économique
- **Gratuit** : 3 mails de test (la limite est `FREE_PHISHING_LIMIT` dans `main.py`).
- **Abonnement** : tests illimités + rapport d'audit détaillé (`POST /subscribe`).
