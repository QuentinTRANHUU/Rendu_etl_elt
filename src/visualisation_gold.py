import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# 1. Chargement de la configuration
load_dotenv()
DOSSIER_RACINE = os.getenv("CHEMIN_DOSSIER_DATA", "data")
DOSSIER_GOLD = os.path.join(DOSSIER_RACINE, "gold")

# Configuration de la page Streamlit
st.set_page_config(page_title="Analyse Pipeline GOLD - Dilemme du Prisonnier", layout="wide")
st.title("🏆 Visualisation de la Couche GOLD")
st.write("Ce dashboard consomme directement les fichiers Parquet générés par DuckDB.")

# Définition des chemins vers tes fichiers Parquet
chemin_benchmark = os.path.join(DOSSIER_GOLD, "gold_benchmark_runs.parquet")
chemin_evolution = os.path.join(DOSSIER_GOLD, "gold_evolution_temporelle.parquet")
chemin_matrice = os.path.join(DOSSIER_GOLD, "gold_matrice_confrontations.parquet")

# Vérification globale de l'existence des fichiers
if not (os.path.exists(chemin_benchmark) and os.path.exists(chemin_evolution) and os.path.exists(chemin_matrice)):
    st.error(f"❌ Fichiers Gold introuvables dans `{DOSSIER_GOLD}`. Exécute d'abord ton script silver_to_gold.py !")
else:
    # Chargement des données
    df_benchmark = pd.read_parquet(chemin_benchmark)
    df_evolution = pd.read_parquet(chemin_evolution)
    df_matrice = pd.read_parquet(chemin_matrice)

    # Création d'onglets pour correspondre à tes 3 requêtes SQL
    tab1, tab2, tab3 = st.tabs([
        "📊 Benchmark des Runs", 
        "📈 Évolution Temporelle", 
        "🧮 Matrice des Profils"
    ])

    # ----------------------------------------------------
    # ONGLET 1 : BENCHMARK DES RUNS
    # ----------------------------------------------------
    with tab1:
        st.header("Analyse comparative globale des Agents")
        st.write("Données issues de `benchmark_runs.sql` (performances agrégées par profil).")
        
        # Filtre par modèle LLM
        modeles = df_benchmark["meta_modele_llm"].unique()
        modele_choisi = st.selectbox("Filtrer par modèle LLM :", modeles, key="sb_bench")
        df_bench_filtré = df_benchmark[df_benchmark["meta_modele_llm"] == modele_choisi]

        # Graphique : Score moyen par tour par agent
        st.subheader("Score moyen obtenu par tour")
        st.bar_chart(
            data=df_bench_filtré, 
            x="profil_agent", 
            y="score_moyen_par_tour"
        )

        # Graphique : Taux de coopération global
        st.subheader("Taux de coopération global par Profil")
        df_bench_filtré["Taux Coop (%)"] = df_bench_filtré["taux_cooperation_global"] * 100
        st.bar_chart(data=df_bench_filtré, x="profil_agent", y="Taux Coop (%)")

        # Table brute
        st.subheader("Données brutes de l'agrégation")
        st.dataframe(df_bench_filtré)

    # ----------------------------------------------------
    # ONGLET 2 : ÉVOLUTION TEMPORELLE
    # ----------------------------------------------------
    with tab2:
        st.header("Comportement des Agents au fil des tours")
        st.write("Données issues de `evolution_temporelle.sql` (dynamique de jeu par tour).")

        modele_choisi_2 = st.selectbox("Filtrer par modèle LLM :", modeles, key="sb_evo")
        df_evo_filtré = df_evolution[df_evolution["meta_modele_llm"] == modele_choisi_2]

        # Graphique de coopération croisée
        st.subheader("Taux de coopération moyen (J1 vs J2) par Tour")
        df_line = df_evo_filtré.set_index("tour")[["taux_cooperation_moyen_j1", "taux_cooperation_moyen_j2"]]
        st.line_chart(df_line)

        # Graphique de la propension à la vengeance
        if "propension_vengeance_moyenne_j1" in df_evo_filtré.columns:
            st.subheader("Propension moyenne à la vengeance du Joueur 1")
            st.line_chart(data=df_evo_filtré, x="tour", y="propension_vengeance_moyenne_j1")

        st.dataframe(df_evo_filtré)

    # ----------------------------------------------------
    # ONGLET 3 : MATRICE DES CONFRONTATIONS (Version Symétrique sans None)
    # ----------------------------------------------------
    with tab3:
        st.header("Matrice des gains croisés (Tournoi d'Axelrod)")
        st.write("Données issues de `matrice_confrontations.sql` (Rapports de force 1 VS 1).")

        modele_choisi_3 = st.selectbox("Filtrer par modèle LLM :", modeles, key="sb_mat")
        df_mat_filtré = df_matrice[df_matrice["meta_modele_llm"] == modele_choisi_3]

        if not df_mat_filtré.empty:
            # --- 1. MATRICE DES GAINS RECONSTRUITE ---
            st.subheader("Matrice des gains moyens de l'Agent en Ligne face à l'Agent en Colonne")
            
            # On prend la perspective où l'agent est Joueur 1
            p1_gains = df_mat_filtré.pivot_table(index="joueur_1_profil", columns="joueur_2_profil", values="gain_moyen_j1_par_tour", aggfunc="mean")
            # On prend la perspective inversée où l'agent était enregistré en Joueur 2
            p2_gains = df_mat_filtré.pivot_table(index="joueur_2_profil", columns="joueur_1_profil", values="gain_moyen_j2_par_tour", aggfunc="mean")
            # On fusionne les deux pour remplir tous les vides !
            pivot_gains = p1_gains.combine_first(p2_gains)
            
            # Affichage stylisé (Formatage des arrondis et remplacement des derniers NaN par "-")
            st.dataframe(pivot_gains.style.background_gradient(cmap="viridis").format(precision=2, na_rep="-"))

            # --- 2. MATRICE DE COOPÉRATION RECONSTRUITE ---
            st.subheader("Taux de coopération réciproque (Coopération mutuelle en %)")
            
            p1_coop = df_mat_filtré.pivot_table(index="joueur_1_profil", columns="joueur_2_profil", values="taux_cooperation_reciproque", aggfunc="mean")
            p2_coop = df_mat_filtré.pivot_table(index="joueur_2_profil", columns="joueur_1_profil", values="taux_cooperation_reciproque", aggfunc="mean")
            pivot_coop = p1_coop.combine_first(p2_coop) * 100
            
            st.dataframe(pivot_coop.style.background_gradient(cmap="YlGnBu").format(precision=2, na_rep="-"))
        else:
            st.warning("Aucune donnée disponible pour ce modèle de LLM.")

        st.subheader("Données de confrontation complètes")
        st.dataframe(df_mat_filtré)