# features.py — Transforme les donnees brutes (courses + participants) en
# "features" (signaux numeriques) exploitables par le modele de prono.
#
# Aucune fuite de donnees : on n'utilise QUE ce qui est connu AVANT la course
# (musique, cotes, gains, corde...). La cible (arrivee) sert seulement a
# l'entrainement, jamais comme feature.

import re
from pathlib import Path
import numpy as np
import pandas as pd

from db import connexion, DB_PATH

CACHE = Path(__file__).parent / "features_cache.pkl"


# ─────────────────────────────────────────────────────────────
#  1. DECODAGE DE LA MUSIQUE
# ─────────────────────────────────────────────────────────────
# La "musique" resume les dernieres performances, ex : "1p2p4p6p" ou "2A4ADA".
# Chaque bloc = {resultat}{discipline}. Resultat : 1-9 = place, 0 = hors top 9,
# D/T/A/R/Q = disqualifie / tombe / arrete / retire (une faute).
# Discipline : a=attele, m=monte, p=plat, h=haies, s=steeple, c=cross, o=obstacle.

_BLOC = re.compile(r"([0-9DTARQ])([a-zA-Z])")
_FAUTE = 11   # score attribue a une faute (disqualif, chute...) : pire qu'une place
_HORS = 10    # score attribue a "0" (fini hors des 9 premiers)


def _pos(car: str) -> int:
    """Convertit un caractere de resultat en score de position (plus bas = mieux)."""
    if car.isdigit():
        n = int(car)
        return _HORS if n == 0 else n
    return _FAUTE   # D, T, A, R, Q = faute


def decoder_musique(musique: str) -> dict:
    """Extrait des indicateurs de forme a partir de la musique."""
    if not musique or not isinstance(musique, str):
        return dict(muzik_nb=0, muzik_pos_moy=np.nan, muzik_pos_moy3=np.nan,
                    muzik_last=np.nan, muzik_win=np.nan, muzik_place=np.nan,
                    muzik_fautes=np.nan)

    blocs = _BLOC.findall(musique)
    positions = [_pos(res) for res, _disc in blocs]
    if not positions:
        return dict(muzik_nb=0, muzik_pos_moy=np.nan, muzik_pos_moy3=np.nan,
                    muzik_last=np.nan, muzik_win=np.nan, muzik_place=np.nan,
                    muzik_fautes=np.nan)

    arr = np.array(positions, dtype=float)
    nb = len(arr)
    return dict(
        muzik_nb=nb,                                   # nb de courses connues
        muzik_pos_moy=arr.mean(),                      # position moyenne
        muzik_pos_moy3=arr[:3].mean(),                 # forme recente (3 dernieres)
        muzik_last=arr[0],                             # derniere position
        muzik_win=float((arr == 1).mean()),            # % de victoires
        muzik_place=float((arr <= 3).mean()),          # % dans les 3
        muzik_fautes=float((arr == _FAUTE).mean()),    # % de fautes (cle en trot)
    )


# ─────────────────────────────────────────────────────────────
#  2. CONSTRUCTION DU TABLEAU DE FEATURES
# ─────────────────────────────────────────────────────────────

def charger_donnees() -> pd.DataFrame:
    """Charge la jointure courses + participants depuis la base."""
    conn = connexion()
    df = pd.read_sql_query(
        """
        SELECT
            p.course_id, p.num_pmu, p.nom, p.age, p.sexe, p.musique,
            p.nombre_courses, p.nombre_victoires, p.nombre_places,
            p.gains_carriere, p.gains_annee, p.place_corde, p.handicap_poids,
            p.cote_reference, p.cote_finale, p.position_arrivee, p.statut,
            c.date, c.specialite, c.discipline, c.distance, c.corde,
            c.nb_partants, c.montant_prix, c.hippodrome, c.pays
        FROM participants p
        JOIN courses c ON c.id = p.course_id
        """,
        conn,
    )
    conn.close()
    return df


def construire_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute toutes les colonnes de features + les cibles."""

    # -- Filtrer : uniquement les courses FRANCAISES, partants reels, arrivee connue
    df = df[df["pays"] == "FRA"].copy()
    df = df[df["statut"] != "NON_PARTANT"].copy()
    df = df[df["position_arrivee"].notna()].copy()

    # -- Features "musique" (forme recente) — version optimisee
    #    On decode chaque musique UNIQUE une seule fois (cache), puis on
    #    reconstruit le tableau d'un coup. Evite le .apply(pd.Series) qui,
    #    ligne par ligne sur des millions de partants, prenait des minutes.
    musiques = df["musique"].fillna("").to_numpy()
    cache_muz = {m: decoder_musique(m) for m in set(musiques)}
    muzik = pd.DataFrame([cache_muz[m] for m in musiques], index=df.index)
    df = pd.concat([df, muzik], axis=1)

    # -- Cotes : proba implicite du marche (normalisee par course)
    #    1/cote ~ proba brute ; on normalise pour que la somme = 1 par course.
    df["cote_finale"] = pd.to_numeric(df["cote_finale"], errors="coerce")
    df["cote_reference"] = pd.to_numeric(df["cote_reference"], errors="coerce")
    df["proba_marche_brute"] = 1.0 / df["cote_finale"]
    somme = df.groupby("course_id")["proba_marche_brute"].transform("sum")
    df["proba_marche"] = df["proba_marche_brute"] / somme
    # Rang du cheval dans la course selon la cote (1 = favori)
    df["rang_cote"] = df.groupby("course_id")["cote_finale"].rank(method="min")
    # Evolution de cote (matinale -> finale) : negatif = le marche l'a soutenu
    df["evo_cote"] = (df["cote_finale"] - df["cote_reference"]) / df["cote_reference"]

    # -- Statistiques carriere
    df["ratio_victoires"] = df["nombre_victoires"] / df["nombre_courses"].replace(0, np.nan)
    df["ratio_places"] = df["nombre_places"] / df["nombre_courses"].replace(0, np.nan)
    df["gains_log"] = np.log1p(df["gains_carriere"].clip(lower=0))
    df["gains_annee_log"] = np.log1p(df["gains_annee"].clip(lower=0))
    # Gains rapportes au nombre de courses (niveau reel)
    df["gains_par_course"] = df["gains_carriere"] / df["nombre_courses"].replace(0, np.nan)

    # -- Encodage des categories utiles
    df["is_attele"] = (df["discipline"] == "ATTELE").astype(int)
    df["is_monte"] = (df["discipline"] == "MONTE").astype(int)
    df["is_plat"] = (df["specialite"] == "PLAT").astype(int)
    df["is_obstacle"] = (df["specialite"] == "OBSTACLE").astype(int)
    df["sexe_code"] = df["sexe"].map({"MALES": 0, "FEMELLES": 1, "HONGRES": 2}).fillna(-1)

    # -- CIBLES (ce qu'on cherche a predire)
    df["cible_gagnant"] = (df["position_arrivee"] == 1).astype(int)
    df["cible_place"] = (df["position_arrivee"] <= 3).astype(int)

    return df


# Colonnes utilisees comme entrees du modele
FEATURES = [
    "age", "sexe_code", "distance", "nb_partants", "place_corde", "handicap_poids",
    "muzik_nb", "muzik_pos_moy", "muzik_pos_moy3", "muzik_last",
    "muzik_win", "muzik_place", "muzik_fautes",
    "cote_finale", "cote_reference", "proba_marche", "rang_cote", "evo_cote",
    "nombre_courses", "ratio_victoires", "ratio_places",
    "gains_log", "gains_annee_log", "gains_par_course",
    "is_attele", "is_monte", "is_plat", "is_obstacle",
]


# Features "propres" (sans fuite) : on exclut tout ce qui derive de la cote FINALE.
FUITE = {"cote_finale", "proba_marche", "rang_cote", "evo_cote"}
FEATURES_SAFE = [f for f in FEATURES if f not in FUITE]


def features_pour_prediction(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les features SAFE sur des donnees BRUTES du jour (sans resultat).
    Utilise par le dashboard : memes calculs qu'a l'entrainement, mais sans
    filtrage sur l'arrivee ni creation de cibles."""
    df = df.copy()
    # musique
    musiques = df["musique"].fillna("").to_numpy()
    cache = {m: decoder_musique(m) for m in set(musiques)}
    muzik = pd.DataFrame([cache[m] for m in musiques], index=df.index)
    df = pd.concat([df, muzik], axis=1)
    # cote du matin
    df["cote_reference"] = pd.to_numeric(df["cote_reference"], errors="coerce")
    # colonnes numeriques brutes : certaines courses (anciennes) les renvoient en texte
    for _col in ["age", "distance", "nb_partants", "place_corde", "handicap_poids"]:
        if _col in df.columns:
            df[_col] = pd.to_numeric(df[_col], errors="coerce")
    # carriere
    nc = pd.to_numeric(df["nombre_courses"], errors="coerce").replace(0, np.nan)
    df["ratio_victoires"] = pd.to_numeric(df["nombre_victoires"], errors="coerce") / nc
    df["ratio_places"] = pd.to_numeric(df["nombre_places"], errors="coerce") / nc
    df["gains_log"] = np.log1p(pd.to_numeric(df["gains_carriere"], errors="coerce").clip(lower=0))
    df["gains_annee_log"] = np.log1p(pd.to_numeric(df["gains_annee"], errors="coerce").clip(lower=0))
    df["gains_par_course"] = pd.to_numeric(df["gains_carriere"], errors="coerce") / nc
    # encodages
    df["is_attele"] = (df["discipline"] == "ATTELE").astype(int)
    df["is_monte"] = (df["discipline"] == "MONTE").astype(int)
    df["is_plat"] = (df["specialite"] == "PLAT").astype(int)
    df["is_obstacle"] = (df["specialite"] == "OBSTACLE").astype(int)
    df["sexe_code"] = df["sexe"].map({"MALES": 0, "FEMELLES": 1, "HONGRES": 2}).fillna(-1)
    return df


def preparer(limite_dates: tuple = None, cache: bool = True) -> pd.DataFrame:
    """Pipeline complet : charge, filtre, calcule les features. Pret pour le modele.

    Avec cache=True : si les features ont deja ete calculees ET que la base n'a
    pas change depuis, on recharge le cache disque (quelques secondes) au lieu
    de tout recalculer (plusieurs minutes).
    """
    if cache and CACHE.exists() and CACHE.stat().st_mtime >= DB_PATH.stat().st_mtime:
        df = pd.read_pickle(CACHE)
    else:
        df = construire_features(charger_donnees())
        if cache:
            df.to_pickle(CACHE)

    if limite_dates:
        d0, d1 = limite_dates
        df = df[(df["date"] >= d0) & (df["date"] <= d1)]
    return df


if __name__ == "__main__":
    print("Chargement + calcul des features (peut prendre 1-2 min sur toute la base)...")
    df = preparer()
    print(f"\nLignes (partants) : {len(df):,}".replace(",", " "))
    print(f"Courses distinctes : {df['course_id'].nunique():,}".replace(",", " "))
    print(f"\nTaux de gagnants  : {df['cible_gagnant'].mean():.1%}")
    print(f"Taux de places    : {df['cible_place'].mean():.1%}")
    print("\nApercu de quelques features (5 premiers chevaux) :")
    apercu = ["nom", "muzik_pos_moy3", "muzik_place", "proba_marche", "rang_cote",
              "ratio_places", "cible_place"]
    print(df[apercu].head().to_string(index=False))
