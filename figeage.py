# figeage.py — Fige la sélection du matin (chevaux + cotes + probas) par utilisateur.
#
# Problème résolu : l'app recalcule les pronos EN DIRECT à chaque ouverture. Sur une
# course serrée, une cote qui bouge (ou un cheval retiré) peut changer le pick APRÈS
# que tu aies parié. Le figeage enregistre la photo du matin ; ensuite l'app affiche
# toujours CE QUE TU AS JOUÉ, et n'actualise QUE les résultats (arrivées, rapports).
#
# Stockage : table Supabase `snapshots` (une ligne par user_id + date, données JSONB).
# Écriture/lecture via la clé service_role (comme les droits) car la session Supabase
# n'est pas persistée entre les rechargements Streamlit.

import json
from datetime import datetime, timezone

import pandas as pd

# Colonnes FIGÉES (prédictions + identité : ne doivent PAS être recalculées après coup)
COLS_FIGEES = [
    "course", "hippodrome", "heure", "nb_partants", "quinte", "distance",
    "num_pmu", "nom", "driver", "musique",
    "proba_place", "proba_gagnant", "cote_reference", "rang_place", "rang_gagnant",
]

# Colonnes de RÉSULTAT (toujours prises en DIRECT : elles arrivent après le figeage)
COLS_NUM = ["num_pmu", "nb_partants", "heure", "proba_place", "proba_gagnant",
            "cote_reference", "rang_place", "rang_gagnant"]


# ══════════════════ Persistance (Supabase, clé service_role) ══════════════════

def enregistrer(user_id: str, jour: str, df: pd.DataFrame) -> tuple[bool, str]:
    """Sauvegarde la sélection du matin (df live). Retourne (ok, message d'erreur)."""
    import auth
    cols = [c for c in COLS_FIGEES if c in df.columns]
    data = json.loads(df[cols].to_json(orient="records"))
    try:
        auth._admin_client().table("snapshots").upsert({
            "user_id": user_id,
            "date": jour,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)


def charger(user_id: str, jour: str):
    """Retourne (df_figé, frozen_at) ou (None, None) s'il n'y a pas de figeage."""
    import auth
    try:
        r = (auth._admin_client().table("snapshots").select("frozen_at,data")
             .eq("user_id", user_id).eq("date", jour).limit(1).execute())
    except Exception:
        return None, None
    if not r.data:
        return None, None
    row = r.data[0]
    df = pd.DataFrame(row.get("data") or [])
    if df.empty:
        return None, None
    for c in COLS_NUM:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "num_pmu" in df.columns:
        df["num_pmu"] = df["num_pmu"].astype("Int64")
    return df, row.get("frozen_at")


def supprimer(user_id: str, jour: str):
    """Supprime le figeage de cette date (pour re-figer ou revenir au live)."""
    import auth
    try:
        auth._admin_client().table("snapshots").delete() \
            .eq("user_id", user_id).eq("date", jour).execute()
    except Exception:
        pass


# ══════════════════ Fusion figé + résultats live ══════════════════

def fusionner(df_frozen: pd.DataFrame, df_live: pd.DataFrame) -> pd.DataFrame:
    """Prédictions FIGÉES + résultats EN DIRECT (arrivée, rapports), joints par course+cheval."""
    frozen = df_frozen.copy()
    frozen["num_pmu"] = pd.to_numeric(frozen["num_pmu"], errors="coerce").astype("Int64")

    live = df_live.copy()
    live["num_pmu"] = pd.to_numeric(live["num_pmu"], errors="coerce").astype("Int64")

    # course_finie : par course, depuis le live
    fin = live.groupby("course")["course_finie"].any().to_dict()

    res = live[["course", "num_pmu", "position", "rapport_place", "rapport_gagnant"]].copy()
    cote = live[["course", "num_pmu", "cote_reference"]].rename(
        columns={"cote_reference": "cote_live"})

    m = frozen.merge(res, on=["course", "num_pmu"], how="left") \
              .merge(cote, on=["course", "num_pmu"], how="left")
    m["course_finie"] = m["course"].map(fin).fillna(False)
    return m


def changements(df_frozen: pd.DataFrame, df_live: pd.DataFrame) -> list:
    """Courses où le modèle choisirait AUTREMENT maintenant (cote bougée / cheval retiré).

    Retourne [(course, hippodrome, [notes...]), ...].
    """
    ch = []
    frozen = df_frozen.copy()
    frozen["num_pmu"] = pd.to_numeric(frozen["num_pmu"], errors="coerce").astype("Int64")
    live = df_live.copy()
    live["num_pmu"] = pd.to_numeric(live["num_pmu"], errors="coerce").astype("Int64")

    for course, g in frozen.groupby("course"):
        gl = live[live["course"] == course]
        if gl.empty or g.empty:
            continue
        # Picks figés (rang 1) vs picks recalculés live
        fp_place = int(g.sort_values("rang_place").iloc[0]["num_pmu"])
        fp_gag = int(g.sort_values("rang_gagnant").iloc[0]["num_pmu"])
        lp_place = int(gl.sort_values("proba_place", ascending=False).iloc[0]["num_pmu"])
        lp_gag = int(gl.sort_values("proba_gagnant", ascending=False).iloc[0]["num_pmu"])

        retires = set(int(x) for x in g["num_pmu"].dropna()) - \
                  set(int(x) for x in gl["num_pmu"].dropna())

        notes = []
        if fp_gag != lp_gag:
            notes.append(f"Gagnant : #{fp_gag} → #{lp_gag}")
        if fp_place != lp_place:
            notes.append(f"Placé : #{fp_place} → #{lp_place}")
        if retires:
            notes.append("retiré depuis : " + ", ".join(f"#{x}" for x in sorted(retires)))
        if notes:
            hip = gl["hippodrome"].iloc[0] if "hippodrome" in gl.columns else ""
            ch.append((course, hip, notes))
    return ch
