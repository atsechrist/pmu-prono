# maj_jour.py — Robot quotidien : ajoute les résultats de la VEILLE dans Supabase.
#
# Lancé chaque matin par GitHub Actions (.github/workflows/maj_historique.yml).
# Utilise les modèles déjà entraînés (dépôt) + l'API PMU (comme pronos_jour).
# N'a PAS besoin de pmu.db : il ne traite qu'une journée à la fois.
#
# Secret requis (variable d'environnement) :
#   PG_DSN = postgresql://postgres.<ref>:<mdp>@aws-0-...pooler.supabase.com:5432/postgres?sslmode=require

import os
import asyncio
from datetime import date, timedelta

import numpy as np
import pandas as pd
import httpx
import psycopg2
from psycopg2.extras import execute_values

from pronos_jour import pronostics

DSN = os.environ["PG_DSN"]
BASE = "https://online.turfinfo.api.pmu.fr/rest/client/1/programme"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _v(x):
    """NaN/None -> None, sinon float."""
    return None if (x is None or (isinstance(x, float) and x != x)) else float(x)


def calc_perf_detail(df, jour):
    """Reproduit la logique de l'historique pour UNE journée (Placé / Gagnant / MIX)."""
    df = df[df["course_finie"] == True].copy()
    perf, detail = [], []
    if df.empty:
        return perf, detail

    # --- PLACE : meilleur pick placé par course ---
    pf = df[df["rang_place"] == 1].copy()
    pf["confiance"] = np.where(pf["proba_place"] >= 0.6, "FORT", "Moyen")
    pf["succes"] = ((pf["position"].notna()) & (pf["position"] <= 3)).astype(int)
    pf["gain"] = np.where((pf["succes"] == 1) & pf["rapport_place"].notna(), pf["rapport_place"], 0.0)
    for conf, g in pf.groupby("confiance"):
        gg = float(g["gain"].sum())
        perf.append((jour, "PLACE", conf, len(g), int(g["succes"].sum()), gg, gg - len(g)))
    for _, r in pf[pf["confiance"] == "FORT"].iterrows():
        detail.append((jour, jour[:7], _v(r["heure"]), r["course"], r["hippodrome"],
                       int(r["num_pmu"]), r["nom"], float(r["proba_place"]),
                       int(r["succes"]), _v(r["rapport_place"]), float(r["gain"])))

    # --- GAGNANT : meilleur pick gagnant par course ---
    gf = df[df["rang_gagnant"] == 1].copy()
    gf["confiance"] = np.where(gf["proba_gagnant"] >= 0.4, "FORT", "Moyen")
    gf["succes"] = ((gf["position"].notna()) & (gf["position"] == 1)).astype(int)
    gf["gain"] = np.where((gf["succes"] == 1) & gf["rapport_gagnant"].notna(), gf["rapport_gagnant"], 0.0)
    for conf, g in gf.groupby("confiance"):
        gg = float(g["gain"].sum())
        perf.append((jour, "GAGNANT", conf, len(g), int(g["succes"].sum()), gg, gg - len(g)))

    # --- MIX = Placé FORT (>=0.6) + Gagnant Moyen (<0.4) ---
    pb = pf[pf["proba_place"] >= 0.6]
    gb = gf[gf["proba_gagnant"] < 0.4]
    n = len(pb) + len(gb)
    if n:
        s = int(pb["succes"].sum() + gb["succes"].sum())
        g = float(pb["gain"].sum() + gb["gain"].sum())
        perf.append((jour, "MIX", "MIX", n, s, g, g - n))

    return perf, detail


async def _fetch_json(url):
    async with httpx.AsyncClient(headers=HEADERS) as client:
        for essai in range(3):
            try:
                r = await client.get(url, timeout=20)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (204, 404):
                    return None
            except Exception:
                await asyncio.sleep(2 * (essai + 1))
    return None


def calc_quinte(df, jour):
    """Résultat Quinté de la journée : top-5 du modèle vs arrivée + dividendes ordre/désordre."""
    q = df[df["quinte"] == True]
    if q.empty:
        return None
    course = q["course"].iloc[0]                 # ex "R1C3"
    jj = jour[8:10] + jour[5:7] + jour[0:4]
    nR = course.split("C")[0][1:]
    nC = course.split("C")[1]
    data = asyncio.run(_fetch_json(f"{BASE}/{jj}/R{nR}/C{nC}/rapports-definitifs"))

    do = dd = None
    for bloc in (data or []):
        if bloc.get("typePari") == "QUINTE_PLUS":
            raps = bloc.get("rapports", [])
            def dv(mot):
                for rap in raps:
                    if mot.lower() in str(rap.get("libelle", "")).lower():
                        d = rap.get("dividendePourUnEuro")
                        if d is not None:
                            return d / 100.0
                return None
            do, dd = dv("Ordre"), dv("sordre")
            break

    qc = df[df["course"] == course].copy()
    modele = list(qc[qc["rang_place"] <= 5].sort_values("rang_place")["num_pmu"])
    arr = qc.dropna(subset=["position"])
    arr = list(arr[arr["position"] <= 5].sort_values("position")["num_pmu"])
    ok = len(modele) == 5 and len(arr) == 5
    gain_ordre = float(do) if (ok and modele == arr and do) else 0.0
    gain_des = float(dd) if (ok and set(modele) == set(arr) and dd) else 0.0
    return (f"{jour}_{course}", jour, jour[:7], gain_ordre, gain_des)


def main():
    jour = (date.today() - timedelta(days=1)).isoformat()
    print(f"[maj_jour] Jour traité : {jour}")

    df = pronostics(jour)
    if df is None or df.empty:
        print("[maj_jour] Aucune course FR ce jour — rien à faire.")
        return
    if not df["course_finie"].any():
        print("[maj_jour] Courses pas encore terminées — on réessaiera demain.")
        return

    perf, detail = calc_perf_detail(df, jour)
    quinte = calc_quinte(df, jour)
    print(f"[maj_jour] perf={len(perf)} lignes, detail={len(detail)}, quinté={'oui' if quinte else 'non'}")

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    if perf:
        execute_values(cur,
            "insert into public.hist_perf (date,strategie,confiance,paris,succes,gains,profit) values %s "
            "on conflict (date,strategie,confiance) do update set "
            "paris=excluded.paris, succes=excluded.succes, gains=excluded.gains, profit=excluded.profit",
            perf)
    cur.execute("delete from public.hist_detail where date = %s", (jour,))
    if detail:
        execute_values(cur,
            "insert into public.hist_detail "
            "(date,mois,heure_depart,course,hippodrome,num,nom,proba,place,rapport_place,gain) values %s",
            detail)
    if quinte:
        execute_values(cur,
            "insert into public.hist_quinte (course_id,date,mois,gain_ordre,gain_des) values %s "
            "on conflict (course_id) do update set date=excluded.date, mois=excluded.mois, "
            "gain_ordre=excluded.gain_ordre, gain_des=excluded.gain_des",
            [quinte])
    conn.commit()
    cur.close()
    conn.close()
    print("[maj_jour] Termine.")


if __name__ == "__main__":
    main()
