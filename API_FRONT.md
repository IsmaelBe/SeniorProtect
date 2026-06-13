# Senior Shield — Doc d'intégration Front

Documentation des endpoints pour le front (Lovable). Toutes les réponses sont en **JSON**.

- **URL de base (prod)** : `https://classifierhackathon.onrender.com`
- **URL de base (local)** : `http://localhost:8000`
- **Doc interactive (Swagger)** : `<URL>/docs`

> ⚠️ Render free met le service en veille après inactivité : le **premier appel** après une pause peut prendre **~40 s** (cold start). Prévois un loader.

---

## Authentification

L'API utilise un **token JWT** (valable 7 jours).

1. `POST /register` ou `POST /login` → renvoie un `access_token`.
2. Stocke ce token (ex. `localStorage`).
3. Pour toutes les routes protégées, ajoute l'en-tête :

```
Authorization: Bearer <access_token>
```

Si le token est absent/invalide/expiré → réponse **401**.

---

## Endpoints

### 🟢 Publics (sans token)

#### `POST /register` — Créer le compte du senior
```json
// body
{
  "nom": "Dupont",
  "prenom": "Jeanne",
  "adresse": "12 rue des Lilas, Lyon",
  "email": "jeanne.dupont@example.com",
  "password": "motdepasse",
  "guardian_email": "marie.dupont@gmail.com"   // optionnel
}
```
```json
// 200 OK
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "nom": "Dupont",
    "prenom": "Jeanne",
    "adresse": "12 rue des Lilas, Lyon",
    "email": "jeanne.dupont@example.com",
    "guardian_email": "marie.dupont@gmail.com",
    "subscription_active": false,
    "created_at": "2026-06-13T15:00:00"
  }
}
```
**Erreurs** : `400` si l'email est déjà utilisé.

---

#### `POST /login` — Connexion
```json
// body
{ "email": "jeanne.dupont@example.com", "password": "motdepasse" }
```
Réponse : identique à `/register` (`access_token` + `user`).
**Erreurs** : `401` si email ou mot de passe incorrect.

---

### 🔒 Protégés (header `Authorization: Bearer <token>`)

#### `GET /me` — Infos du compte connecté
```json
// 200 OK
{
  "id": 1, "nom": "Dupont", "prenom": "Jeanne",
  "adresse": "12 rue des Lilas, Lyon",
  "email": "jeanne.dupont@example.com",
  "guardian_email": "marie.dupont@gmail.com",
  "subscription_active": false,
  "created_at": "2026-06-13T15:00:00"
}
```

---

#### `GET /inbox` — La boîte mail du senior
Liste des mails, du plus récent au plus ancien.
> ⚠️ **Ne dit JAMAIS quels mails sont des tests de phishing** (volontaire). Affiche-les comme des mails normaux.

```json
// 200 OK
[
  {
    "id": "5",
    "sender_name": "Sécurité Banque Postale",
    "sender_email": "securite@labanque-postale-alerte.com",
    "subject": "URGENT : activité suspecte sur votre compte",
    "body": "<p>Bonjour Jeanne,</p>...<a href=\"...\">Cliquez ici</a>...",
    "opened": false,
    "received_at": "2026-06-13T15:05:00"
  }
]
```
- `id` est une **chaîne** (peut être un id interne ou un id Gmail).
- `body` est du **HTML** → affiche-le tel quel (ex. `dangerouslySetInnerHTML` / `v-html`). Les liens piège sont déjà dedans.

---

#### `GET /emails/{id}` — Ouvrir un mail
Renvoie le mail complet et le **marque comme lu** (`opened: true`).
```json
// 200 OK — même format qu'un élément de /inbox
{ "id": "5", "sender_name": "...", "subject": "...", "body": "<p>...</p>", "opened": true, "received_at": "..." }
```
**Erreurs** : `404` si le mail n'existe pas.

---

#### `POST /phishing/send` — Déposer un faux phishing de test
```json
// body  (scenario optionnel, laissé à null = aléatoire)
{ "scenario": null }
```
```json
// 200 OK
{
  "id": 7,
  "subject": "Votre colis est en attente de livraison",
  "tests_used": 1,
  "free_limit": 3,
  "message": "Test de phishing déposé dans la boîte."
}
```
**Erreurs** : `402` quand la limite gratuite (3 tests) est atteinte et que l'utilisateur n'est pas abonné.
```json
// 402
{ "detail": "Limite gratuite atteinte (3 tests). Abonnez-vous pour continuer la protection." }
```
→ C'est le moment d'afficher l'écran d'abonnement.

---

#### `GET /audit` — Bilan (le tableau de bord du proche)
```json
// 200 OK — NON abonné
{
  "phishing_sent": 3,
  "phishing_opened": 2,
  "phishing_clicked": 1,
  "risk_score": 33,                 // 0 à 100 = (clics / envoyés) x 100
  "subscription_active": false,
  "details": null,                  // null tant que non abonné
  "message": "Votre proche est tombé dans 1 piège(s). Abonnez-vous pour voir le rapport détaillé..."
}
```
```json
// 200 OK — abonné : "details" est rempli
{
  "phishing_sent": 3, "phishing_opened": 2, "phishing_clicked": 1,
  "risk_score": 33, "subscription_active": true,
  "details": [
    { "id": 7, "sender_name": "Chronopost Livraison",
      "subject": "Votre colis est en attente de livraison",
      "received_at": "2026-06-13T15:10:00", "opened": true, "clicked": true }
  ],
  "message": "1 piège(s) sur 3 ont fonctionné. Rapport détaillé ci-dessous."
}
```
→ Affiche `details` uniquement s'il n'est pas `null` (= produit payant).

---

#### `POST /subscribe` — Activer l'abonnement
Pas de body. Active `subscription_active` (stub, **pas de paiement réel** pour le hackathon).
```json
// 200 OK — renvoie le user mis à jour
{ "id": 1, "subscription_active": true, ... }
```

---

### 📧 Connexion d'un vrai Gmail (optionnel)

Permet de lire la **vraie** boîte du senior et d'y injecter les tests.

#### `GET /gmail/connect` (auth) — Lance la connexion Google
```json
// 200 OK
{ "auth_url": "https://accounts.google.com/o/oauth2/auth?..." }
```
→ Le front **redirige** ou ouvre `auth_url`. Après autorisation, Google renvoie vers le backend (`/gmail/callback`), qui redirige ensuite vers `FRONT_URL?gmail=connected`.

#### `GET /gmail/status` (auth) — État de la connexion
```json
// 200 OK
{ "connected": true, "gmail_address": "jeanne@gmail.com" }
```

> Une fois Gmail connecté, `/inbox`, `/emails/{id}` et `/phishing/send` basculent automatiquement sur le vrai Gmail. **Aucun changement côté front** : mêmes routes, mêmes réponses.

---

## 🔗 Le lien piège (à savoir, pas à appeler)

Quand un mail de phishing contient un lien `.../track/click/<token>`, le **clic du senior** (depuis le mail) est tracé par le backend qui affiche une page de sensibilisation. Le front n'a rien à faire : ça remonte ensuite dans `/audit` (`clicked: true`).

---

## Récap des codes d'erreur

| Code | Sens |
|------|------|
| `401` | Token manquant, invalide ou expiré → renvoyer vers login |
| `400` | Données invalides (ex. email déjà utilisé) |
| `402` | Limite gratuite atteinte → écran d'abonnement |
| `404` | Ressource introuvable (mail, user) |
| `422` | Body mal formé (validation Pydantic) |

## CORS
CORS est **ouvert à tous les domaines** (`*`) — le front peut appeler l'API depuis n'importe quelle origine sans config.
