# pronos_jour.py — Recupere les courses d'un jour et calcule les pronostics.
#
# Pour une date donnee (aujourd'hui par defaut) :
#   1. telecharge le programme + les partants via l'API PMU (cote du MATIN dispo)
#   2. calcule les features propres
#   3. applique les modeles (place + gagnant)
#   4. retourne un tableau de pronos, trie par course
#
# Utilise par le dashboard. Contourne le blocage DNS automatiquement.

import asyncio
import logging
from datetime import date

import httpx
import numpy as np
import pandas as pd
import lightgbm as lgb

import dns_contournement
from features import features_pour_prediction, FEATURES_SAFE

BASE = "https://online.turfinfo.api.pmu.fr/rest/client/1/programme"
HEADERS = {"User-Agent": "Mozilla/5.0"}
_dns_installe = False


def _init_dns():
    global _dns_installe
    if not _dns_installe:
        dns_contournement.installer(logging.getLogger())
        _dns_installe = True


def _position(ordre, num):
    """Place d'un cheval (par son numero) dans l'ordre d'arrivee, ou None."""
    if not ordre:
        return None
    for i, groupe in enumerate(ordre, start=1):
        if num in groupe:
            return i
    return None


def _parse_rapports(data, type_pari):
    """Extrait {num_pmu: rapport} pour un type de pari (SIMPLE_PLACE ou SIMPLE_GAGNANT)."""
    out = {}
    if not isinstance(data, list):
        return out
    for bloc in data:
        if bloc.get("typePari") == type_pari:
            for rap in bloc.get("rapports", []):
                combi, div = rap.get("combinaison"), rap.get("dividendePourUnEuro")
                if combi and div is not None:
                    try:
                        out[int(combi)] = div / 100.0
                    except (ValueError, TypeError):
                        pass
    return out


async def _none():
    return None


async def _get(client, sem, url):
    for essai in range(3):
        try:
            async with sem:
                r = await client.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (204, 404):
                return None
        except Exception:
            await asyncio.sleep(2 * (essai + 1))
    return None


async def _recuperer(jour_iso: str) -> pd.DataFrame:
    """Telecharge tous les partants d'un jour et retourne un DataFrame brut."""
    _init_dns()
    jj = jour_iso[8:10] + jour_iso[5:7] + jour_iso[0:4]
    sem = asyncio.Semaphore(20)
    lignes = []
    async with httpx.AsyncClient(headers=HEADERS) as client:
        prog = await _get(client, sem, f"{BASE}/{jj}")
        if not prog:
            return pd.DataFrame()
        reunions = prog.get("programme", {}).get("reunions", []) or []

        taches = []
        rap_taches = []
        meta = []
        for reu in reunions:
            # France uniquement (le modele est entraine sur les courses FR)
            pays = reu.get("pays")
            code_pays = pays.get("code") if isinstance(pays, dict) else pays
            if code_pays != "FRA":
                continue
            hippo = (reu.get("hippodrome") or {}).get("libelleCourt")
            specs = reu.get("specialites") or []
            for c in reu.get("courses", []) or []:
                nR, nC = c["numReunion"], c["numOrdre"]
                info = dict(
                    course=f"R{nR}C{nC}", hippodrome=hippo,
                    libelle=c.get("libelleCourt") or c.get("libelle"),
                    discipline=c.get("discipline"),
                    specialite=specs[0] if specs else c.get("specialite"),
                    distance=c.get("distance"),
                    nb_partants=c.get("nombreDeclaresPartants"),
                    heure=c.get("heureDepart"),
                    ordre_arrivee=c.get("ordreArrivee"),   # None tant que pas couru
                    quinte=any("QUINTE_PLUS" in str(pa.get("typePari"))
                               for pa in (c.get("paris") or [])),   # course Quinté+ ?
                )
                taches.append(_get(client, sem, f"{BASE}/{jj}/R{nR}/C{nC}/participants"))
                # rapports place : uniquement pour les courses deja courues
                if c.get("ordreArrivee"):
                    rap_taches.append(_get(client, sem, f"{BASE}/{jj}/R{nR}/C{nC}/rapports-definitifs"))
                else:
                    rap_taches.append(_none())
                meta.append(info)

        resultats = await asyncio.gather(*taches)
        rap_resultats = await asyncio.gather(*rap_taches)

    for info, data, rap_data in zip(meta, resultats, rap_resultats):
        if not data:
            continue
        ordre = info.get("ordre_arrivee")
        place_map = _parse_rapports(rap_data, "SIMPLE_PLACE")
        gagnant_map = _parse_rapports(rap_data, "SIMPLE_GAGNANT")
        info_sans_ordre = {k: v for k, v in info.items() if k != "ordre_arrivee"}
        for p in data.get("participants", []):
            if p.get("statut") == "NON_PARTANT":
                continue
            gains = p.get("gainsParticipant") or {}
            ref = p.get("dernierRapportReference") or {}
            lignes.append({
                **info_sans_ordre,
                "course_finie": ordre is not None,               # la course est-elle courue ?
                "position": _position(ordre, p.get("numPmu")),   # arrivee reelle si dispo
                "rapport_place": place_map.get(p.get("numPmu")),  # vrai gain place si couru
                "rapport_gagnant": gagnant_map.get(p.get("numPmu")),  # vrai gain gagnant si couru
                "num_pmu": p.get("numPmu"), "nom": p.get("nom"),
                "age": p.get("age"), "sexe": p.get("sexe"), "musique": p.get("musique"),
                "nombre_courses": p.get("nombreCourses"),
                "nombre_victoires": p.get("nombreVictoires"),
                "nombre_places": p.get("nombrePlaces"),
                "gains_carriere": gains.get("gainsCarriere"),
                "gains_annee": gains.get("gainsAnneeEnCours"),
                "place_corde": p.get("placeCorde"),
                "handicap_poids": p.get("handicapPoids"),
                "cote_reference": ref.get("rapport"),
                "driver": p.get("driver"),
            })
    return pd.DataFrame(lignes)


def pronostics(jour_iso: str = None) -> pd.DataFrame:
    """Retourne les pronos du jour : 1 ligne par cheval avec proba place/gagnant."""
    if jour_iso is None:
        jour_iso = date.today().isoformat()

    df = asyncio.run(_recuperer(jour_iso))
    if df.empty:
        return df

    feats = features_pour_prediction(df)
    m_place = lgb.Booster(model_file="modele_place.txt")
    m_gag = lgb.Booster(model_file="modele_gagnant.txt")
    df["proba_place"] = m_place.predict(feats[FEATURES_SAFE])
    df["proba_gagnant"] = m_gag.predict(feats[FEATURES_SAFE])
    df["valeur"] = df["proba_gagnant"] * pd.to_numeric(df["cote_reference"], errors="coerce")

    # Rang dans la course selon la proba de place / de gagnant
    df["rang_place"] = df.groupby("course")["proba_place"].rank(ascending=False, method="first")
    df["rang_gagnant"] = df.groupby("course")["proba_gagnant"].rank(ascending=False, method="first")
    df["jour"] = jour_iso
    return df.sort_values(["course", "proba_place"], ascending=[True, False])


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else None
    df = pronostics(d)
    if df.empty:
        print("Aucune course trouvee pour cette date.")
    else:
        print(f"{df['course'].nunique()} courses, {len(df)} partants\n")
        # Meilleur pick 'place' par course
        top = df[df["rang_place"] == 1]
        print("=== Pronostic PLACE (le cheval le plus sur par course) ===")
        for _, r in top.iterrows():
            conf = "FORT" if r["proba_place"] >= 0.6 else "moyen"
            print(f"  {r['course']:6} {str(r['hippodrome'])[:14]:14} -> #{int(r['num_pmu']):>2} {str(r['nom'])[:20]:20} "
                  f"place={r['proba_place']:.0%} cote_matin={r['cote_reference']} [{conf}]")
