# auth.py — Authentification, droits par stratégie, et administration (Supabase).
#
# - Connexion / inscription email + mot de passe via Supabase Auth.
# - Droits lus dans la table `entitlements` (une ligne par utilisateur).
# - Superadmin (emails dans les secrets) : voit tous les users et gère leurs droits.
#
# Note : pas de persistance de session pour l'instant — un rafraîchissement de page
# redemande la connexion (limite de Streamlit Community Cloud avec les cookies).

import streamlit as st
from supabase import create_client, Client

# Les 4 stratégies (identifiants internes) + libellés d'affichage
STRATEGIES = ["place", "gagnant", "mix", "quinte"]
LIBELLES = {"place": "⭐ Placé", "gagnant": "🏆 Gagnant",
            "mix": "🎲 MIX", "quinte": "🎰 Quinté+"}
DROITS_DEFAUT = list(STRATEGIES)


# ══════════════════ Clients Supabase ══════════════════

def _anon_client() -> Client:
    """Client public (clé anon) : connexion, inscription, lecture de SES droits."""
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["key"])


def _admin_client() -> Client:
    """Client admin (clé service_role) : lister tous les users, écrire les droits."""
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])


# ══════════════════ Droits ══════════════════

def est_admin(email: str) -> bool:
    """True si l'email est un superadmin (liste dans les secrets)."""
    try:
        admins = [e.lower() for e in st.secrets["admin"]["emails"]]
    except Exception:
        admins = []
    return bool(email) and email.lower() in admins


def _droits(user_id: str, email: str, client: Client) -> list[str]:
    """Stratégies autorisées pour cet utilisateur. Les admins ont tout."""
    if est_admin(email):
        return list(STRATEGIES)
    try:
        r = (client.table("entitlements").select("strategies")
             .eq("user_id", user_id).limit(1).execute())
        if r.data:
            return [s for s in (r.data[0].get("strategies") or []) if s in STRATEGIES]
    except Exception:
        pass
    return []


# ══════════════════ État de session ══════════════════

def utilisateur_actuel():
    return st.session_state.get("user")


def droits_actuels() -> list[str]:
    return st.session_state.get("droits", [])


def a_droit(strat: str) -> bool:
    return strat in droits_actuels()


def _memoriser(user, client: Client):
    st.session_state["user"] = {"id": user.id, "email": user.email}
    st.session_state["droits"] = _droits(user.id, user.email, client)


# ══════════════════ Connexion / inscription ══════════════════

def deconnexion():
    try:
        _anon_client().auth.sign_out()
    except Exception:
        pass
    for cle in ("user", "droits"):
        st.session_state.pop(cle, None)
    st.rerun()


def formulaire_auth() -> bool:
    """Affiche connexion / inscription. Retourne True si connecté."""
    if utilisateur_actuel():
        return True

    onglet_co, onglet_ins = st.tabs(["🔑 Se connecter", "✨ Créer un compte"])

    with onglet_co:
        with st.form("form_connexion"):
            email = st.text_input("Email")
            mdp = st.text_input("Mot de passe", type="password")
            valider = st.form_submit_button("Se connecter", use_container_width=True)
        if valider:
            try:
                client = _anon_client()
                res = client.auth.sign_in_with_password(
                    {"email": email.strip(), "password": mdp})
                _memoriser(res.user, client)
                st.rerun()
            except Exception:
                st.error("Email ou mot de passe incorrect (ou compte pas encore confirmé).")

    with onglet_ins:
        with st.form("form_inscription"):
            email = st.text_input("Email", key="ins_email")
            mdp = st.text_input("Mot de passe (min. 6 caractères)", type="password", key="ins_mdp")
            valider = st.form_submit_button("Créer mon compte", use_container_width=True)
        if valider:
            if len(mdp) < 6:
                st.error("Le mot de passe doit faire au moins 6 caractères.")
            else:
                try:
                    client = _anon_client()
                    res = client.auth.sign_up({"email": email.strip(), "password": mdp})
                    if res.session is None:
                        st.success("✅ Compte créé ! Vérifie ta boîte mail pour confirmer "
                                   "ton adresse, puis connecte-toi.")
                    else:
                        _memoriser(res.user, client)
                        st.rerun()
                except Exception as e:
                    st.error(f"Inscription impossible : {e}")

    return utilisateur_actuel() is not None


# ══════════════════ Administration (superadmin) ══════════════════

def lister_utilisateurs() -> list[dict]:
    """Liste tous les utilisateurs + leurs droits. Réservé aux admins (clé service_role)."""
    admin = _admin_client()
    users = admin.auth.admin.list_users()
    if hasattr(users, "users"):
        users = users.users
    droits_par_user = {}
    try:
        rows = admin.table("entitlements").select("user_id, strategies").execute()
        for row in (rows.data or []):
            droits_par_user[row["user_id"]] = row.get("strategies") or []
    except Exception:
        pass
    resultat = []
    for u in users:
        email = getattr(u, "email", "") or ""
        resultat.append({
            "user_id": u.id,
            "email": email,
            "strategies": list(STRATEGIES) if est_admin(email)
                          else droits_par_user.get(u.id, []),
            "admin": est_admin(email),
        })
    return resultat


def definir_droits(user_id: str, strategies: list[str]):
    """Écrit les droits d'un utilisateur (upsert). Réservé aux admins (clé service_role)."""
    from datetime import datetime, timezone
    admin = _admin_client()
    strategies = [s for s in strategies if s in STRATEGIES]
    admin.table("entitlements").upsert({
        "user_id": user_id,
        "strategies": strategies,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
