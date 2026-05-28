# 🕵️‍♂️ Simulation du Dilemme du Prisonnier Itératif — Pipeline ETL/ELT Medallion

Ce projet implémente une architecture de données complète et industrialisée pour simuler, transformer et analyser des tournois du **Dilemme du Prisonnier Itératif** menés par des agents dotés de stratégies comportementales spécifiques ou propulsés par des modèles d'Intelligence Artificielle (LLM).

Inspiré de l'expérience historique de Robert Axelrod (1981), ce pipeline a été modernisé pour répondre à des problématiques de **Big Data** et de reproductibilité analytique en utilisant une architecture en cascade (Medallion) couplée à la puissance de calcul "Out-of-Core" de **DuckDB**.

---

## 🏗️ Architecture des Données

Le projet s'appuie sur le pattern d'architecture **Medallion** (Bronze → Silver → Gold) afin de garantir la traçabilité, la propreté et la valorisation des données de simulation :

1. **Couche Bronze (Données Brutes) :** Stockage des fichiers de simulation initiaux au format Parquet issus de la génération directe des tournois. Chaque fichier contient l'intégralité des logs d'une session.
2. **Couche Silver (Nettoyage & Enrichissement) :** Centralisation incrémentale de toutes les sessions au sein d'un registre global unifié. Les choix textuels sont binarisés (`COOPERER` → 1, `TRAHIR` → 0) et des indicateurs de contexte (calcul du coup précédent via fenêtrage analytique `LAG`) sont calculés de manière transparente.
3. **Couche Gold (Agrégation Décisionnelle) :** Tables d'agrégations métiers optimisées pour l'analyse décisionnelle et la dataviz (génération de heatmaps, courbes de confiance temporelles et calculs d'équilibres de Nash).

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

* **Optimisation RAM (Out-of-Core) :** DuckDB traite les fichiers Parquet en flux continu (streaming) directement depuis le disque dur. Le pipeline peut ainsi traiter des fichiers de plusieurs dizaines de gigaoctets sans saturation de la mémoire vive de la machine.
* **Modularité SQL :** L'utilisation de fichiers de requêtes externes (`.sql`) permet de maintenir une logique métier lisible, versionnable et isolée des scripts d'orchestration Python.

---

## 🚀 Installation et Utilisation

### 1. Prérequis

Assure-toi de disposer de Python 3.10+ installé sur ta machine.

### 2. Cloner le projet et installer les dépendances

```bash
git clone <url-de-ton-depot-github>
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

#### Étape 1 : Génération des simulations (Extraction → Bronze)

Génère les données de tournoi brutes à partir des profils configurés.

```bash
python src/generation_bronze.py

```

#### Étape 2 : Nettoyage et Centralisation (Bronze → Silver)

Exécute la logique SQL de traitement incrémental via DuckDB pour alimenter le registre global sans retraiter les sessions déjà intégrées.

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

La couche **Gold** met à disposition d'un Data Analyst trois tables hautement valorisables pour des outils de restitution (Streamlit, PowerBI, Tableau) :

1. **`gold_matrice_confrontations.parquet` :** Calcule les rendements moyens croisés de chaque profil contre chaque profil. Idéal pour afficher la **Heatmap des gains** et identifier visuellement les **Équilibres de Nash**.
2. **`gold_evolution_temporelle.parquet` :** Agrège les taux de coopération et l'indice de propension à la vengeance tour par tour. Permet de mettre en évidence des **comportements émergents** (effondrement de la coopération en fin de partie).
3. **`gold_benchmark_runs.parquet` :** Permet de comparer dynamiquement l'impact des variations d'hyperparamètres (taille de la mémoire des agents, nombre de tours) sur l'efficacité globale des profils (Conformément au **Bonus** d'analyse multi-runs).