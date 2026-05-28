import os
import glob
import re
import duckdb
from dotenv import load_dotenv

# Chargement de l'environnement et des dossiers
load_dotenv()
DOSSIER_RACINE = os.getenv("CHEMIN_DOSSIER_DATA", "data")
DOSSIER_BRONZE = os.path.join(DOSSIER_RACINE, "bronze")
DOSSIER_SILVER = os.path.join(DOSSIER_RACINE, "silver")
CHEMIN_FINAL_SILVER = os.path.join(DOSSIER_SILVER, "registre_global_tournois.parquet")

def extraire_parametres_nom_fichier(nom_fichier):
    """
    Découpe le nom du fichier Bronze avec une regex pour récupérer les paramètres.
    """
    pattern = r"simulation_tournoi_(.*)_(\d+)_tours_(\d+)_memoire_(\d{8}_\d{6})\.parquet"
    match = re.search(pattern, nom_fichier)
    
    if match:
        return {
            "meta_modele_llm": match.group(1),
            "meta_nb_tours": int(match.group(2)),
            "meta_taille_memoire": int(match.group(3)),
            "meta_horodatage": match.group(4)
        }
    return {"meta_modele_llm": "inconnu", "meta_nb_tours": None, "meta_taille_memoire": None, "meta_horodatage": "inconnu"}

def construire_table_silver_unifiee():
    # Connexion DuckDB volatile (en mémoire pour effectuer les calculs de transition)
    con = duckdb.connect(database=':memory:')
    
    # Identifier les sessions déjà traitées dans l'historique Silver
    horodatages_traites = set()
    if os.path.exists(CHEMIN_FINAL_SILVER):
        print("Analyse du registre Silver existant via DuckDB...")
        # DuckDB peut requêter un fichier Parquet instantanément sans le charger en RAM
        sessions_existantes = con.execute(f"""
            SELECT DISTINCT meta_horodatage 
            FROM read_parquet('{CHEMIN_FINAL_SILVER.replace('\\', '/')}')
            WHERE meta_horodatage IS NOT NULL
        """).fetchall()
        horodatages_traites = {row[0] for row in sessions_existantes}
        print(f"{len(horodatages_traites)} simulation(s) distincte(s) détectée(s) dans le Silver.")

    # Scanner le dossier Bronze
    fichiers_bronze = glob.glob(os.path.join(DOSSIER_BRONZE, "*.parquet"))
    if not fichiers_bronze:
        print(f"Aucun fichier trouvé dans {DOSSIER_BRONZE}.")
        return
    
    fichiers_a_traiter = []
    
    # Filtrage incrémental des fichiers
    for chemin_fichier in fichiers_bronze:
        nom_fichier = os.path.basename(chemin_fichier)
        
        # Sécurité anti-fichier vide (0 octet)
        if os.path.getsize(chemin_fichier) == 0:
            print(f"Fichier vide détecté et ignoré : {nom_fichier}")
            continue
            
        metadonnees = extraire_parametres_nom_fichier(nom_fichier)
        horodatage_fichier = metadonnees["meta_horodatage"]
        
        if horodatage_fichier in horodatages_traites:
            continue
            
        fichiers_a_traiter.append((chemin_fichier, metadonnees))

    if not fichiers_a_traiter:
        print("Aucun nouveau fichier Bronze à intégrer. La couche Silver DuckDB est déjà à jour.")
        return

    print(f"Traitement massif de {len(fichiers_a_traiter)} nouvelle(s) simulation(s) avec DuckDB...")
    
    # Pour chaque nouveau fichier, on utilise DuckDB pour injecter les métadonnées,
    # encoder les choix et calculer les colonnes dérivées en flux continu (streaming).
    liste_tables_temporaires = []
    
    for index, (chemin, meta) in enumerate(fichiers_a_traiter):
        nom_table_temp = f"temp_session_{index}"
        
        chemin_sql_silver = os.path.join("src", "queries", "silver", "clean_and_enrich_bronze.sql")

        with open(chemin_sql_silver, "r", encoding="utf-8") as f:
            sql_template = f.read()

        # Remplacement manuel et ciblé pour ne pas interférer avec les clauses OVER (...) du SQL
        sql_final = sql_template \
            .replace("{chemin_bronze}", chemin.replace('\\', '/')) \
            .replace("{meta_modele_llm}", meta['meta_modele_llm']) \
            .replace("{meta_nb_tours}", str(meta['meta_nb_tours']) if meta['meta_nb_tours'] is not None else 'NULL') \
            .replace("{meta_taille_memoire}", str(meta['meta_taille_memoire']) if meta['meta_taille_memoire'] is not None else 'NULL') \
            .replace("{meta_horodatage}", meta['meta_horodatage'])

        # Construction et exécution de la table temporaire
        requete_transformation = f"CREATE TABLE {nom_table_temp} AS {sql_final}"
        con.execute(requete_transformation)
        liste_tables_temporaires.append(nom_table_temp)

    # Union des nouvelles données
    sql_union_nouveaux = " UNION ALL ".join([f"SELECT * FROM {t}" for t in liste_tables_temporaires])
    con.execute(f"CREATE TABLE nouveaux_traites AS {sql_union_nouveaux}")

    # Fusion finale et écriture physique
    os.makedirs(DOSSIER_SILVER, exist_ok=True)
    
    # Si un historique existe déjà, on combine l'ancien fichier Parquet et les nouveautés SQL
    if os.path.exists(CHEMIN_FINAL_SILVER):
        print("Fusion de l'historique global existant avec le nouvel incrément...")
        chemin_temp_silver = CHEMIN_FINAL_SILVER + ".tmp"
        
        con.execute(f"""
            COPY (
                SELECT * FROM read_parquet('{CHEMIN_FINAL_SILVER.replace('\\', '/')}')
                UNION ALL
                SELECT * FROM nouveaux_traites
            ) TO '{chemin_temp_silver.replace('\\', '/')}' (FORMAT PARQUET);
        """)
        
        # Remplacement sécurisé du fichier
        if os.path.exists(CHEMIN_FINAL_SILVER):
            os.remove(CHEMIN_FINAL_SILVER)
        os.rename(chemin_temp_silver, CHEMIN_FINAL_SILVER)
    else:
        # Premier lancement : on écrit directement la table SQL vers le fichier Parquet
        print("Création initiale du registre global Silver...")
        con.execute(f"COPY nouveaux_traites TO '{CHEMIN_FINAL_SILVER.replace('\\', '/')}' (FORMAT PARQUET);")

    # Affichage du volume final pour contrôle
    lignes_totales = con.execute(f"SELECT COUNT(*) FROM read_parquet('{CHEMIN_FINAL_SILVER.replace('\\', '/')}')").fetchone()[0]
    print(f"\nCouche Silver mise à jour avec succès via DuckDB !")
    print(f"Fichier unifié : '{CHEMIN_FINAL_SILVER}'")
    print(f"Volume total de l'historique : {lignes_totales} lignes centralisées.")

if __name__ == "__main__":
    construire_table_silver_unifiee()