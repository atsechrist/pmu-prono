# export_pdf.py — Genere un PDF propre de la selection Placé du jour.

from fpdf import FPDF


from datetime import datetime, timezone


def _txt(s):
    """Nettoie une chaine pour l'encodage latin-1 des polices de base."""
    if s is None:
        return ""
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _heure_gmt(ms):
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).strftime("%H:%M")
    except (ValueError, TypeError, OSError):
        return ""


def detail_mois_pdf(mois: str, dfm) -> bytes:
    """PDF du detail des paris Placé FORT d'un mois, trie par date puis heure.
    dfm : colonnes date, heure_depart, course, hippodrome, num, nom, proba, place, rapport_place, gain."""
    dfm = dfm.sort_values(["date", "heure_depart"], na_position="last")
    pdf = FPDF(orientation="L", unit="mm", format="A4")   # paysage
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _txt(f"Detail Place FORT - {mois}"), ln=1)
    n = len(dfm)
    nb_place = int((dfm["place"] == 1).sum())
    benef = dfm["gain"].sum() - n
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    taux = (nb_place / n * 100) if n else 0
    pdf.cell(0, 6, _txt(f"{n} paris  |  {nb_place} places ({taux:.0f}%)  |  "
                        f"benefice {benef:+.0f} EUR (mise 1/pari)  |  trie par heure"), ln=1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    cols = [("Date", 24), ("Heure", 14), ("Course", 16), ("Hippodrome", 42), ("N", 8),
            ("Cheval", 55), ("Proba", 14), ("Cote", 14), ("Resultat", 30), ("Gain", 18)]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for titre, w in cols:
        pdf.cell(w, 7, _txt(titre), border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for _, r in dfm.iterrows():
        place = int(r["place"]) == 1
        cote = r.get("rapport_place")
        cote = "" if cote is None or (isinstance(cote, float) and cote != cote) else f"{cote:.2f}"
        gain = float(r["gain"])
        res = f"place ({cote})" if place else "non place"
        cells = [
            (str(r["date"]), 24), (_heure_gmt(r["heure_depart"]), 14),
            (str(r["course"]), 16), (str(r["hippodrome"])[:26], 42),
            (str(int(r["num"])), 8), (str(r["nom"])[:34], 55),
            (f"{r['proba']*100:.0f}%", 14), (cote, 14),
            ("PLACE" if place else "rate", 30), (f"{gain-1:+.2f}", 18),
        ]
        for val, w in cells:
            pdf.cell(w, 5.5, _txt(val), border=1)
        pdf.ln()

    return bytes(pdf.output())


def selection_pdf(jour_iso: str, picks) -> bytes:
    """picks : DataFrame trie (colonnes course, hippodrome, num_pmu, nom, driver,
    proba_place, cote_reference, position). Retourne le PDF en bytes."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()

    # En-tete
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _txt("PMU Prono - Selection Place du jour"), ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 7, _txt(f"Courses du {jour_iso}  -  Strategie SECURITE (le Place)"), ln=1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    fort = picks[picks["proba_place"] >= 0.6]
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _txt(f"{len(fort)} pronostics FORT (proba de place >= 60%)"), ln=1)
    pdf.ln(1)

    # En-tete de tableau
    cols = [("Course", 20), ("Hippodrome", 40), ("N", 10), ("Cheval", 52),
            ("Place", 16), ("Cote", 14), ("Resultat", 30)]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for titre, w in cols:
        pdf.cell(w, 7, _txt(titre), border=1, fill=True, align="C")
    pdf.ln()

    # Lignes
    pdf.set_font("Helvetica", "", 9)
    for _, r in fort.iterrows():
        pos = r.get("position")
        pos_vide = pos is None or (isinstance(pos, float) and pos != pos)
        if not r.get("course_finie"):
            res = "a venir"
        elif pos_vide:
            res = "hors arrivee"           # course finie mais cheval non classe
        elif int(pos) <= 3:
            res = f"{int(pos)}e - place OK"
        else:
            res = f"{int(pos)}e - rate"
        cote = "" if r.get("cote_reference") is None or r["cote_reference"] != r["cote_reference"] else f"{r['cote_reference']:.1f}"
        cells = [
            (r["course"], 20), (str(r["hippodrome"])[:24], 40),
            (str(int(r["num_pmu"])), 10), (str(r["nom"])[:32], 52),
            (f"{r['proba_place']*100:.0f}%", 16), (cote, 14), (res, 30),
        ]
        for val, w in cells:
            pdf.cell(w, 6, _txt(val), border=1)
        pdf.ln()

    # Pied de page
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 4, _txt(
        "Rappel : jeu d'argent = risque. Ce modele a un petit avantage backteste "
        "(~+5%/an au place sur les FORT) mais ne garantit aucun gain. "
        "Joue de facon responsable, avec de l'argent que tu peux te permettre de perdre."))

    return bytes(pdf.output())
