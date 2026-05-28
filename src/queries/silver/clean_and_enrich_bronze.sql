SELECT 
    tour,
    joueur_1_profil,
    joueur_2_profil,
    
    -- Encodage direct (COOPERER -> 1, TRAHIR -> 0)
    CASE WHEN joueur_1_choix = 'COOPERER' THEN 1 ELSE 0 END AS joueur_1_choix,
    CASE WHEN joueur_2_choix = 'COOPERER' THEN 1 ELSE 0 END AS joueur_2_choix,
    
    joueur_1_gain,
    joueur_2_gain,
    joueur_1_score_cumule,
    joueur_2_score_cumule,
    joueur_1_justification_prive,
    joueur_2_justification_prive,
    joueur_1_justification_public,
    joueur_2_justification_public,
    param_duree_memoire,
    param_total_tours_partie,
    param_matrice_gains,
    
    -- Métadonnées dynamiques injectées par l'orchestrateur
    '{meta_modele_llm}' AS meta_modele_llm,
    {meta_nb_tours} AS meta_nb_tours,
    {meta_taille_memoire} AS meta_taille_memoire,
    '{meta_horodatage}' AS meta_horodatage,
    
    -- Calcul de l'écart de score
    (joueur_1_score_cumule - joueur_2_score_cumule) AS ecart_score_j1_vs_j2,
    
    -- Shift(1) via la fonction analytique LAG()
    LAG(CASE WHEN joueur_1_choix = 'COOPERER' THEN 1 ELSE 0 END) OVER (
        PARTITION BY joueur_1_profil, joueur_2_profil 
        ORDER BY tour
    ) AS joueur_1_choix_precedent,
    
    LAG(CASE WHEN joueur_2_choix = 'COOPERER' THEN 1 ELSE 0 END) OVER (
        PARTITION BY joueur_1_profil, joueur_2_profil 
        ORDER BY tour
    ) AS joueur_2_choix_precedent
    
FROM read_parquet('{chemin_bronze}')