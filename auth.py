# auth.py — Authentification (email + mot de passe) et droits, via Supabase.
#
# Phase 1 (test) : tout inscrit a droit aux 4 strategies.
# Phase 2 (payant) : _droits_utilisateur() lira la table des abonnements.

import streamlit as st
from supabase import create_client, Client

# Les 4 strategies de l'app (identifiants internes)
STRATEGIES = ["place", "gagnant", "mix", "quinte"]
# Droits par defaut a l'inscription (pour l'instant : tout)
DROITS_DEFAUT = list(STRATEGIES)


def _client() -> Client:
    """Cree un client Supabase neuf (pas de cache : evite de partager l'etat
    d'authentification entre utilisateurs)."""
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["key"])


def _droits_utilisateur(user) -> list[str]:
    """Droits d'un utilisateur. Phase 1 : toutes les strategies.
    Phase 2 : lira les strategies payees dans la base."""
    return list(DROITS_DEFAUT)


# ---------- Etat de session ----------

def utilisateur_actuel():
    """Retourne le dict utilisateur connecte, ou None."""
    return st.session_state.get("user")


def droits_actuels() -> list[str]:
    return st.session_state.get("droits", [])


def a_droit(strat: str) -> bool:
    """True si l'utilisateur connecte a droit a cette strategie."""
    return strat in droits_actuels()


# ---------- Actions ----------

def _memoriser(user):
    st.session_state["user"] = {"id": user.id, "email": user.email}
    st.session_state["droits"] = _droits_utilisateur(user)


def deconnexion():
    try:
        _client().auth.sign_out()
    except Exception:
        pass
    for cle in ("user", "droits"):
        st.session_state.pop(cle, None)
    st.rerun()


def formulaire_auth() -> bool:
    """Affiche connexion / inscription. Retourne True si l'utilisateur est connecte."""
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
                res = _client().auth.sign_in_with_password(
                    {"email": email.strip(), "password": mdp})
                _memoriser(res.user)
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
                    res = _client().auth.sign_up(
                        {"email": email.strip(), "password": mdp})
                    if res.session is None:
                        # Confirmation par email activee : compte cree mais pas encore actif
                        st.success("✅ Compte créé ! Vérifie ta boîte mail pour confirmer "
                                   "ton adresse, puis connecte-toi.")
                    else:
                        _memoriser(res.user)
                        st.rerun()
                except Exception as e:
                    st.error(f"Inscription impossible : {e}")

    return utilisateur_actuel() is not None
