import os
import duckdb
from dotenv import load_dotenv

# Chargement de l'environnement et des dossiers
load_dotenv()
DOSSIER_RACINE = os.getenv("CHEMIN_DOSSIER_DATA", "data")
DOSSIER_SILVER = os.path.join(DOSSIER_RACINE, "silver")
DOSSIER_GOLD = os.path.join(DOSSIER_RACINE, "gold")

# Dossier contenant tes requêtes SQL externes
DOSSIER_QUERIES = os.path.join("src", "queries", "gold")

CHEMIN_SILVER = os.path.join(DOSSIER_SILVER, "registre_global_tournois.parquet")

def charger_et_executer_requete(con, nom_fichier_sql, chemin_export_parquet, chemin_silver_sql):
    """
    Lit un fichier SQL externe, injecte la source de données, et l'exécute dans DuckDB.
    """
    chemin_fichier_sql = os.path.join(DOSSIER_QUERIES, nom_fichier_sql)
    
    # Lecture du code SQL brut
    with open(chemin_fichier_sql, "r", encoding="utf-8") as f:
        sql_brut = f.read()
    
    # Injection dynamique du chemin vers la couche Silver Parquet
    sql_formate = sql_brut.format(chemin_silver=chemin_silver_sql)
    
    # Construction de la commande COPY de DuckDB pour exporter le résultat sur le disque
    commande_copy = f"COPY ({sql_formate}) TO '{chemin_export_parquet}' (FORMAT PARQUET);"
    
    # Exécution par le moteur DuckDB
    con.execute(commande_copy)

def generer_couche_gold():
    if not os.path.exists(CHEMIN_SILVER):
        print(f"Impossible de générer la couche Gold : le fichier Silver '{CHEMIN_SILVER}' est introuvable.")
        return

    # Connexion DuckDB volatile en mémoire
    con = duckdb.connect(database=':memory:')
    os.makedirs(DOSSIER_GOLD, exist_ok=True)
    
    print("Calcul de la couche Gold à partir des requêtes SQL externes...")
    chemin_silver_sql = CHEMIN_SILVER.replace('\\', '/')

    # Définition des cibles d'exportation
    table_configs = [
        {"sql": "matrice_confrontations.sql", "parquet": "gold_matrice_confrontations.parquet", "label": "Matrice des profils"},
        {"sql": "evolution_temporelle.sql", "parquet": "gold_evolution_temporelle.parquet", "label": "Évolution temporelle"},
        {"sql": "benchmark_runs.sql", "parquet": "gold_benchmark_runs.parquet", "label": "Benchmark des runs"}
    ]

    # Boucle d'exécution industrielle
    for config in table_configs:
        print(f"  └─ Traitement : {config['label']}...")
        chemin_export = os.path.join(DOSSIER_GOLD, config['parquet']).replace('\\', '/')
        
        # Appel générique de l'exécuteur de requêtes
        charger_et_executer_requete(con, config['sql'], chemin_export, chemin_silver_sql)

    print(f"\nCouche GOLD générée avec succès dans '{DOSSIER_GOLD}' !")

if __name__ == "__main__":
    generer_couche_gold()