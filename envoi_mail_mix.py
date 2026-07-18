# envoi_mail_mix.py — Genere la selection MIX du jour et l'envoie par email.
#
# Lance automatiquement chaque matin par GitHub Actions (.github/workflows/mail_mix.yml).
# Reproduit EXACTEMENT la selection MIX du dashboard : Place FORT (>=60%) + Gagnant Moyen (<40%).
#
# Identifiants lus depuis les variables d'environnement (secrets GitHub) :
#   GMAIL_USER          -> ton adresse Gmail (ex: atsechrist@gmail.com)
#   GMAIL_APP_PASSWORD  -> un "mot de passe d'application" Gmail (16 lettres, PAS ton mot de passe normal)
#   MAIL_TO             -> destinataire (optionnel ; par defaut = GMAIL_USER)

import os
import ssl
import smtplib
from datetime import date
from email.message import EmailMessage

import pandas as pd

from pronos_jour import pronostics
from export_pdf import mix_pdf


def construire_mix(df):
    """Selection MIX = Place FORT (>=60%) au PLACE + Gagnant Moyen (<40%) au GAGNANT.
    Identique a la logique du dashboard."""
    pf = df[(df["rang_place"] == 1) & (df["proba_place"] >= 0.6)].copy()
    pf["Pari"] = "PLACÉ"
    pf["proba"] = pf["proba_place"]

    gm = df[(df["rang_gagnant"] == 1) & (df["proba_gagnant"] < 0.4)].copy()
    gm["Pari"] = "GAGNANT"
    gm["proba"] = gm["proba_gagnant"]

    mix = pd.concat([pf, gm], ignore_index=True)
    return mix.sort_values("heure", na_position="last")


def part_cotes_publiees(df):
    """Part des partants dont la cote du matin est deja publiee (0 a 1)."""
    if not len(df):
        return 0.0
    cotes = pd.to_numeric(df["cote_reference"], errors="coerce")
    return float(cotes.notna().mean())


def envoyer_email(jour, pdf_bytes, total, nb_place, nb_gagnant, part_cotes):
    """Envoie le PDF en piece jointe via Gmail (SMTP SSL)."""
    user = os.environ["GMAIL_USER"]
    mot_de_passe = os.environ["GMAIL_APP_PASSWORD"]
    destinataire = os.environ.get("MAIL_TO") or user

    alerte = ""
    if part_cotes < 0.80:
        alerte = (f"\n⚠️  Attention : seulement {part_cotes:.0%} des cotes du matin etaient "
                  "publiees au moment de l'envoi. La liste peut encore evoluer legerement — "
                  "verifie sur le dashboard avant de jouer si tu joues des courses tardives.\n")

    msg = EmailMessage()
    msg["Subject"] = f"🐎 Selection MIX du {jour} — {total} paris"
    msg["From"] = user
    msg["To"] = destinataire
    msg.set_content(
        f"Salut,\n\n"
        f"Voici ta selection MIX du jour ({jour}), en piece jointe (PDF).\n\n"
        f"  - {total} paris  ({nb_place} au PLACE + {nb_gagnant} au GAGNANT)\n"
        f"  - Tries par heure de course\n"
        f"  - Cotes du matin publiees : {part_cotes:.0%}\n"
        f"{alerte}\n"
        f"Rappel : jeu d'argent = risque. Joue de facon responsable, "
        f"avec de l'argent que tu peux te permettre de perdre.\n\n"
        f"— Ton assistant PMU Prono"
    )
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf",
                       filename=f"selection_mix_{jour}.pdf")

    contexte = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexte) as serveur:
        serveur.login(user, mot_de_passe)
        serveur.send_message(msg)
    print(f"[mail_mix] Email envoye a {destinataire}.")


def main():
    jour = date.today().isoformat()
    print(f"[mail_mix] Jour : {jour}")

    df = pronostics(jour)
    if df is None or not len(df):
        print("[mail_mix] Aucune course francaise aujourd'hui — pas d'email.")
        return

    part_cotes = part_cotes_publiees(df)
    print(f"[mail_mix] Cotes du matin publiees : {part_cotes:.0%}")

    mix = construire_mix(df)
    if not len(mix):
        print("[mail_mix] Aucun pari MIX aujourd'hui — pas d'email.")
        return

    pdf_bytes = mix_pdf(jour, mix.rename(columns={"num_pmu": "num", "Pari": "pari"}))
    nb_place = int((mix["Pari"] == "PLACÉ").sum())
    nb_gagnant = int((mix["Pari"] == "GAGNANT").sum())
    print(f"[mail_mix] {len(mix)} paris ({nb_place} place + {nb_gagnant} gagnant).")

    # DRY_RUN=1 -> genere le PDF sans envoyer (pour tester en local)
    if os.environ.get("DRY_RUN") == "1":
        chemin = f"selection_mix_{jour}.pdf"
        with open(chemin, "wb") as f:
            f.write(pdf_bytes)
        print(f"[mail_mix] DRY_RUN : PDF ecrit dans {chemin} (email non envoye).")
        return

    envoyer_email(jour, pdf_bytes, len(mix), nb_place, nb_gagnant, part_cotes)


if __name__ == "__main__":
    main()
