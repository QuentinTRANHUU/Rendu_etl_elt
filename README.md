# 🕵️‍♂️ Simulation du Dilemme du Prisonnier Itératif — Pipeline ETL/ELT Medallion

Ce projet implémente une architecture de données complète et industrialisée pour simuler, transformer et analyser des tournois du **Dilemme du Prisonnier Itératif** menés par des agents dotés de stratégies comportementales spécifiques ou propulsés par des modèles d'Intelligence Artificielle (LLM).

Inspiré de l'expérience historique de Robert Axelrod (1981), ce pipeline a été modernisé pour répondre à des problématiques de **Big Data** et de reproductibilité analytique en utilisant une architecture en cascade (Medallion) couplée à la puissance de calcul "Out-of-Core" de **DuckDB**.

---

## 🏗️ Architecture des Données

Le projet s'appuie sur le pattern d'architecture **Medallion** (Bronze → Silver → Gold) afin de garantir la traçabilité, la propreté et la valorisation des données de simulation :

1. **Couche Bronze (Données Brutes) :** Stockage des fichiers de simulation initiaux au format Parquet issus de la génération directe des tournois. Chaque fichier contient l'intégralité des logs d'une session.
2. **Couche Silver (Nettoyage & Enrichissement) :** Centralisation incrémentale de toutes les sessions au sein d'un registre global unifié. Les choix textuels sont binarisés (`COOPERER` → 1, `TRAHIR` → 0) et des indicateurs de contexte (calcul du coup précédent via fenêtrage analytique `LAG`) sont calculés de manière transparente.
3. **Couche Gold (Agrégation Décisionnelle) :** Tables d'agrégations métiers optimisées pour l'analyse décisionnelle et la dataviz (génération de heatmaps, courbes de confiance temporelles et calculs d'équilibres de Nash).

---

## Naming Convention (Couche Bronze)

Les fichiers générés dans la couche `data/bronze/` suivent une convention de nommage stricte afin de garantir la traçabilité des simulations sans risque d'écrasement (idempotence du pipeline) :

```text
simulation_YYYYMMDD_HHMMSS_[MODELE_LLM]_[PARAM_MEMOIRE].parquet

```

### Explication des composants :

* **`YYYYMMDD_HHMMSS`** : Horodatage précis du lancement du tournoi (Année, Mois, Jour _ Heure, Minute, Seconde). Il sert d'identifiant temporel unique.
* **`[MODELE_LLM]`** : Le nom du modèle d'IA utilisé pour orchestrer les agents (ex: `gpt4o`, `llama3`, `local`), ou `metier` si la simulation utilise uniquement des stratégies codées en dur.
* **`[PARAM_MEMOIRE]`** : La taille de la mémoire (nombre de coups précédents retenus) configurée pour ce run (ex: `mem_1`, `mem_5`).

*Exemple de fichier réel :* `simulation_20260528_143022_llama3_mem_3.parquet`

---

## 📊 Schémas des Tables (Data Lineage)

Le passage de la couche Bronze à la couche Silver applique des transformations structurelles et analytiques majeures. Voici la description des schémas cibles :

### 1. Couche Bronze (`bronze_simulations_brutes`)

Cette table contient les logs bruts "bruts de fonderie" issus directement du moteur de jeu.

| Nom de la colonne | Type | Description | Exemple / Valeurs |
| --- | --- | --- | --- |
| `id_session` | `VARCHAR` | Identifiant unique (UUID) de la session de tournoi | `f81d4fae-7dec...` |
| `num_tour` | `INTEGER` | Index du tour actuel au sein de la confrontation | `1`, `2`, `3`... |
| `agent_1` | `VARCHAR` | Nom du profil / stratégie du premier joueur | `TitForTat` |
| `agent_2` | `VARCHAR` | Nom du profil / stratégie du second joueur | `AlwaysDefect` |
| `choix_agent_1` | `VARCHAR` | Action textuelle brute choisie par l'agent 1 | `COOPERER` ou `TRAHIR` |
| `choix_agent_2` | `VARCHAR` | Action textuelle brute choisie par l'agent 2 | `COOPERER` ou `TRAHIR` |
| `gain_agent_1` | `INTEGER` | Points d'utilité obtenus par l'agent 1 sur ce tour | `0`, `1`, `3` ou `5` |
| `gain_agent_2` | `INTEGER` | Points d'utilité obtenus par l'agent 2 sur ce tour | `0`, `1`, `3` ou `5` |
| `meta_horodatage` | `TIMESTAMP` | Date et heure d'ingestion dans la couche Bronze | `2026-05-28 14:30:22` |

---

### 2. Couche Silver (`silver_registre_global`)

Cette table unifie l'ensemble des sessions historiques, binarise les indicateurs pour optimiser les performances de calcul et enrichit les lignes avec des données de contexte (fenêtrage).

| Nom de la colonne | Type | Description | Transformation / Origine |
| --- | --- | --- | --- |
| `id_session` | `VARCHAR` | Identifiant unique de la session | Copie conforme Bronze |
| `num_tour` | `INTEGER` | Index du tour | Copie conforme Bronze |
| `agent_1` | `VARCHAR` | Stratégie de l'agent 1 | Idem |
| `agent_2` | `VARCHAR` | Stratégie de l'agent 2 | Idem |
| `cooperation_agent_1` | `UTINYINT` | **Binarisation** : `1` si COOPERER, `0` si TRAHIR | `CASE WHEN choix_agent_1 = 'COOPERER' THEN 1...` |
| `cooperation_agent_2` | `UTINYINT` | **Binarisation** : `1` si COOPERER, `0` si TRAHIR | `CASE WHEN choix_agent_2 = 'COOPERER' THEN 1...` |
| `gain_agent_1` | `INTEGER` | Points de l'agent 1 | Copie conforme Bronze |
| `gain_agent_2` | `INTEGER` | Points de l'agent 2 | Copie conforme Bronze |
| `action_prec_agent_1` | `VARCHAR` | Action jouée par l'agent 1 au tour précédent | **Calculé via** `LAG(choix_agent_1) OVER (...)` |
| `action_prec_agent_2` | `VARCHAR` | Action jouée par l'agent 2 au tour précédent | **Calculé via** `LAG(choix_agent_2) OVER (...)` |
| `meta_insertion_silver` | `TIMESTAMP` | Date et heure de traitement par le script Silver | `CURRENT_TIMESTAMP` |

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

## 🚀 Installation et Utilisation

### 1. Prérequis

Assure-toi de disposer de Python 3.10+ installé sur ta machine.

### 2. Cloner le projet et installer les dépendances

```bash
git clone git@github.com:QuentinTRANHUU/Rendu_etl_elt.git
cd RENDU_ETL_ELT
pip install -r requirements.txt

```

### 3. Configurer l'environnement

Copie le fichier d'exemple et ajuste les variables si nécessaire (par défaut, les données pointent vers le sous-dossier `data/` du projet) :

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

## 📊 Objectifs de l'Analyse Exploratoire (Couche Gold)

La couche **Gold** met à disposition d'un Data Analyst trois tables hautement valorisables pour des outils de restitution (tels que Streamlit, PowerBI, Tableau) :

1. **`gold_matrice_confrontations.parquet` :** Calcule les rendements moyens croisés de chaque profil contre chaque profil. Idéal pour afficher la **Heatmap des gains** et identifier visuellement les **Équilibres de Nash**.
2. **`gold_evolution_temporelle.parquet` :** Agrège les taux de coopération et l'indice de propension à la vengeance tour par tour. Permet de mettre en évidence des **comportements émergents** (effondrement de la coopération en fin de partie).
3. **`gold_benchmark_runs.parquet` :** Permet de comparer dynamiquement l'impact des variations d'hyperparamètres (taille de la mémoire des agents, nombre de tours) sur l'efficacité globale des profils (Conformément au **Bonus** d'analyse multi-runs).