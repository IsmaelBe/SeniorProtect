"""Faux mails de phishing (modèles statiques) pour l'exercice de sensibilisation.

Pas d'IA : on pioche dans une banque de modèles. Le corps contient le marqueur
{{LINK}} que le backend remplace par le vrai lien de traçage avant livraison.
"""
import random

# Modèles d'arnaques classiques visant les personnes âgées en France.
# {prenom} est remplacé par le backend ; {{LINK}} marque l'emplacement du lien piège.
TEMPLATES = [
    {
        "sender_name": "Sécurité Banque Postale",
        "sender_email": "securite@labanque-postale-alerte.com",
        "subject": "URGENT : activité suspecte sur votre compte",
        "body": (
            "<p>Bonjour {prenom},</p>"
            "<p>Nous avons détecté une <strong>connexion inhabituelle</strong> "
            "sur votre compte bancaire. Par mesure de sécurité, votre accès a été "
            "temporairement suspendu.</p>"
            "<p>Pour réactiver votre compte sous 24h, confirmez votre identité : {{LINK}}</p>"
            "<p>Sans action de votre part, votre compte sera définitivement bloqué.</p>"
            "<p>Le service sécurité.</p>"
        ),
    },
    {
        "sender_name": "Chronopost Livraison",
        "sender_email": "suivi@chronopost-colis-livraison.net",
        "subject": "Votre colis est en attente de livraison",
        "body": (
            "<p>Bonjour {prenom},</p>"
            "<p>Votre colis n'a pas pu être livré. Des <strong>frais de douane "
            "de 1,99 €</strong> restent à régler.</p>"
            "<p>Réglez maintenant pour recevoir votre colis : {{LINK}}</p>"
            "<p>Passé 48h, le colis sera retourné à l'expéditeur.</p>"
        ),
    },
    {
        "sender_name": "Direction Générale des Finances Publiques",
        "sender_email": "remboursement@impots-gouv-remboursement.com",
        "subject": "Remboursement d'impôt de 384,29 € en attente",
        "body": (
            "<p>Bonjour {prenom},</p>"
            "<p>Suite au recalcul de votre déclaration, vous bénéficiez d'un "
            "<strong>remboursement de 384,29 €</strong>.</p>"
            "<p>Indiquez vos coordonnées bancaires pour recevoir le virement : {{LINK}}</p>"
            "<p>Cordialement, votre centre des finances publiques.</p>"
        ),
    },
    {
        "sender_name": "Assurance Maladie - Ameli",
        "sender_email": "contact@ameli-carte-vitale.fr",
        "subject": "Votre carte Vitale doit être mise à jour",
        "body": (
            "<p>Bonjour {prenom},</p>"
            "<p>Votre <strong>carte Vitale</strong> arrive à expiration. Sans mise à "
            "jour, vos remboursements seront suspendus.</p>"
            "<p>Mettez à jour vos informations ici : {{LINK}}</p>"
            "<p>L'Assurance Maladie.</p>"
        ),
    },
]


def generate_phishing_email(prenom: str, nom: str = None, scenario: str = None) -> dict:
    """Retourne un dict {sender_name, sender_email, subject, body}.

    body contient le marqueur {{LINK}} à remplacer par le backend.
    """
    tpl = random.choice(TEMPLATES)
    return {
        "sender_name": tpl["sender_name"],
        "sender_email": tpl["sender_email"],
        "subject": tpl["subject"],
        "body": tpl["body"].replace("{prenom}", prenom),
    }


# Quelques mails légitimes pour que la boîte ait l'air vivante (mode simulé).
LEGIT_EMAILS = [
    {
        "sender_name": "Pharmacie du Centre",
        "sender_email": "contact@pharmacieducentre.fr",
        "subject": "Votre ordonnance est prête",
        "body": "<p>Bonjour,</p><p>Votre traitement est disponible à la pharmacie. "
        "Bonne journée !</p>",
    },
    {
        "sender_name": "Marie (votre fille)",
        "sender_email": "marie.dupont@gmail.com",
        "subject": "On vient dimanche !",
        "body": "<p>Coucou,</p><p>On passe dimanche midi avec les enfants. "
        "Tu veux qu'on apporte le dessert ? Bisous</p>",
    },
    {
        "sender_name": "Mairie de votre commune",
        "sender_email": "newsletter@mairie.fr",
        "subject": "Programme des animations du mois",
        "body": "<p>Retrouvez toutes les animations et sorties organisées ce mois-ci "
        "pour les seniors.</p>",
    },
]
