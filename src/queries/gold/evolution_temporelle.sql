SELECT 
    meta_modele_llm,
    tour,
    COUNT(joueur_1_profil) AS nombre_matchs_observes,
    AVG(joueur_1_choix) AS taux_cooperation_moyen_j1,
    AVG(joueur_2_choix) AS taux_cooperation_moyen_j2,
    AVG(ecart_score_j1_vs_j2) AS ecart_score_moyen,
    AVG(CASE WHEN joueur_1_choix = 0 AND joueur_2_choix_precedent = 0 THEN 1.0 ELSE 0.0 END) AS propension_vengeance_moyenne_j1
FROM read_parquet('{chemin_silver}')
GROUP BY 
    meta_modele_llm,
    tour