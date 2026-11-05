# Security Monitoring — Laboratoire ELK

Pipeline de collecte, de normalisation et de visualisation de logs de sécurité
(CSV + JSON) basé sur la stack Elastic : **Elasticsearch, Logstash, Kibana**,
avec MongoDB et Redis préparés pour les prochains sprints.

Le **Sprint 2** couvre l'infrastructure, l'ingestion, la normalisation, la
vérification de bout en bout et le tableau de bord Kibana.

## Sommaire

- [Objectif du Sprint 2](#objectif-du-sprint-2)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Démarrage rapide](#démarrage-rapide)
- [Commandes](#commandes)
- [Résultat attendu](#résultat-attendu)
- [Structure du dépôt](#structure-du-dépôt)
- [Corrections apportées au Sprint 2](#corrections-apportées-au-sprint-2)
- [Dépannage](#dépannage)
- [Sécurité](#sécurité)
- [État du sprint et suite](#état-du-sprint-et-suite)

## Objectif du Sprint 2

- Démarrer une stack ELK reproductible avec Docker Compose.
- Ingérer deux formats de logs : CSV et NDJSON.
- Normaliser les documents au format ECS (`@timestamp`, `log.level`,
  `event.dataset`, `source.ip`, `user.name`, etc.).
- Séparer les lignes invalides dans un index dédié `logs-parse-errors-*`.
- Vérifier automatiquement l'ingestion avec un script et un jeu de logs
  reproductible (seed fixe).
- Fournir un tableau de bord Kibana importable/ex portable.

## Architecture

```
data/input/*.csv  ──> csv-ingest  ──┐
                                    ├──> normalize ──> logs-security-YYYY.MM.dd
data/input/*.json ──> json-ingest ──┘              └──> logs-parse-errors-YYYY.MM
```

- **Elasticsearch** : stockage et agrégations (`logs-security-*`,
  `logs-parse-errors-*`).
- **Logstash** : trois pipelines (`csv-ingest`, `json-ingest`, `normalize`)
  déclarés dans `infra/logstash/pipelines.yml`.
- **Kibana** : data view `Security Logs` et dashboard `Security Overview`.
- **MongoDB** et **Redis** : démarrés pour les sprints suivants (persistance
  applicative, tentatives de connexion, blocage d'IP).

La documentation détaillée (architecture, ingestion, rapports) est conservée
localement et n'est pas versionnée.

## Prérequis

- Docker 24+ et Docker Compose v2 (`docker compose`).
- Python 3.10+ (le générateur et le script de vérification utilisent la
  bibliothèque standard ; `Faker` est installé dans le venv local).
- `make`, `curl`.
- Environ 4 Go de RAM disponibles (Elasticsearch 1 Go, Logstash 512 Mo,
  Kibana).

## Démarrage rapide

```bash
make setup
cp .env.example .env
# Éditer .env (mots de passe MongoDB / Redis)
make demo
```

`make demo` démarre la stack, attend les services, installe les templates,
importe le dashboard Kibana, génère les logs, attend l'ingestion puis lance la
vérification.

Démarrage manuel, étape par étape :

```bash
make setup      # crée .venv et installe Faker
cp .env.example .env
make up
make wait
make init       # optionnel : les templates sont aussi installés par elastic-init
make kibana
make gen
make verify
```

Accès :

| Service | URL / port |
| --- | --- |
| Kibana | <http://localhost:5601> |
| Elasticsearch | <http://localhost:9200> |
| API Logstash | <http://localhost:9600> |
| MongoDB | `127.0.0.1:27018` |
| Redis | `127.0.0.1:6379` |

## Commandes

| Commande | Description |
| --- | --- |
| `make setup` | Crée `.venv` et installe `scripts/requirements.txt`. |
| `make up` | Démarre la stack en arrière-plan. |
| `make wait` | Attend Elasticsearch, Logstash et Kibana. |
| `make init` | Installe les templates d'index Elasticsearch. |
| `make kibana` | Importe la data view et le dashboard depuis le NDJSON. |
| `make dashboard` | Reconstruit le dashboard Kibana et réexporte le NDJSON. |
| `make gen` | Génère les logs CSV + JSON dans `data/input/`. |
| `make verify` | Vérifie l'ingestion de bout en bout. |
| `make restart-logstash` | Recharge la configuration des pipelines. |
| `make logs` | Suit les logs des conteneurs. |
| `make ps` | Affiche l'état des conteneurs. |
| `make reset` | Arrête la stack, supprime les volumes et les logs générés. |
| `make demo` | Enchaîne `up`, `wait`, `init`, `kibana`, `gen`, puis `verify`. |

Variables utiles :

```bash
make gen GEN_ARGS="--count 5000 --days 7 --with-errors --seed 7"
make verify ES_URL=http://localhost:9200
```

## Résultat attendu

Avec la commande par défaut (`--count 2000 --days 3 --with-errors --seed 42`) :

- **4 000** documents dans `logs-security-*` (2 000 CSV + 2 000 JSON).
- **5** documents dans `logs-parse-errors-*` :
  - 2 lignes avec une IP invalide (une CSV, une JSON) ;
  - 2 lignes avec une date invalide (une CSV, une JSON) ;
  - 1 ligne JSON volontairement corrompue.
- `event.dataset` contient `csv` et `json`.
- `log.level` contient `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `source.ip` est renseigné et les IP publiques sont enrichies par GeoIP.

Sortie type de `make verify` :

```text
[PASS] Elasticsearch reachable -> green
[PASS] Index template logs-security installed
[PASS] logs-security-* index has documents -> 4000 docs
[PASS] logs-parse-errors-* received invalid rows -> 5 docs
[PASS] log.level populated (bug fixed) -> INFO,WARNING,ERROR,CRITICAL
[PASS] event.dataset populated -> csv,json
[PASS] source.ip populated
[PASS] Sample doc has @timestamp
[PASS] Sample doc has log.level -> ERROR
[PASS] Sample doc has source.ip -> 74.61.37.32

RESULT: OK - Sprint 2 ingestion verified
```

Dans Kibana : **Dashboards → Security Overview**. Les panneaux affichent le
volume total, les erreurs d'ingestion, la répartition CSV/JSON, les événements
par niveau dans le temps, les IP sources principales et les échecs de connexion
par utilisateur.

## Structure du dépôt

```text
.
├── docker-compose.yaml
├── Makefile
├── .env.example
├── data/input/                 # logs générés (git-ignoré, .gitkeep conservé)
├── infra/
│   ├── elasticsearch/
│   │   ├── logs-security-template.json
│   │   ├── logs-parse-errors-template.json
│   │   └── logs-security.json  # exemple de document normalisé
│   ├── kibana/exports/
│   │   └── security-overview.ndjson
│   └── logstash/
│       ├── pipelines.yml
│       └── pipeline/
│           ├── csv.conf
│           ├── json.conf
│           └── normalize.conf
└── scripts/
    ├── generate_logs.py
    ├── init_elasticsearch.sh
    ├── init_kibana.sh
    ├── build_kibana_dashboard.py
    ├── verify_ingestion.py
    └── requirements.txt
```

Le dossier `docs/` (architecture, ingestion, rapports de sprint) reste local
et n'est pas versionné.

## Corrections apportées au Sprint 2

- Suppression de `tag_on_failure` sur le filtre `csv` (option non supportée,
  qui empêchait le pipeline de démarrer).
- Conservation du champ `level` avant le renommage vers `log.level`.
- Ajout de `event.dataset` (`csv` ou `json`) pour distinguer les deux sources.
- GeoIP limité aux IP publiques ; les IP privées ne déclenchent plus d'erreur.
- Template dédié `logs-parse-errors` pour éviter la collision avec le template
  intégré `logs-*` d'Elasticsearch (data streams).
- Passage des entrées `file` de `mode => "read"` à `tail` +
  `start_position => "beginning"` pour éviter qu'un fichier créé pendant le
  démarrage de Logstash soit ignoré.
- Service `elastic-init` qui installe les templates **avant** le démarrage de
  Logstash (`depends_on: service_completed_successfully`).
- Dashboard Kibana versionné et réimportable (`make dashboard` / `make kibana`).

## Dépannage

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `make up` échoue sur `.env` | Fichier `.env` absent | `cp .env.example .env` puis éditer les mots de passe. |
| Aucun document après `make gen` | Pipeline en erreur ou sincedb obsolète | `make logs`, puis `make reset` pour rejouer depuis zéro. |
| `Unknown setting 'tag_on_failure' for csv` | Ancienne configuration du filtre CSV | Vérifier `infra/logstash/pipeline/csv.conf` puis `make restart-logstash`. |
| `composable template ... would cause data streams ...` | Template `logs-parse-errors` absent | `make init` ou `make reset`. |
| `json-ingest in=0` | Fichier ignoré à cause d'un sincedb / d'un démarrage trop tôt | `make reset` (supprime les volumes) puis relancer la démo. |
| Dashboard absent dans Kibana | Import non exécuté | `make kibana`. |
| Champ `source.geo` absent pour une IP | IP privée ou réservée | Comportement attendu : GeoIP n'est appliqué qu'aux IP publiques. |
| Port déjà utilisé | Service local sur le même port | Modifier la section `ports` de `docker-compose.yaml`. MongoDB est exposé sur `27018` pour éviter le `27017` local. |
| Kibana lent au premier démarrage | Initialisation de Kibana | Attendre `make wait` ou consulter `make ps`. |

Commandes de diagnostic :

```bash
docker compose ps
docker compose logs --tail=100 logstash
curl -s http://localhost:9200/_cat/indices/logs-*?v
curl -s http://localhost:9200/logs-security-*/_count
curl -s http://localhost:9200/logs-parse-errors-*/_count
curl -s http://localhost:9200/_data_stream
make verify
```

## Sécurité

- Le fichier `.env` est **git-ignoré** et ne doit jamais être commité.
- La sécurité Elasticsearch (`xpack.security.enabled=false`) et l'absence de
  TLS sont adaptées à un laboratoire local uniquement, pas à la production.
- Les identifiants Jira ou tout autre secret ne doivent pas être stockés dans
  le dépôt. Le jeton Jira utilisé pendant le projet doit être révoqué/rotaté.
- Les logs générés sont synthétiques (Faker) et ne contiennent pas de données
  personnelles réelles.

## État du sprint et suite

Le périmètre technique du Sprint 2 est implémenté et vérifié. La mise à jour
des tickets Jira (**SCRUM-66 à SCRUM-71**) reste manuelle : passer les tickets
au statut Done après validation, en joignant le rapport et les preuves
d'exécution.

Prochaines étapes (Sprint 4) :

- API applicative (selon la stack choisie) et persistance MongoDB.
- Redis pour les tentatives de connexion et le blocage temporaire d'IP.
- Authentification, rôles et premiers écrans frontend.
- Tests d'intégration et captures d'écran finales.
