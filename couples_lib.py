# couples_lib.py — Logique partagée pour les paris Couplé Gagnant / Couplé Placé / Trio.
# Utilisé par backfill_couples.py (historique) et maj_jour.py (robot quotidien).


def gagnants(top, arr, nb):
    """Le pick du modèle gagne-t-il ? Retourne (couple_gagnant, couple_place, trio).

    top : n° des chevaux triés par proba du modèle (meilleur d'abord)
    arr : n° des chevaux triés par ordre d'arrivée réel (1er d'abord)
    nb  : nombre de partants (règle du placé : top 3 si >=8, sinon top 2)
    """
    if len(top) < 2 or len(arr) < 2:
        return False, False, False
    top2, arr2 = set(top[:2]), set(arr[:2])
    places = set(arr[:3]) if nb >= 8 else set(arr[:2])
    couple_g = top2 == arr2
    couple_p = top2 <= places
    trio = len(top) >= 3 and len(arr) >= 3 and set(top[:3]) == set(arr[:3])
    return couple_g, couple_p, trio


def dividende(rapports_data, type_pari, gagnante):
    """Dividende (pour 1€) de la combinaison 'gagnante' (set de str) dans les rapports."""
    for bloc in (rapports_data or []):
        if bloc.get("typePari") == type_pari:
            for rp in bloc.get("rapports", []):
                combi = rp.get("combinaison") or ""
                if "NP" in combi:
                    continue
                if set(combi.split("-")) == gagnante:
                    d = rp.get("dividendePourUnEuro")
                    return d / 100.0 if d is not None else 0.0
    return 0.0
