# dashboard.py — Interface web des pronostics du jour.
#
# Lancement :  streamlit run dashboard.py
# (ou double-clic sur "Lancer le dashboard.bat")

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from pronos_jour import pronostics
from export_pdf import selection_pdf

st.set_page_config(page_title="PMU Prono", page_icon="🐎", layout="wide")


# ─── Porte d'entree : mot de passe ────────────────────────────
def _mot_de_passe_attendu():
    """Lit le mot de passe dans les secrets Streamlit ; sinon valeur par defaut (local)."""
    try:
        return st.secrets["password"]
    except Exception:
        return "pmu2026"   # defaut pour tester en local ; a changer dans les secrets en ligne


def verifier_acces():
    """Affiche une porte de connexion tant que le bon mot de passe n'est pas saisi."""
    if st.session_state.get("acces_ok"):
        return
    st.title("🔒 PMU Prono")
    saisie = st.text_input("Mot de passe", type="password")
    if saisie:
        if saisie == _mot_de_passe_attendu():
            st.session_state["acces_ok"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    st.stop()


verifier_acces()

st.title("🐎 PMU Prono — Pronostics du jour")
st.caption("Modele entraine sur 13 ans de courses FRANCAISES. Strategie SECURITE : le Placé. "
           "(Courses etrangeres exclues.)")

from datetime import datetime, timezone

def heure_gmt(ms):
    """Convertit un timestamp (ms) en heure GMT 'HH:MM'."""
    if ms is None or (isinstance(ms, float) and ms != ms):
        return ""
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%H:%M")
    except (ValueError, OSError):
        return ""

# --- Choix de la date + bouton actualiser ---
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    # Choix libre : tout l'historique disponible (mai 2013) jusqu'a demain
    jour = st.date_input("Date des courses", value=date.today(),
                         min_value=date(2013, 5, 1),
                         max_value=date.today() + timedelta(days=1))
with col2:
    st.write("")
    st.write("")
    rafraichir = st.button("🔄 Actualiser les résultats")

# --- Chargement (mis en cache 3 min ; le bouton force le rechargement) ---
@st.cache_data(ttl=180, show_spinner="Recuperation des courses et calcul des pronos...")
def charger(jour_iso):
    return pronostics(jour_iso), datetime.now().strftime("%H:%M:%S")

if rafraichir:
    charger.clear()

df, heure_charge = charger(jour.isoformat())

if df is None or df.empty:
    st.warning("Aucune course trouvee pour cette date (le programme n'est peut-etre pas encore publie).")
    st.stop()

nb_finies = int(df.groupby("course")["course_finie"].first().sum())
st.success(f"{df['course'].nunique()} courses - {len(df)} partants analyses  "
           f"·  {nb_finies} courses terminées  ·  chargé à {heure_charge}")
st.caption("Les résultats se figent au chargement. Clique **🔄 Actualiser les résultats** "
           "pour récupérer les arrivées des courses courues depuis.")

# ═══════════════════════════════════════════════════════════════
#  SELECTION DU JOUR — les pronos Placé les plus surs
# ═══════════════════════════════════════════════════════════════
st.header("⭐ Sélection Placé du jour")
st.caption("Les chevaux que le modele juge les plus surs de finir dans les 3 (courses FR). "
           "Seuil 'FORT' = proba de place >= 60%.")

tri_placé = st.selectbox(
    "Trier la sélection (s'applique aussi au PDF)",
    ["Heure GMT (chronologique)", "Confiance du modèle", "Hippodrome"],
    index=0, key="tri_place")

def fmt_resultat(row):
    """Affiche le verdict du cheval choisi selon l'etat de la course."""
    if not row["course_finie"]:
        return "⏳ à venir"
    pos = row["position"]
    if pd.notna(pos) and int(pos) <= 3:
        return f"{int(pos)}e  ✅ placé"
    if pd.notna(pos):
        return f"{int(pos)}e  ❌ non placé"
    return "❌ non placé"   # course finie mais cheval hors arrivee (chute, disq...)

top = df[df["rang_place"] == 1].copy()
top["Confiance"] = top["proba_place"].apply(lambda p: "🟢 FORT" if p >= 0.6 else "🟡 Moyen")
top["Résultat"] = top.apply(fmt_resultat, axis=1)

# Tri choisi par l'utilisateur — applique au tableau ET au PDF
if tri_placé.startswith("Heure"):
    top = top.sort_values("heure", ascending=True, na_position="last")
elif tri_placé.startswith("Hippodrome"):
    top = top.sort_values(["hippodrome", "heure"], na_position="last")
else:
    top = top.sort_values("proba_place", ascending=False)

# --- Indicateur de reussite du jour, par niveau de confiance ---
def bloc_reussite(titre, sous_ensemble):
    couru = sous_ensemble[sous_ensemble["course_finie"]]   # course finie = pari resolu
    st.markdown(f"**{titre}**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pronos du jour", len(sous_ensemble))
    c2.metric("Déjà courus", len(couru))
    if len(couru):
        place = couru["position"] <= 3
        nb_ok = int(place.sum())
        c3.metric("Réussite (placés)", f"{place.mean():.0%}", f"{nb_ok}/{len(couru)}")
        # Benefice : mise 1 par pari couru ; gain = rapport_place si place, sinon 0
        gains = couru["rapport_place"].where(place, 0).fillna(0).sum()
        profit = gains - len(couru)
        c4.metric("Bénéfice (1€/pari)", f"{profit:+.1f} €", f"ROI {profit/len(couru):+.0%}")
    else:
        c3.metric("Réussite (placés)", "—")
        c4.metric("Bénéfice (1€/pari)", "—")

col_f, col_m = st.columns(2)
with col_f:
    bloc_reussite("🟢 FORT (proba ≥ 60%)", top[top["proba_place"] >= 0.6])
with col_m:
    bloc_reussite("🟡 Moyen (proba < 60%)", top[top["proba_place"] < 0.6])

top["Heure GMT"] = top["heure"].apply(heure_gmt)

COLS = ["course", "Heure GMT", "hippodrome", "num_pmu", "nom", "driver",
        "proba_place", "cote_reference", "Résultat"]
NOMS = ["Course", "Heure GMT", "Hippodrome", "N°", "Cheval", "Driver/Jockey",
        "Proba placé", "Cote matin", "Résultat"]

def format_table(sous_ensemble):
    v = sous_ensemble[COLS].copy()
    v.columns = NOMS
    v["Proba placé"] = (v["Proba placé"] * 100).round(0).astype(int).astype(str) + "%"
    return v

fort = top[top["proba_place"] >= 0.6]
moyen = top[top["proba_place"] < 0.6]

# ═══ LA LISTE À JOUER : Placé FORT, isolé ═══
st.subheader(f"🎯 À JOUER — {len(fort)} paris Placé FORT")
st.caption(f"Ta stratégie : jouer ces chevaux au **placé**. Ordre : **{tri_placé}** (idem PDF).")
st.dataframe(format_table(fort), use_container_width=True, hide_index=True,
             height=min(700, 60 + 35 * len(fort)))

pdf_bytes = selection_pdf(jour.isoformat(), top)
st.download_button(
    "📄 Télécharger MES paris du jour (PDF)",
    data=pdf_bytes,
    file_name=f"paris_place_fort_{jour.isoformat()}.pdf",
    mime="application/pdf",
)

# Moyen : secondaire, replié (à ne PAS jouer)
with st.expander(f"🟡 Voir aussi les {len(moyen)} pronos Moyen (indicatif — à ne pas jouer)"):
    st.dataframe(format_table(moyen), use_container_width=True, hide_index=True,
                 height=min(500, 60 + 35 * len(moyen)))

# ═══════════════════════════════════════════════════════════════
#  SELECTION GAGNANT du jour
# ═══════════════════════════════════════════════════════════════
st.header("🏆 Sélection Gagnant du jour")
st.caption("Le cheval que le modele juge le plus probable de GAGNER chaque course (FR). "
           "Bien plus dur que le placé : meme le meilleur pick ne gagne qu'~1 fois sur 3. "
           "Seuil 'FORT' = proba de gain >= 40% (~43% de victoires au backtest).")

def fmt_res_gagnant(row):
    if not row["course_finie"]:
        return "⏳ à venir"
    pos = row["position"]
    if pd.notna(pos) and int(pos) == 1:
        return "1er  ✅ gagné"
    if pd.notna(pos):
        return f"{int(pos)}e  ❌"
    return "❌ non classé"

topg = df[df["rang_gagnant"] == 1].copy()
topg["Confiance"] = topg["proba_gagnant"].apply(lambda p: "🟢 FORT" if p >= 0.40 else "🟡 Moyen")
topg["Résultat"] = topg.apply(fmt_res_gagnant, axis=1)
topg = topg.sort_values("proba_gagnant", ascending=False)

def bloc_gagnant(titre, sub):
    couru = sub[sub["course_finie"]]
    st.markdown(f"**{titre}**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pronos du jour", len(sub))
    c2.metric("Déjà courus", len(couru))
    if len(couru):
        win = couru["position"] == 1
        c3.metric("Victoires", f"{win.mean():.0%}", f"{int(win.sum())}/{len(couru)}")
        gains = couru["rapport_gagnant"].where(win, 0).fillna(0).sum()
        profit = gains - len(couru)
        c4.metric("Bénéfice (1€/pari)", f"{profit:+.1f} €", f"ROI {profit/len(couru):+.0%}")
    else:
        c3.metric("Victoires", "—")
        c4.metric("Bénéfice (1€/pari)", "—")

cg1, cg2 = st.columns(2)
with cg1:
    bloc_gagnant("🟢 FORT (proba ≥ 40%)", topg[topg["proba_gagnant"] >= 0.40])
with cg2:
    bloc_gagnant("🟡 Moyen (proba < 40%)", topg[topg["proba_gagnant"] < 0.40])

topg["Heure GMT"] = topg["heure"].apply(heure_gmt)
vueg = topg[["course", "Heure GMT", "hippodrome", "num_pmu", "nom", "driver",
             "proba_gagnant", "cote_reference", "Confiance", "Résultat"]].copy()
vueg.columns = ["Course", "Heure GMT", "Hippodrome", "N°", "Cheval", "Driver/Jockey",
                "Proba gagnant", "Cote matin", "Confiance", "Résultat"]
vueg["Proba gagnant"] = (vueg["Proba gagnant"] * 100).round(0).astype(int).astype(str) + "%"
st.caption("Trié par confiance du modèle (le plus probable gagnant en premier). "
           "Clique l'en-tête pour trier par heure ou par course.")
st.dataframe(vueg, use_container_width=True, hide_index=True, height=min(600, 60 + 35 * len(vueg)))

st.warning("⚠️ Le Gagnant est plus risqué et plus variable que le Placé (on perd souvent). "
           "A jouer avec parcimonie. Le ROI backteste reste un plafond optimiste, pas une promesse.")

# ═══════════════════════════════════════════════════════════════
#  QUINTE+ du jour
# ═══════════════════════════════════════════════════════════════
st.header("🎰 Quinté+ du jour")
q = df[df["quinte"]].copy() if "quinte" in df.columns else df.iloc[0:0]
if q.empty:
    st.info("Aucune course Quinté+ identifiee pour cette date (programme pas encore publie, "
            "ou le Quinté est prevu un autre jour).")
else:
    course_q, hippo_q = q["course"].iloc[0], q["hippodrome"].iloc[0]
    heure_q = heure_gmt(q["heure"].iloc[0])
    q = q.sort_values("proba_place", ascending=False).reset_index(drop=True)
    q["Rang"] = q.index + 1
    st.subheader(f"Course : {course_q} — {hippo_q}  ({len(q)} partants)  ·  {heure_q} GMT")

    if q["course_finie"].any():
        top5 = q.dropna(subset=["position"]).sort_values("position").head(5)
        arr = "  -  ".join(f"{int(r['position'])}. #{int(r['num_pmu'])} {r['nom']}" for _, r in top5.iterrows())
        st.success(f"🏁 Arrivée (5 premiers) : {arr}")
        gagnants_num = set(top5["num_pmu"])
        c7, c8 = st.columns(2)
        c7.metric("Base Top 7 : les 5 dedans ?", f"{q.head(7)['num_pmu'].isin(gagnants_num).sum()}/5")
        c8.metric("Base Top 8 : les 5 dedans ?", f"{q.head(8)['num_pmu'].isin(gagnants_num).sum()}/5")
    else:
        st.caption("🕐 Course pas encore courue.")

    vue = q.head(10)[["Rang", "num_pmu", "nom", "driver", "proba_place", "proba_gagnant", "cote_reference"]].copy()
    vue.columns = ["Rang", "N°", "Cheval", "Driver/Jockey", "Proba placé", "Proba gagnant", "Cote matin"]
    vue["Proba placé"] = (vue["Proba placé"] * 100).round(0).astype(int).astype(str) + "%"
    vue["Proba gagnant"] = (vue["Proba gagnant"] * 100).round(0).astype(int).astype(str) + "%"
    st.markdown("**Classement du modèle** — joue les premiers comme base :")
    st.dataframe(vue, use_container_width=True, hide_index=True, height=min(500, 60 + 35 * len(vue)))

    st.markdown("**Chances d'avoir les 5 premiers dans ta base** (backteste, en désordre) :")
    ref = pd.DataFrame({
        "Base (chevaux)": [5, 6, 7, 8, 10],
        "Quinté 5/5": ["5%", "14%", "26%", "41%", "70%"],
        "Bonus 4/5": ["32%", "50%", "67%", "79%", "93%"],
        "Tickets a boxer": [1, 6, 21, 56, 252],
    })
    st.dataframe(ref, use_container_width=True, hide_index=True)

st.warning("⚠️ Le Quinté+ est une LOTERIE : meme avec une bonne base, tu perds la plupart du "
           "temps, et le gros lot demande l'ordre EXACT. A jouer pour le plaisir/le jackpot, "
           "avec de petites sommes — jamais comme une strategie de gain.")

# ═══════════════════════════════════════════════════════════════
#  DETAIL PAR COURSE
# ═══════════════════════════════════════════════════════════════
st.header("🔎 Détail par course")
courses = df["course"].unique().tolist()
choix = st.selectbox("Choisir une course", courses,
                     format_func=lambda c: f"{c} — {df[df['course']==c]['hippodrome'].iloc[0]}")

d = df[df["course"] == choix].copy().sort_values("proba_place", ascending=False)

# Arrivee officielle si la course est courue
if d["course_finie"].any():
    ordre = d.dropna(subset=["position"]).sort_values("position")
    arrivee = " - ".join(f"{int(r['position'])}.#{int(r['num_pmu'])} {r['nom']}"
                         for _, r in ordre.head(5).iterrows())
    st.success(f"🏁 **Arrivée :** {arrivee}")
else:
    st.caption("🕐 Course pas encore courue — arrivée a venir.")

def fmt_arr(row):
    if not row["course_finie"]:
        return "—"
    pos = row["position"]
    if pd.isna(pos):
        return "hors arrivée"   # n'a pas fini (chute, disq...)
    pos = int(pos)
    return f"{pos}e ✅" if pos <= 3 else f"{pos}e"

d["Arrivée"] = d.apply(fmt_arr, axis=1)
detail = d[["num_pmu", "nom", "driver", "musique", "proba_place", "proba_gagnant", "cote_reference", "Arrivée"]].copy()
detail.columns = ["N°", "Cheval", "Driver/Jockey", "Musique", "Proba placé", "Proba gagnant", "Cote matin", "Arrivée"]
detail["Proba placé"] = (detail["Proba placé"] * 100).round(0).astype(int).astype(str) + "%"
detail["Proba gagnant"] = (detail["Proba gagnant"] * 100).round(0).astype(int).astype(str) + "%"
st.dataframe(detail, use_container_width=True, hide_index=True,
             height=min(600, 60 + 35 * len(detail)))

import os

# ═══════════════════════════════════════════════════════════════
#  HISTORIQUE DE PERFORMANCE (backtest hors echantillon 2021-2026)
# ═══════════════════════════════════════════════════════════════
st.header("📈 Historique de performance")
st.caption("Mesuré sur 2021-2026 (courses FR) — periode que le modele n'a JAMAIS vue a "
           "l'entrainement. Gains reels, mise 1 par pari.")
st.warning("⚠️ Les ROI positifs viennent en partie d'effets structurels du marche francais "
           "(favoris sous-paries au placé). En pariant pour de vrai, ta mise fait BAISSER le "
           "rapport → rendement reel plus bas. A voir comme un plafond optimiste, pas une promesse.")

def afficher_perf(hist, strat, label_succes, txt_fort, txt_moyen):
    h = hist[hist["strategie"] == strat]
    if h.empty:
        st.caption("Pas de donnees.")
        return

    def bloc(titre, hh):
        st.markdown(f"**{titre}**")
        if not len(hh):
            st.caption("Aucun pari.")
            return
        p = int(hh["paris"].sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Paris (total)", f"{p:,}".replace(",", " "))
        m2.metric(label_succes, f"{hh['succes'].sum()/p:.1%}")
        m3.metric("ROI global", f"{hh['profit'].sum()/p:+.1%}")
        m4.metric("Bénéfice (1€/pari)", f"{hh['profit'].sum():+,.0f} €".replace(",", " "))

    bloc(f"🟢 FORT ({txt_fort})", h[h["confiance"] == "FORT"])
    st.write("")
    bloc(f"🟡 Moyen ({txt_moyen})", h[h["confiance"] == "Moyen"])
    piv = (h.pivot_table(index="date", columns="confiance", values="profit", aggfunc="sum")
             .fillna(0).sort_index().cumsum())
    piv.columns = [f"{c} (€)" for c in piv.columns]
    st.caption("Gains cumulés (mise 1€/pari depuis 2021) :")
    st.line_chart(piv, height=260)

    # --- Récap MENSUEL par niveau (FORT et Moyen) pour suivre la bankroll ---
    def table_mensuelle(niveau, titre):
        sub = h[h["confiance"] == niveau].copy()
        if sub.empty:
            return
        st.markdown(f"**📅 Récap par mois — {titre}** (mise 1€/pari) :")
        sub["Mois"] = sub["date"].dt.to_period("M").astype(str)
        pm = sub.groupby("Mois").agg(paris=("paris", "sum"), succes=("succes", "sum"),
                                     profit=("profit", "sum")).reset_index()
        pm["Bankroll (€)"] = pm["profit"].cumsum().round(0).astype(int)
        pm[label_succes] = (pm["succes"] / pm["paris"] * 100).round(0).astype(int).astype(str) + "%"
        pm["ROI"] = (pm["profit"] / pm["paris"] * 100).round(1).astype(str) + "%"
        pm["Bénéfice (€)"] = pm["profit"].round(0).astype(int)
        pm = pm.rename(columns={"paris": "Paris"})
        vue = pm[["Mois", "Paris", label_succes, "Bénéfice (€)", "Bankroll (€)", "ROI"]]
        st.dataframe(vue, use_container_width=True, hide_index=True, height=min(500, 60 + 35 * len(vue)))

    table_mensuelle("FORT", "🟢 FORT")
    table_mensuelle("Moyen", "🟡 Moyen")

if not os.path.exists("historique_perf.csv"):
    st.info("Historique pas encore genere. Lance `python historique.py` une fois pour le creer.")
else:
    hist = pd.read_csv("historique_perf.csv")
    hist["date"] = pd.to_datetime(hist["date"])
    tab_p, tab_g, tab_q = st.tabs(["⭐ Placé", "🏆 Gagnant", "🎰 Quinté+"])
    with tab_p:
        afficher_perf(hist, "PLACE", "Taux de placé", "proba ≥ 60%", "proba < 60%")
    with tab_g:
        st.caption("Le Gagnant est plus variable : des mois entiers peuvent etre negatifs.")
        afficher_perf(hist, "GAGNANT", "Taux de victoire", "proba ≥ 40%", "proba < 40%")
    with tab_q:
        if os.path.exists("quinte_resume.csv") and os.path.exists("historique_quinte.csv"):
            r = pd.read_csv("quinte_resume.csv").iloc[0]
            hq = pd.read_csv("historique_quinte.csv")
            mise = int(r["mise"])
            st.markdown(f"**Ticket = les 5 meilleurs du modèle, 1 €/course, sur {int(r['quinte'])} "
                        "Quinté (2021-2026) :**")

            st.markdown("**🎯 Jeu Ordre** (les 5 dans l'ordre exact)")
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Mise totale", f"{mise:,} €".replace(",", " "))
            o2.metric("Gains", f"{r['gain_ordre']:,.0f} €".replace(",", " "))
            o3.metric("Profit", f"{r['gain_ordre']-mise:+,.0f} €".replace(",", " "))
            o4.metric("Touché", f"{int(r['hits_ordre'])} fois")

            st.markdown("**🔀 Jeu Désordre** (les 5, ordre indifférent)")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Mise totale", f"{mise:,} €".replace(",", " "))
            d2.metric("Gains", f"{r['gain_des']:,.0f} €".replace(",", " "))
            d3.metric("Profit", f"{r['gain_des']-mise:+,.0f} €".replace(",", " "))
            d4.metric("Touché", f"{int(r['hits_des'])} fois")

            hq = hq.sort_values("mois")
            courbe = pd.DataFrame({
                "mois": hq["mois"],
                "Ordre (€)": (hq["gain_ordre"] - hq["mise"]).cumsum(),
                "Désordre (€)": (hq["gain_des"] - hq["mise"]).cumsum(),
            }).set_index("mois")
            st.caption("Profit cumulé (mise 1€/course depuis 2021) :")
            st.line_chart(courbe, height=260)

            # --- Récap MENSUEL Quinté (ordre + désordre + bankroll) ---
            st.markdown("**📅 Récap par mois** (mise 1€/course) :")
            q = hq.copy()
            q["Bénéf. Ordre (€)"] = (q["gain_ordre"] - q["mise"]).round(0).astype(int)
            q["Bénéf. Désordre (€)"] = (q["gain_des"] - q["mise"]).round(0).astype(int)
            q["Bankroll Ordre (€)"] = (q["gain_ordre"] - q["mise"]).cumsum().round(0).astype(int)
            q["Bankroll Désordre (€)"] = (q["gain_des"] - q["mise"]).cumsum().round(0).astype(int)
            q = q.rename(columns={"mois": "Mois", "courses": "Quinté"})
            vueq = q[["Mois", "Quinté", "Bénéf. Ordre (€)", "Bénéf. Désordre (€)",
                      "Bankroll Ordre (€)", "Bankroll Désordre (€)"]]
            st.dataframe(vueq, use_container_width=True, hide_index=True, height=min(500, 60 + 35 * len(vueq)))

            st.error(
                f"⚠️ Ne te fie PAS a ces montants positifs. Le jeu **Ordre n'est tombé que "
                f"{int(r['hits_ordre'])} fois en 5 ans** : tout le profit vient de 1-2 coups de chance "
                "— sans eux, c'est une perte totale. Le **Désordre** touche plus souvent mais reste "
                "porte par de rares gros rapports. En realite, ta mise dilue le rapport (paris mutuels) "
                "et le PMU garde ~35%. Le Quinté est une **loterie a variance extreme** : sur la duree "
                "tu perds. A jouer pour le frisson, avec de tres petites sommes — jamais comme un revenu.")
        else:
            st.info("Historique Quinté pas encore genere (lance `python historique.py`).")

st.divider()
st.caption("⚠️ Rappel : jeu d'argent = risque. Ce modele a un petit avantage backteste "
           "mais ne garantit aucun gain. Joue de facon responsable, avec de l'argent que tu peux perdre.")
