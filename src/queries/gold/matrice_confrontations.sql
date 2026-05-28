SELECT 
    meta_modele_llm, 
    joueur_1_profil, 
    joueur_2_profil,
    param_total_tours_partie,
    COUNT(tour) AS total_tours_joues,
    AVG(joueur_1_gain) AS gain_moyen_j1_par_tour,
    AVG(joueur_2_gain) AS gain_moyen_j2_par_tour,
    AVG(joueur_1_choix) AS taux_cooperation_j1,
    AVG(joueur_2_choix) AS taux_cooperation_j2,
    AVG(CASE WHEN joueur_1_choix = 1 AND joueur_2_choix = 1 THEN 1.0 ELSE 0.0 END) AS taux_cooperation_reciproque,
    AVG(CASE WHEN joueur_1_choix = 0 AND joueur_2_choix = 1 THEN 1.0 ELSE 0.0 END) AS taux_exploitation_j1_sur_j2
FROM read_parquet('{chemin_silver}')
GROUP BY 
    meta_modele_llm, 
    joueur_1_profil, 
    joueur_2_profil,
    param_total_tours_partie