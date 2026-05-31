# 🕵️‍♂️ Simulation du Dilemme du Prisonnier Itératif — Pipeline ETL/ELT Medallion

Ce projet implémente une architecture de données complète et industrialisée pour simuler, transformer et analyser des tournois du **Dilemme du Prisonnier Itératif** menés par des agents dotés de stratégies comportementales spécifiques ou propulsés par des modèles d'Intelligence Artificielle (LLM).

Inspiré de l'expérience historique de Robert Axelrod (1981), ce pipeline a été modernisé pour répondre à des problématiques de **Big Data** et de reproductibilité analytique en utilisant une architecture en cascade (Medallion) couplée à la puissance de calcul "Out-of-Core" de **DuckDB**.

---

## 📌 Sommaire

1. [🚀 Installation et Utilisation](#-installation-et-utilisation)
2. [🏗️ Architecture des Données](#%EF%B8%8F-architecture-des-données)
3. [📂 Arborescence du Projet](#-arborescence-du-projet)
4. [⚙️ Naming Convention (Couche Bronze)](#naming-convention-couche-bronze)
5. [📊 Schémas des Tables (Data Lineage)](#-schémas-des-tables-data-lineage)
6. [⚡ Choix Technologiques & Passage à l'Échelle](#-choix-technologiques--passage-à-léchelle)
7. [📈 Objectifs de l'Analyse Exploratoire](#-objectifs-de-lanalyse-exploratoire-couche-gold)

---

## 🚀 Installation et Utilisation

### 1. Prérequis

Assure-toi de disposer de Python 3.13.13 installé sur ta machine.

Installe Ollama `https://ollama.com/download/windows`

### 2. Cloner le projet et installer les dépendances

```bash
git clone git@github.com:QuentinTRANHUU/Rendu_etl_elt.git
cd RENDU_ETL_ELT
pip install -r requirements.txt
```

### 3. Configurer l'environnement

Copie le fichier d'exemple et ajuste les variables si nécessaire. Tu pourras y configurer les paramètres des parties, du LLM et le chemin du dossier data (attention : si tu personnalises ce chemin, fait bien attention à créer les trois sous-dossier `gold`, `silver` et `bronze`) :

```bash
cp .env.example .env
```

### 4. Exécution du Pipeline de Données

Le pipeline doit être exécuté de manière séquentielle en respectant l'ordre suivant :

#### Étape 1 : Génération des simulations (Bronze)

Génère les données brutes de tournoi à partir des profils, règles de jeu et formats de réponses configurés dans ./src/prompts_regles_et_profils.json.

```bash
python src/generation_bronze.py
```

#### Étape 2 : Nettoyage et Centralisation (Bronze → Silver)

Exécute la logique SQL de traitement incrémental via DuckDB pour alimenter le registre global sans retraiter les sessions déjà intégrées. De nouvelles simulations peuvent ainsi s'ajouter dans le silver depuis le bronze sans retraiter l'ensemble du bronze.

```bash
python src/bronze_to_silver.py
```

#### Étape 3 : Calcul des Tables Analytiques (Silver → Gold)

Génère les tables prêtes pour l'analyse BI et la dataviz.

```bash
python src/silver_to_gold.py
```

---

## 🏗️ Architecture des Données

Le projet s'appuie sur le pattern d'architecture **Medallion** (Bronze → Silver → Gold) afin de garantir la traçabilité, la propreté et la valorisation des données de simulation :

1. **Couche Bronze (Données Brutes) :** Stockage des fichiers de simulation initiaux au format Parquet issus de la génération directe des tournois. Chaque fichier contient l'intégralité des logs d'une session.
2. **Couche Silver (Nettoyage & Enrichissement) :** Centralisation incrémentale de toutes les sessions au sein d'un registre global unifié. Les choix textuels sont binarisés (`COOPERER` → 1, `TRAHIR` → 0) et des indicateurs de contexte (calcul du coup précédent via fenêtrage analytique `LAG`) sont calculés de manière transparente.
3. **Couche Gold (Agrégation Décisionnelle) :** Tables d'agrégations métiers optimisées pour l'analyse décisionnelle et la dataviz (génération de heatmaps, courbes de confiance temporelles et calculs d'équilibres de Nash).

---

## ⚙️ Naming Convention (Couche Bronze)

Les fichiers générés dans la couche `data/bronze/` suivent une convention de nommage stricte afin de garantir la traçabilité des simulations sans risque d'écrasement (idempotence du pipeline) :

```text
simulation_tournoi_[MODELE_LLM]_[NB_TOURS]_tours_[DUREE_MEMOIRE]_memoire_YYYYMMDD_HHMMSS_.parquet
```

### Explication des composants :

* **`[MODELE_LLM]`** : Le nom du modèle d'IA utilisé pour orchestrer les agents (ex: `gpt4o`, `llama3`).
* **`[NB_TOURS]`** : Le nombre de tours par partie (ex: `5`, `20`).
* **`[DUREE_MEMOIRE]`** : Les X derniers tours dont l'IA se souvient pour prendre sa décision (ex: `5`, `20`). Elle aura accès aux décision de ces tours mais aussi à ses justifications, secrètes et publiques, ainsi qu'aux justifications publiques de son adversaire.
* **`YYYYMMDD_HHMMSS`** : Horodatage précis du lancement du tournoi (Année, Mois, Jour _ Heure, Minute, Seconde). Il sert d'identifiant temporel unique.

*Exemple de fichier réel :* `simulation_tournoi_llama3_8b_1_tours_1_memoire_20260528_150833.parquet`

---

## 📊 Schémas des Tables (Data Lineage)

### 1. Couche Bronze (`bronze_simulations_brutes`)

| Nom de la colonne | Type | Description | Exemple de Valeurs |
| --- | --- | --- | --- |
| `tour` | `INTEGER` | Index du tour actuel au sein de la confrontation | `1`, `2`, `3`... |
| `joueur_1_profil` | `VARCHAR` | Nom du profil / stratégie du premier joueur | `TitForTat` |
| `joueur_2_profil` | `VARCHAR` | Nom du profil / stratégie du second joueur | `AlwaysDefect` |
| `joueur_1_choix` | `VARCHAR` | Action textuelle brute choisie par l'agent 1 | `COOPERER` ou `TRAHIR` |
| `joueur_2_choix` | `VARCHAR` | Action textuelle brute choisie par l'agent 2 | `COOPERER` ou `TRAHIR` |
| `joueur_1_gain` | `INTEGER` | Score obtenus par l'agent 1 sur ce tour | `0`, `1`, `3` ou `5` |
| `joueur_2_gain` | `INTEGER` | Score d'utilité obtenus par l'agent 2 sur ce tour | `0`, `1`, `3` ou `5` |
| `joueur_1_score_cumule` | `INTEGER` | Score cumulé sur la partie | `22` |
| `joueur_2_score_cumule` | `INTEGER` | Score cumulé sur la partie | `22` |
| `joueur_1_justification_prive` | `VARCHAR` | Comment l'IA s'explique son cheminement de pensée | `"Je vais tenter d'être d'abord coopératif..."` |
| `joueur_2_justification_prive` | `VARCHAR` | Comment l'IA s'explique son cheminement de pensée | `"Je ne peux pas lui faire confiance, je vais tout le temps trahir c'est plus sûr"` |
| `joueur_1_justification_public` | `VARCHAR` | Comment l'IA explique sa décision a son adversaire et tente peut-être de le manipuler | `"Nous avons plus a gagner à jouer ensembles pour maximiser nos gains."` |
| `joueur_2_justification_public` | `VARCHAR` | Comment l'IA explique sa décision a son adversaire et tente peut-être de le manipuler | `"Je trahis car je ne te fais pas confiance, si tu coopère encore je changerais ma décision plus tard."` |

---

### 2. Couche Silver (`silver_registre_global`)

Cette table unifie l'ensemble des sessions historiques, binarise les indicateurs pour optimiser les performances de calcul et enrichit les lignes avec des données de contexte.

Note : Si la plupart des paramètres de parties, modifiables dans le .env, seront retranscrit dans de nouvelles colonnes, ce n'est pas le cas de la matrice de gains (qui peut cependant être inféré à partir des gains).

| Nom de la colonne | Type | Description | Exemple / Valeurs |
| --- | --- | --- | --- |
| `tour` | `INTEGER` | Index du tour actuel au sein de la confrontation | `1`, `2`, `3`... |
| `joueur_1_profil` | `VARCHAR` | Nom du profil / stratégie du premier joueur | `TitForTat` |
| `joueur_2_profil` | `VARCHAR` | Nom du profil / stratégie du second joueur | `AlwaysDefect` |
| `joueur_1_choix` | `VARCHAR` |  **Binarisation** : `1` si COOPERER, `0` si TRAHIR | `CASE WHEN choix_agent_1 = 'COOPERER' THEN 1...` |
| `joueur_2_choix` | `VARCHAR` |  **Binarisation** : `1` si COOPERER, `0` si TRAHIR | `CASE WHEN choix_agent_1 = 'COOPERER' THEN 1...` |
| `joueur_1_gain` | `INTEGER` | Score obtenus par l'agent 1 sur ce tour | `0`, `1`, `3` ou `5` |
| `joueur_2_gain` | `INTEGER` | Score d'utilité obtenus par l'agent 2 sur ce tour | `0`, `1`, `3` ou `5` |
| `joueur_1_score_cumule` | `INTEGER` | Score cumulé sur la partie | `22` |
| `joueur_2_score_cumule` | `INTEGER` | Score cumulé sur la partie | `22` |
| `joueur_1_justification_prive` | `VARCHAR` | Comment l'IA s'explique son cheminement de pensée | `"Je vais tenter d'être d'abord coopératif..."` |
| `joueur_2_justification_prive` | `VARCHAR` | Comment l'IA s'explique son cheminement de pensée | `"Je ne peux pas lui faire confiance, je vais tout le temps trahir c'est plus sûr"` |
| `joueur_1_justification_public` | `VARCHAR` | Comment l'IA explique sa décision a son adversaire et tente peut-être de le manipuler | `"Nous avons plus a gagner à jouer ensembles pour maximiser nos gains."` |
| `joueur_2_justification_public` | `VARCHAR` | Comment l'IA explique sa décision a son adversaire et tente peut-être de le manipuler | `"Je trahis car je ne te fais pas confiance, si tu coopère encore je changerais ma décision plus tard."` |
| `meta_modele_llm` | `VARCHAR` | Nom du modèle de LLM utilisé. | `llama3:8b` |
| `meta_nb_tours` | `INTEGER` | Nombre de tours par partie. | `5` |
| `meta_taille_memoire` | `INTEGER` | Nombre de tours dont l'IA se souvient au moment de prendre sa décision. | `5` |
| `meta_horodatage` | `VARCHAR` | Date de la fin de la simulation du tournois au format YYYYMMDD_HHMMSS. | `20260528_172213` |
| `ecart_score_j1_vs_j2` | `INTEGER` | Ecart des scores cumulés à ce tour (J1-J2). | `13`, `-6`, ... |
| `joueur_1_choix_precedent` | `INTEGER` | Action jouée par l'agent 1 au tour précédent | `0` ou `1` |
| `joueur_2_choix_precedent` | `INTEGER` | Action jouée par l'agent 1 au tour précédent | `0` ou `1` |

### 📂 Arborescence du Projet

Conformément aux standards de l'ingénierie de données moderne (typage *dbt*), **la logique de transformation SQL est entièrement découplée de l'infrastructure d'orchestration Python**.

```text
RENDU_ETL_ELT/
├── data/                           <-- Ignoré par Git (Sauf structure racine)
│   ├── bronze/                     <-- Sorties brutes des simulations (.parquet)
│   ├── silver/                     <-- Registre global centralisé (.parquet)
│   └── gold/                       <-- Vues analytiques décisionnelles (.parquet)
├── src/
│   ├── queries/                    <-- Entrepôt des requêtes SQL pures
│   │   ├── silver/
│   │   │   └── clean_and_enrich_bronze.sql
│   │   └── gold/
│   │       ├── benchmark_runs.sql
│   │       ├── evolution_temporelle.sql
│   │       └── matrice_confrontations.sql
│   ├── generation_bronze.py        <-- Moteur de simulation des tournois
│   ├── bronze_to_silver.py         <-- Orchestrateur d'intégration Silver DuckDB
│   └── silver_to_gold.py           <-- Moteur d'agrégation Gold DuckDB
├── .env                            <-- Configuration des variables d'environnement
├── .env.example                    <-- Modèle de configuration partagé
├── prompts_regles_et_profils.json  <-- Configuration des profils de jeu
└── requirements.txt                <-- Dépendances strictes du projet
```

---

## ⚡ Choix Technologiques & Passage à l'Échelle

Pour anticiper une génération massive de données (simulations répétées sur des milliers de tours), **Pandas a été entièrement écarté des phases de transformation au profit de DuckDB**.

* **Optimisation RAM (Out-of-Core) :** DuckDB s'appuie sur un moteur d'exécution vectorisé. Au lieu de charger l'intégralité des fichiers Parquet en mémoire vive (comme le ferait Pandas), DuckDB traite les données par blocs (vecteurs) directement depuis le disque. Ce pipeline de traitement par lots (Batch) peut ainsi fusionner et transformer des volumes de plusieurs dizaines de gigaoctets sans saturer la RAM de la machine.
* **Modularité SQL :** L'utilisation de fichiers de requêtes externes (`.sql`) permet de maintenir une logique métier lisible, versionnable et isolée des scripts d'orchestration Python.

---

## 📊 Objectifs de l'Analyse Exploratoire (Couche Gold)

La couche **Gold** met à disposition d'un Data Analyst trois tables pour des outils de restitution (tels que Streamlit, PowerBI, Tableau) :

1. **`gold_matrice_confrontations.parquet` :** Calcule les rendements moyens croisés de chaque profil contre chaque profil. Idéal pour afficher la **Heatmap des gains** et identifier visuellement les **Équilibres de Nash**.
2. **`gold_evolution_temporelle.parquet` :** Agrège les taux de coopération et l'indice de propension à la vengeance tour par tour. Permet de mettre en évidence des **comportements émergents** (effondrement de la coopération en fin de partie).
3. **`gold_benchmark_runs.parquet` :** Permet de comparer dynamiquement l'impact des variations d'hyperparamètres (taille de la mémoire des agents, nombre de tours) sur l'efficacité globale des profils (Conformément au **Bonus** d'analyse multi-runs).