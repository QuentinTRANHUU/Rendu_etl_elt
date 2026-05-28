WITH stats_globales AS (
    SELECT 
        meta_modele_llm,
        param_total_tours_partie,
        param_duree_memoire,
        joueur_1_profil AS profil_agent,
        COUNT(DISTINCT meta_horodatage) AS total_matchs_joues,
        AVG(joueur_1_choix) AS taux_cooperation_global,
        AVG(joueur_1_gain) AS score_moyen_par_tour
    FROM read_parquet('{chemin_silver}')
    GROUP BY 
        meta_modele_llm,
        param_total_tours_partie,
        param_duree_memoire,
        joueur_1_profil
),
scores_finaux AS (
    SELECT 
        meta_modele_llm,
        param_total_tours_partie,
        param_duree_memoire,
        joueur_1_profil AS profil_agent,
        AVG(joueur_1_score_cumule) AS score_cumule_moyen_fin_partie
    FROM read_parquet('{chemin_silver}')
    WHERE tour = param_total_tours_partie
    GROUP BY 
        meta_modele_llm,
        param_total_tours_partie,
        param_duree_memoire,
        joueur_1_profil
)
SELECT 
    sg.*,
    sf.score_cumule_moyen_fin_partie
FROM stats_globales sg
JOIN scores_finaux sf ON 
    sg.meta_modele_llm = sf.meta_modele_llm AND
    sg.param_total_tours_partie = sf.param_total_tours_partie AND
    sg.param_duree_memoire = sf.param_duree_memoire AND
    sg.profil_agent = sf.profil_agent