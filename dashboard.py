# dashboard.py — Interface web des pronostics du jour.
#
# Lancement :  streamlit run dashboard.py
# (ou double-clic sur "Lancer le dashboard.bat")

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from pronos_jour import pronostics
from export_pdf import selection_pdf, detail_mois_pdf, mix_pdf
import auth

st.set_page_config(page_title="PMU Prono", page_icon="🐎", layout="wide")


def verifier_acces():
    """Page d'accueil + connexion (tant que l'utilisateur n'est pas connecté)."""
    if auth.utilisateur_actuel():
        return

    import streamlit.components.v1 as components

    # ============ HERO (rendu HTML fidele via iframe) ============
    hero = """
    <style>
      body{margin:0; background:transparent;
           font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}
      .hero{background:linear-gradient(135deg,#7c3aed 0%,#2563eb 52%,#059669 100%);
            border-radius:20px; padding:36px 22px; text-align:center; color:#fff;
            box-shadow:0 14px 40px rgba(37,99,235,.35);}
      .horse{font-size:56px; line-height:1;}
      .title{font-size:44px; font-weight:800; letter-spacing:.5px; margin-top:2px;}
      .sub{font-size:18px; font-weight:500; opacity:.96; margin-top:8px;}
      .pills{display:flex; gap:9px; flex-wrap:wrap; justify-content:center; margin-top:16px;}
      .pill{background:rgba(255,255,255,.20); padding:6px 14px; border-radius:22px;
            font-size:13.5px; font-weight:600; backdrop-filter:blur(4px);}
    </style>
    <div class="hero">
      <div class="horse">🐎</div>
      <div class="title">PMU Prono</div>
      <div class="sub">Pronostics hippiques par Intelligence Artificielle</div>
      <div class="pills">
        <span class="pill">📅 13 ans de données</span>
        <span class="pill">🔬 backtest honnête</span>
        <span class="pill">🐎 2,7 M de partants</span>
        <span class="pill">🇫🇷 courses françaises</span>
      </div>
    </div>"""
    components.html(hero, height=260)

    st.subheader("🎯 Le principe")
    st.write(
        "Un modèle d'IA entraîné sur **13 ans de courses françaises** (2013-2026, "
        "**2,7 millions de partants**) analyse chaque jour la *musique*, les cotes, la forme "
        "et les gains de chaque cheval. Toutes les stratégies sont **validées honnêtement** : "
        "le modèle apprend sur 2013-2020 et n'est jugé que sur **2021-2026 — des courses qu'il "
        "n'a jamais vues** (résultats réalistes, pas gonflés).")

    # ============ CARTES stratégies (gradient, rendu fidele, responsive) ============
    st.subheader("📊 Les stratégies en chiffres")
    cartes = [
        ("linear-gradient(135deg,#7c3aed,#a855f7)", "🎲", "MIX", "Placé Fort + Gagnant Moyen",
         "+13 045 €", [("47,7%", "réussite"), ("+13,1%", "ROI"), ("99 615", "paris")]),
        ("linear-gradient(135deg,#059669,#10b981)", "⭐", "Placé Fort", "Le + sûr — top 3",
         "+5 703 €", [("71,5%", "placés"), ("+12,5%", "ROI"), ("45 502", "paris")]),
        ("linear-gradient(135deg,#ea580c,#f97316)", "🏆", "Gagnant Moyen", "L'outsider qui gagne",
         "+7 341 €", [("27,6%", "victoires"), ("+13,6%", "ROI"), ("54 113", "paris")]),
        ("linear-gradient(135deg,#dc2626,#f43f5e)", "🎰", "Quinté+", "Les 5 premiers — base 7",
         "+70 076 €", [("+59 730 €", "ordre ×2"), ("+10 346 €", "désordre"), ("2 020", "paris")]),
    ]
    cards = ""
    for grad, icon, nom, sub, big, stats in cartes:
        rows = "".join(
            f'<div class="row"><span class="v">{v}</span><span class="l">{l}</span></div>'
            for v, l in stats)
        cards += f"""
        <div class="card" style="background:{grad};">
          <div class="ic">{icon}</div>
          <div class="nom">{nom}</div>
          <div class="sub">{sub}</div>
          <div class="big">{big}</div>
          {rows}
        </div>"""
    cards_html = f"""
    <style>
      *{{box-sizing:border-box;}}
      body{{margin:0; background:transparent;
           font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
      .rail{{display:flex; gap:14px; overflow-x:auto; padding:2px 2px 12px;
            scroll-snap-type:x mandatory; -webkit-overflow-scrolling:touch;}}
      .rail::-webkit-scrollbar{{height:7px;}}
      .rail::-webkit-scrollbar-thumb{{background:rgba(130,130,130,.45); border-radius:4px;}}
      .card{{flex:1 0 165px; scroll-snap-align:start; border-radius:18px; padding:18px 16px;
            color:#fff; box-shadow:0 10px 26px rgba(0,0,0,.18);}}
      .ic{{font-size:30px; line-height:1;}}
      .nom{{font-size:17px; font-weight:800; margin-top:6px;}}
      .sub{{font-size:12px; opacity:.9; margin-top:2px; min-height:28px;}}
      .big{{font-size:27px; font-weight:800; margin:10px 0 6px;}}
      .row{{display:flex; justify-content:space-between; align-items:baseline;
           border-top:1px solid rgba(255,255,255,.28); padding:6px 0;}}
      .v{{font-size:14px; font-weight:800;}}
      .l{{font-size:12px; opacity:.9;}}
    </style>
    <div class="rail">{cards}</div>"""
    components.html(cards_html, height=285, scrolling=False)
    st.caption("💰 Bénéfice = mise 1€/pari, sur 2021-2026 (sur mobile, glisse les cartes ↔). "
               "**🎲 MIX** = le plus rentable · **⭐ Placé Fort** = le plus régulier · "
               "**🎰 Quinté+** = gros gains mais très rares (2 jackpots — voir le détail).")

    with st.expander("📋 Voir tous les chiffres (comparatif détaillé des 6 tranches)"):
        comp = pd.DataFrame([
            ["🎲 MIX",           "99 615", "47,7% (mixte)",   "+13,1%", "+13 045 €", "16 pertes d'affilée · creux −105 €"],
            ["⭐ Placé Fort",    "45 502", "71,5% placés",    "+12,5%", "+5 703 €",  "Faible — le plus régulier"],
            ["🟡 Placé Moyen",   "25 088", "51,9% placés",    "+12,1%", "+3 027 €",  "Moyen"],
            ["🏆 Gagnant Fort",  "16 477", "48,5% victoires", "+10,7%", "+1 770 €",  "Élevé"],
            ["🟠 Gagnant Moyen", "54 113", "27,6% victoires", "+13,6%", "+7 341 €",  "Très élevé (gros coups rares)"],
            ["🎰 Quinté+",       "2 020",  "78 désordre · 2 ordre", "variance ++", "+70 076 € (dont +59 730 € ordre ×2)", "Extrême — porté par 2 jackpots"],
        ], columns=["Stratégie", "Paris", "Réussite", "ROI", "Bénéfice", "Risque"])
        st.dataframe(comp, use_container_width=True, hide_index=True)
        st.caption("Mesuré sur 2021-2026 (courses FR jamais vues à l'entraînement). "
                   "Les ROI restent des **plafonds optimistes** — en réel, ta mise réduit le rapport. "
                   "⚠️ Le **Quinté** est une loterie : ses +61 750 € viennent de **2 jackpots** "
                   "(mai + déc 2021) ; sans eux, il est en perte. À ne pas comparer aux autres.")

    st.subheader("🛠️ Ce que l'application te donne")
    st.markdown(
        "- **La sélection du jour** : les chevaux à jouer, triés par heure de course\n"
        "- **Les résultats en direct** au fil des arrivées (✅/❌) + ton bénéfice du jour\n"
        "- **L'historique complet** : courbe de gains, récap mensuel, suivi de bankroll\n"
        "- **Export PDF** de tes paris du jour et du détail de chaque mois")

    st.divider()
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("### 🔒 Accès à l'application")
        st.caption("Connecte-toi ou crée ton compte pour accéder à tes stratégies.")
        auth.formulaire_auth()

    st.divider()
    st.caption("⚠️ Jeu d'argent = risque. Les rendements affichés sont des **backtests** "
               "(plafonds optimistes), pas des garanties. Joue de façon responsable, avec de "
               "l'argent que tu peux te permettre de perdre. Réservé aux 18 ans et plus.")
    st.stop()


auth.restaurer_session()   # reconnecte via cookie si session précédente
auth.flush_cookie()        # écrit le cookie de session en attente (après connexion)

if st.query_params.get("dbg") == "1":
    import traceback
    try:
        _ctx = dict(st.context.cookies)
    except Exception as _e:
        _ctx = f"ERREUR st.context.cookies: {_e!r}"
    st.write("cookies vus par le serveur:", _ctx)
    _rt = None
    try:
        _rt = st.context.cookies.get("pmu_rt")
    except Exception as _e:
        st.write("get pmu_rt err:", repr(_e))
    st.write("pmu_rt lu:", _rt)
    if _rt:
        try:
            _r = auth._anon_client().auth.refresh_session(_rt)
            st.write("refresh OK, user =", _r.user.email if _r and _r.user else None)
        except Exception as _e:
            st.write("refresh FAIL:", repr(_e))
            st.code(traceback.format_exc())
    st.stop()

verifier_acces()

# --- Barre latérale : utilisateur connecté + ses stratégies + déconnexion ---
with st.sidebar:
    _u = auth.utilisateur_actuel()
    if _u:
        st.markdown(f"👤 **{_u['email']}**")
        _libelles = {"place": "⭐ Placé", "gagnant": "🏆 Gagnant",
                     "mix": "🎲 MIX", "quinte": "🎰 Quinté+"}
        _mes = [_libelles.get(s, s) for s in auth.droits_actuels()]
        st.caption("Tes stratégies : " + (", ".join(_mes) if _mes else "aucune"))
        if st.button("Se déconnecter", use_container_width=True):
            auth.deconnexion()

st.title("🐎 PMU Prono — Pronostics du jour")
st.caption("Modele entraine sur 13 ans de courses FRANCAISES. Strategie SECURITE : le Placé. "
           "(Courses etrangeres exclues.)")

# ═══════════════════════════════════════════════════════════════
#  PANNEAU SUPERADMIN — gérer les utilisateurs et leurs droits
# ═══════════════════════════════════════════════════════════════
_moi = auth.utilisateur_actuel()
if _moi and auth.est_admin(_moi["email"]):
    with st.expander("🛠️ Administration — utilisateurs et droits", expanded=False):
        try:
            _users = auth.lister_utilisateurs()
            st.caption(f"{len(_users)} utilisateur(s). Coche/décoche les stratégies puis enregistre. "
                       "Les admins ont automatiquement tout.")
            _df_admin = pd.DataFrame([{
                "Email": u["email"],
                "⭐ Placé": "place" in u["strategies"],
                "🏆 Gagnant": "gagnant" in u["strategies"],
                "🎲 MIX": "mix" in u["strategies"],
                "🎰 Quinté+": "quinte" in u["strategies"],
                "Admin": u["admin"],
                "_id": u["user_id"],
            } for u in _users])
            _edite = st.data_editor(
                _df_admin, hide_index=True, use_container_width=True,
                disabled=["Email", "Admin"],
                column_config={"_id": None},
                key="admin_editor")
            if st.button("💾 Enregistrer les droits"):
                _n = 0
                for _, _row in _edite.iterrows():
                    if _row["Admin"]:
                        continue
                    _strats = []
                    if _row["⭐ Placé"]: _strats.append("place")
                    if _row["🏆 Gagnant"]: _strats.append("gagnant")
                    if _row["🎲 MIX"]: _strats.append("mix")
                    if _row["🎰 Quinté+"]: _strats.append("quinte")
                    auth.definir_droits(_row["_id"], _strats)
                    _n += 1
                st.success(f"✅ Droits mis à jour pour {_n} utilisateur(s). "
                           "Ils verront le changement à leur prochaine connexion.")
                st.rerun()
        except Exception as _e:
            st.error(f"Erreur d'administration : {_e}")

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
#  SELECTION MIX du jour (EN PREMIER — Placé Fort + Gagnant Moyen)
# ═══════════════════════════════════════════════════════════════
if auth.a_droit("mix"):
    st.header("🎲 Sélection MIX du jour")
    st.caption("Placé FORT (≥60%) joués au PLACÉ **+** Gagnant Moyen (<40%) joués au GAGNANT. "
               "~2 paris/course. Plus gros bénéfice backtesté (+13 045€ sur 2021-26).")

    pf = df[(df["rang_place"] == 1) & (df["proba_place"] >= 0.6)].copy()
    pf["Pari"] = "PLACÉ"; pf["proba"] = pf["proba_place"]
    gm = df[(df["rang_gagnant"] == 1) & (df["proba_gagnant"] < 0.4)].copy()
    gm["Pari"] = "GAGNANT"; gm["proba"] = gm["proba_gagnant"]
    mix = pd.concat([pf, gm], ignore_index=True)

    def _mix_ok(row):
        if pd.isna(row["position"]):
            return False
        return (row["Pari"] == "PLACÉ" and row["position"] <= 3) or \
               (row["Pari"] == "GAGNANT" and row["position"] == 1)

    def _mix_res(row):
        if not row["course_finie"]:
            return "⏳ à venir"
        pos = row["position"]
        if pd.isna(pos):
            return "❌"
        return f"{int(pos)}e {'✅' if _mix_ok(row) else '❌'}"

    def _mix_gain(row):
        if not _mix_ok(row):
            return 0.0
        r = row["rapport_place"] if row["Pari"] == "PLACÉ" else row["rapport_gagnant"]
        return r if pd.notna(r) else 0.0

    if len(mix):
        mix["Heure GMT"] = mix["heure"].apply(heure_gmt)
        mix["Résultat"] = mix.apply(_mix_res, axis=1)
        mix = mix.sort_values("heure", na_position="last")

        couru = mix[mix["course_finie"]].copy()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Paris MIX du jour", len(mix))
        c2.metric("Déjà courus", len(couru))
        if len(couru):
            couru["ok"] = couru.apply(_mix_ok, axis=1)
            couru["g"] = couru.apply(_mix_gain, axis=1)
            profit = couru["g"].sum() - len(couru)
            c3.metric("Réussite", f"{couru['ok'].mean():.0%}", f"{int(couru['ok'].sum())}/{len(couru)}")
            c4.metric("Bénéfice (1€/pari)", f"{profit:+.1f} €", f"ROI {profit/len(couru):+.0%}")
        else:
            c3.metric("Réussite", "—")
            c4.metric("Bénéfice (1€/pari)", "—")

        vue_mix = mix[["course", "Heure GMT", "hippodrome", "num_pmu", "nom", "Pari",
                       "proba", "cote_reference", "Résultat"]].copy()
        vue_mix.columns = ["Course", "Heure GMT", "Hippodrome", "N°", "Cheval", "Pari",
                           "Proba", "Cote matin", "Résultat"]
        vue_mix["Proba"] = (vue_mix["Proba"] * 100).round(0).astype(int).astype(str) + "%"
        st.caption("Trié par heure. Colonne **Pari** = jouer au PLACÉ ou au GAGNANT selon la ligne.")
        st.dataframe(vue_mix, use_container_width=True, hide_index=True,
                     height=min(700, 60 + 35 * len(vue_mix)))
        st.download_button(
            "📄 Télécharger MES paris MIX (PDF)",
            data=mix_pdf(jour.isoformat(), mix.rename(columns={"num_pmu": "num", "Pari": "pari"})),
            file_name=f"selection_mix_{jour.isoformat()}.pdf",
            mime="application/pdf", key="dl_mix")
    else:
        st.info("Aucun pari MIX pour cette date.")

# ═══════════════════════════════════════════════════════════════
#  SELECTION DU JOUR — les pronos Placé les plus surs
# ═══════════════════════════════════════════════════════════════
if auth.a_droit("place"):
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
if auth.a_droit("gagnant"):
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
if auth.a_droit("quinte"):
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

NIVEAUX = {"FORT": "🟢 FORT", "Moyen": "🟡 Moyen",
           "MIX": "🎲 MIX (Placé Fort + Gagnant Moyen)"}
ORDRE_NIV = ["SUPER", "FORT", "Moyen", "MIX"]

def afficher_perf(hist, strat, label_succes):
    h = hist[hist["strategie"] == strat]
    if h.empty:
        st.caption("Pas de donnees.")
        return
    niveaux = [n for n in ORDRE_NIV if n in set(h["confiance"])]

    for niv in niveaux:
        hh = h[h["confiance"] == niv]
        st.markdown(f"**{NIVEAUX[niv]}**")
        p = int(hh["paris"].sum())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Paris (total)", f"{p:,}".replace(",", " "))
        m2.metric(label_succes, f"{hh['succes'].sum()/p:.1%}")
        m3.metric("ROI global", f"{hh['profit'].sum()/p:+.1%}")
        m4.metric("Bénéfice (1€/pari)", f"{hh['profit'].sum():+,.0f} €".replace(",", " "))
        st.write("")

    piv = (h.pivot_table(index="date", columns="confiance", values="profit", aggfunc="sum")
             .fillna(0).sort_index().cumsum())
    piv = piv[[n for n in ORDRE_NIV if n in piv.columns]]
    piv.columns = [f"{c} (€)" for c in piv.columns]
    st.caption("Gains cumulés (mise 1€/pari depuis 2021) :")
    st.line_chart(piv, height=260)

    # --- Récap MENSUEL par niveau pour suivre la bankroll ---
    for niv in niveaux:
        sub = h[h["confiance"] == niv].copy()
        st.markdown(f"**📅 Récap par mois — {NIVEAUX[niv]}** (mise 1€/pari) :")
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

if not os.path.exists("historique_perf.csv"):
    st.info("Historique pas encore genere. Lance `python historique.py` une fois pour le creer.")
else:
    hist = pd.read_csv("historique_perf.csv")
    hist["date"] = pd.to_datetime(hist["date"])
    tab_p, tab_g, tab_m, tab_q = st.tabs(["⭐ Placé", "🏆 Gagnant", "🎲 Mix", "🎰 Quinté+"])
    with tab_p:
        afficher_perf(hist, "PLACE", "Taux de placé")
        # --- Telechargement du detail d'un mois (Placé FORT, par heure) ---
        if os.path.exists("historique_detail.csv"):
            det = pd.read_csv("historique_detail.csv")
            st.markdown("**📄 Télécharger le détail d'un mois** (Placé FORT, trié par heure) :")
            mois_dispo = sorted(det["mois"].astype(str).unique(), reverse=True)
            m_sel = st.selectbox("Mois", mois_dispo, key="mois_detail_place")
            dm = det[det["mois"].astype(str) == m_sel]
            st.download_button(
                f"📄 Détail {m_sel} en PDF ({len(dm)} paris)",
                data=detail_mois_pdf(m_sel, dm),
                file_name=f"detail_place_fort_{m_sel}.pdf",
                mime="application/pdf",
                key="dl_detail_place")
    with tab_g:
        st.caption("Le Gagnant est plus variable : des mois entiers peuvent etre negatifs.")
        afficher_perf(hist, "GAGNANT", "Taux de victoire")
    with tab_m:
        st.caption("🎲 MIX = **Placé FORT** (stable) + **Gagnant Moyen** (variable) joués ensemble. "
                   "~2 paris par course. Le bénéfice total est le plus élevé de toutes les stratégies.")
        afficher_perf(hist, "MIX", "Taux de réussite")
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
