# dns_contournement.py — Contourne le blocage DNS de pmu.fr (frequent a Abidjan)
#
# Certaines connexions (FAI ivoiriens notamment) ne resolvent pas le domaine
# online.turfinfo.api.pmu.fr : le nom ne se traduit pas en adresse IP
# ("getaddrinfo failed"), alors que la connexion internet marche tres bien.
#
# Solution : on demande l'IP a un DNS chiffre (DNS-over-HTTPS de Google, puis
# Cloudflare en secours), qui lui n'est pas bloque, et on force la resolution
# locale de ce host vers cette IP. Le nom de domaine reste utilise pour le
# certificat TLS (SNI), donc la connexion HTTPS est parfaitement valide.

import socket
import httpx

HOSTS_PMU = ["online.turfinfo.api.pmu.fr"]

# Resolveurs DNS-over-HTTPS (renvoient du JSON). Essayes dans l'ordre.
DOH = [
    ("https://dns.google/resolve", "Google"),
    ("https://cloudflare-dns.com/dns-query", "Cloudflare"),
]


def _resoudre_doh(host: str) -> list[str]:
    """Retourne la liste des IP d'un host via DNS-over-HTTPS."""
    for url, nom in DOH:
        try:
            headers = {"accept": "application/dns-json"}
            r = httpx.get(url, params={"name": host, "type": "A"},
                          headers=headers, timeout=15)
            if r.status_code == 200:
                ips = [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]
                if ips:
                    return ips
        except Exception:
            continue
    return []


def installer(log=None):
    """Installe le contournement DNS. A appeler UNE fois au demarrage.
    Retourne True si au moins un host PMU a pu etre resolu."""
    table = {}
    for host in HOSTS_PMU:
        # Si la resolution normale marche deja, on ne touche a rien
        try:
            socket.getaddrinfo(host, 443)
            continue
        except socket.gaierror:
            pass
        ips = _resoudre_doh(host)
        if ips:
            table[host] = ips[0]
            if log:
                log.info(f"  Contournement DNS : {host} -> {ips[0]} (via DoH)")
        elif log:
            log.warning(f"  Impossible de resoudre {host} meme via DoH")

    if not table:
        return True  # rien a contourner (resolution normale OK)

    def _cible(host):
        """Retourne l'IP de remplacement, en gerant le cas ou host est en bytes."""
        cle = host.decode() if isinstance(host, (bytes, bytearray)) else host
        return table.get(cle)

    # 1) Chemin SYNCHRONE : socket.getaddrinfo (httpx.get, requests...)
    _orig = socket.getaddrinfo

    def _patched(host, *args, **kwargs):
        ip = _cible(host)
        return _orig(ip if ip else host, *args, **kwargs)

    socket.getaddrinfo = _patched

    # 2) Chemin ASYNCHRONE : asyncio resout via loop.getaddrinfo, PAS via
    #    socket.getaddrinfo. On patche donc aussi la boucle d'evenements,
    #    sinon httpx.AsyncClient echoue malgre le patch ci-dessus.
    #    (Attention : httpx passe le host en BYTES a ce niveau.)
    import asyncio
    _orig_loop = asyncio.base_events.BaseEventLoop.getaddrinfo

    async def _patched_loop(self, host, port, *args, **kwargs):
        ip = _cible(host)
        return await _orig_loop(self, ip if ip else host, port, *args, **kwargs)

    asyncio.base_events.BaseEventLoop.getaddrinfo = _patched_loop
    return True


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    installer(logging.getLogger())
    # Test
    r = httpx.get(f"https://{HOSTS_PMU[0]}/rest/client/1/programme/14072024",
                  timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    print("Test requete PMU :", r.status_code)
