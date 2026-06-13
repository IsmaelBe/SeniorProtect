#!/usr/bin/env bash
#
# Test de bout en bout de l'API Senior Shield.
# Usage : ./test_api.sh https://ton-app.onrender.com
#         ./test_api.sh                # défaut : http://localhost:8000
#
set -euo pipefail

BASE="${1:-http://localhost:8000}"
BASE="${BASE%/}"   # enlève un éventuel / final

# Email unique à chaque exécution pour ne pas tomber sur "email déjà utilisé".
EMAIL="test+$(date +%s)@example.com"
PASSWORD="motdepasse"

# Petit helper pour extraire un champ JSON sans dépendre de jq.
json() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

say() { printf "\n\033[1;34m== %s ==\033[0m\n" "$1"; }
ok()  { printf "\033[1;32m✓ %s\033[0m\n" "$1"; }

say "0. Réveil du service (Render free peut prendre ~40s)"
curl -s --max-time 90 "$BASE/" ; echo

say "1. Inscription ($EMAIL)"
REG=$(curl -s -X POST "$BASE/register" \
  -H "Content-Type: application/json" \
  -d "{\"nom\":\"Dupont\",\"prenom\":\"Jeanne\",\"adresse\":\"12 rue des Lilas, Lyon\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"guardian_email\":\"marie@gmail.com\"}")
TOKEN=$(echo "$REG" | json "['access_token']")
USER_ID=$(echo "$REG" | json "['user']['id']")
ok "Compte créé (id=$USER_ID), token récupéré"
AUTH="Authorization: Bearer $TOKEN"

say "2. /me"
ME=$(curl -s "$BASE/me" -H "$AUTH" | json "['email']")
ok "Connecté en tant que $ME"

say "3. /login (vérifie qu'on peut se reconnecter)"
TT=$(curl -s -X POST "$BASE/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | json "['token_type']")
ok "Login OK (token_type=$TT)"

say "4. /inbox initial"
COUNT=$(curl -s "$BASE/inbox" -H "$AUTH" | json " .__len__()")
ok "$COUNT mail(s) légitime(s) dans la boîte"

say "5. Envoi de 3 tests de phishing (limite gratuite)"
for i in 1 2 3; do
  RESP=$(curl -s -X POST "$BASE/phishing/send" -H "$AUTH" -H "Content-Type: application/json" -d '{}')
  SUBJ=$(echo "$RESP" | json "['subject']")
  USED=$(echo "$RESP" | json "['tests_used']")
  ok "Test $USED/3 déposé : \"$SUBJ\""
done

say "6. 4e envoi : doit être REFUSÉ (402, limite gratuite atteinte)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/phishing/send" -H "$AUTH" -H "Content-Type: application/json" -d '{}')
[ "$CODE" = "402" ] && ok "Bien refusé (HTTP 402)" || printf "\033[1;31m✗ attendu 402, reçu %s\033[0m\n" "$CODE"

say "7. Récupération du lien piège du 1er phishing"
INBOX=$(curl -s "$BASE/inbox" -H "$AUTH")
TRAP=$(echo "$INBOX" | python3 -c "
import sys,json,re
mails=json.load(sys.stdin)
for m in mails:
    found=re.search(r'/track/click/([0-9a-f]+)', m['body'])
    if found:
        print(found.group(1)); break
")
if [ -n "$TRAP" ]; then
  ok "Token de piège trouvé : $TRAP"
  say "8. Simulation du clic sur le lien piège"
  curl -s -o /dev/null -w "page de sensibilisation : HTTP %{http_code}\n" "$BASE/track/click/$TRAP"
  ok "Clic enregistré"
else
  printf "\033[1;31m✗ aucun lien piège trouvé dans l'inbox\033[0m\n"
fi

say "9. /audit (non abonné : chiffres globaux, pas de détail)"
curl -s "$BASE/audit" -H "$AUTH" | python3 -c "
import sys,json
a=json.load(sys.stdin)
print(f\"  envoyés={a['phishing_sent']} ouverts={a['phishing_opened']} cliqués={a['phishing_clicked']} risque={a['risk_score']}%\")
print(f\"  abonné={a['subscription_active']}  détails={'oui' if a['details'] else 'non (réservé abonnés)'}\")
"

say "10. /subscribe puis /audit (abonné : détail débloqué)"
curl -s -X POST "$BASE/subscribe" -H "$AUTH" > /dev/null
ok "Abonnement activé"
curl -s "$BASE/audit" -H "$AUTH" | python3 -c "
import sys,json
a=json.load(sys.stdin)
print(f\"  abonné={a['subscription_active']}  détails={len(a['details']) if a['details'] else 0} mail(s)\")
for d in (a['details'] or []):
    print(f\"   - {d['subject']!r:50}  ouvert={d['opened']} cliqué={d['clicked']}\")
"

printf "\n\033[1;32m✅ Tous les tests sont passés.\033[0m\n"
