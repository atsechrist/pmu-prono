# export_pdf.py — Genere un PDF propre de la selection Placé du jour.

from fpdf import FPDF


def _txt(s):
    """Nettoie une chaine pour l'encodage latin-1 des polices de base."""
    if s is None:
        return ""
    return str(s).encode("latin-1", "replace").decode("latin-1")


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
