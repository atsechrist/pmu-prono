# db.py — Base de donnees SQLite du projet PMU Prono
# Definit le schema et les fonctions d'acces a la base.
#
# 3 tables :
#   - courses        : 1 ligne par course (date, hippodrome, discipline, distance, arrivee...)
#   - participants   : 1 ligne par cheval dans une course (musique, cote, driver, arrivee...)
#   - scrape_journal : suivi des dates deja recuperees (pour ne jamais rescraper)

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pmu.db"


def connexion() -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec les bons reglages."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL = meilleures perfs en ecriture continue (le scraper ecrit beaucoup)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def initialiser_db():
    """Cree les tables si elles n'existent pas."""
    conn = connexion()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id                TEXT PRIMARY KEY,   -- ex: 2024-07-14_R1C1
            date              TEXT NOT NULL,       -- AAAA-MM-JJ
            num_reunion       INTEGER,
            num_course        INTEGER,
            hippodrome_code   TEXT,
            hippodrome        TEXT,
            pays              TEXT,
            discipline        TEXT,                -- ATTELE / MONTE / PLAT / HAIES / STEEPLE...
            specialite        TEXT,                -- TROT / PLAT / OBSTACLE
            distance          INTEGER,
            corde             TEXT,
            categorie         TEXT,
            condition_age     TEXT,
            condition_sexe    TEXT,
            nb_partants       INTEGER,
            montant_prix      INTEGER,
            type_piste        TEXT,
            penetrometre      TEXT,                -- etat du terrain (obstacle/plat)
            heure_depart      INTEGER,             -- timestamp ms
            ordre_arrivee     TEXT                 -- JSON : [[2],[10],[1]...] = arrivee par numero
        );

        CREATE TABLE IF NOT EXISTS participants (
            course_id         TEXT NOT NULL,
            num_pmu           INTEGER NOT NULL,
            id_cheval         INTEGER,
            nom               TEXT,
            age               INTEGER,
            sexe              TEXT,
            race              TEXT,
            driver            TEXT,
            entraineur        TEXT,
            proprietaire      TEXT,
            musique           TEXT,                -- perfs recentes ex "1p2p4p6p"
            nombre_courses    INTEGER,
            nombre_victoires  INTEGER,
            nombre_places     INTEGER,
            gains_carriere    INTEGER,
            gains_annee       INTEGER,
            place_corde       INTEGER,
            handicap_poids    INTEGER,
            poids_monte       INTEGER,
            oeilleres         TEXT,
            allure            TEXT,
            nom_pere          TEXT,
            nom_mere          TEXT,
            cote_reference    REAL,                -- cote matinale (de reference)
            cote_finale       REAL,                -- derniere cote directe avant depart
            position_arrivee  INTEGER,             -- place reelle a l'arrivee (1=gagnant, NULL=non place)
            statut            TEXT,                -- PARTANT / NON_PARTANT
            PRIMARY KEY (course_id, num_pmu),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS scrape_journal (
            date       TEXT PRIMARY KEY,   -- AAAA-MM-JJ
            statut     TEXT,               -- OK / VIDE / ERREUR
            nb_courses INTEGER,
            maj        TEXT                -- horodatage du traitement
        );

        CREATE INDEX IF NOT EXISTS idx_courses_date ON courses(date);
        CREATE INDEX IF NOT EXISTS idx_courses_specialite ON courses(specialite);
        CREATE INDEX IF NOT EXISTS idx_part_cheval ON participants(id_cheval);
        CREATE INDEX IF NOT EXISTS idx_part_course ON participants(course_id);
        """
    )
    conn.commit()
    conn.close()


def date_deja_traitee(conn: sqlite3.Connection, date: str) -> bool:
    """Retourne True si la date a deja ete recuperee avec succes (OK ou VIDE)."""
    row = conn.execute(
        "SELECT statut FROM scrape_journal WHERE date = ? AND statut IN ('OK','VIDE')",
        (date,),
    ).fetchone()
    return row is not None


def marquer_date(conn, date, statut, nb_courses=0):
    """Enregistre le resultat du traitement d'une date dans le journal."""
    from datetime import datetime
    conn.execute(
        "INSERT OR REPLACE INTO scrape_journal (date, statut, nb_courses, maj) VALUES (?,?,?,?)",
        (date, statut, nb_courses, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


if __name__ == "__main__":
    initialiser_db()
    print(f"Base initialisee : {DB_PATH}")
