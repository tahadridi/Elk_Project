# Security Monitoring — Laboratoire ELK

Pipeline de collecte, de normalisation et de visualisation de logs de sécurité
(CSV + JSON) basé sur la stack Elastic : **Elasticsearch, Logstash, Kibana**.
MongoDB et Redis sont préparés pour les fonctionnalités applicatives des
prochains sprints.

Le Sprint 2 est implémenté et vérifié : infrastructure Docker Compose,
ingestion, normalisation ECS, gestion des erreurs et dashboard Kibana.

## Statut du projet

| Fonctionnalité | État |
| --- | --- |
| Stack ELK reproductible avec Docker Compose | Implémenté |
| Ingestion CSV + JSON | Implémenté |
| Normalisation ECS | Implémenté |
| Séparation des lignes invalides (`logs-parse-errors-*`) | Implémenté |
| Dashboard Kibana `Security Overview` | Implémenté |
| Vérification automatique de l'ingestion | Implémenté |
| Persistance MongoDB | Prévu |
| Redis : tentatives de connexion / blocage d'IP | Prévu |
| API applicative | Prévu |
| Authentification, rôles et frontend | Prévu |
| Tests d'intégration et captures finales | Prévu |

Les fonctionnalités marquées **Prévu** ne sont pas encore disponibles.

## Architecture

```text
data/input/*.csv  ──> csv-ingest  ──┐
                                    ├──> normalize ──> logs-security-YYYY.MM.dd
data/input/*.json ──> json-ingest ──┘              └──> logs-parse-errors-YYYY.MM
```

- **Elasticsearch** : stockage et agrégations (`logs-security-*`,
  `logs-parse-errors-*`).
- **Logstash** : trois pipelines (`csv-ingest`, `json-ingest`, `normalize`)
  déclarés dans `infra/logstash/pipelines.yml`.
- **Kibana** : data view `Security Logs` et dashboard `Security Overview`.
- **MongoDB** et **Redis** : démarrés pour les prochains sprints, pas encore
  utilisés par le pipeline.

## Prérequis

- Docker 24+ et Docker Compose v2 (`docker compose`).
- Python 3.10+ (le générateur et le script de vérification utilisent la
  bibliothèque standard ; `Faker` est installé dans le venv local).
- `make`, `curl`.
- Environ 4 Go de RAM disponibles.

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

Démarrage manuel :

```bash
make up
make wait
make init
make kibana
make gen
make verify
```

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

## Accès

| Service | URL / port |
| --- | --- |
| Kibana | <http://localhost:5601> |
| Elasticsearch | <http://localhost:9200> |
| API Logstash | <http://localhost:9600> |
| MongoDB | `127.0.0.1:27018` |
| Redis | `127.0.0.1:6379` |

## Résultat attendu

Après `make demo` avec les paramètres par défaut :

- **4 000** documents dans `logs-security-*` (2 000 CSV + 2 000 JSON).
- **5** documents dans `logs-parse-errors-*` (IP/date invalides et JSON
  corrompu).
- `event.dataset` contient `csv` et `json`.
- `log.level` contient `INFO`, `WARNING`, `ERROR` et `CRITICAL`.
- Les IP publiques sont enrichies par GeoIP.
- Kibana : **Dashboards → Security Overview**.
- `make verify` se termine par :
  `RESULT: OK - Sprint 2 ingestion verified`.

## Structure du dépôt

```text
.
├── docker-compose.yaml
├── Makefile
├── .env.example
├── data/input/          # logs générés (git-ignoré)
├── infra/
│   ├── elasticsearch/   # templates + exemple de document
│   ├── kibana/exports/  # dashboard Security Overview
│   └── logstash/        # pipelines CSV, JSON, normalize
└── scripts/             # génération, init, dashboard, vérification
```

Le dossier `docs/` (architecture, ingestion, rapports de sprint) reste local et
n'est pas versionné.

## Dépannage

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `make up` échoue sur `.env` | Fichier `.env` absent | `cp .env.example .env` puis éditer les mots de passe. |
| Aucun document après `make gen` | Pipeline en erreur ou sincedb obsolète | `make logs`, puis `make reset` pour rejouer depuis zéro. |
| `composable template ... would cause data streams ...` | Template `logs-parse-errors` absent | `make init` ou `make reset`. |
| `json-ingest in=0` | Fichier ignoré à cause du sincedb | `make reset` puis relancer la démo. |
| Dashboard absent dans Kibana | Import non exécuté | `make kibana`. |
| Port déjà utilisé | Service local sur le même port | Modifier la section `ports` de `docker-compose.yaml`. |
| Kibana lent au premier démarrage | Initialisation de Kibana | Attendre `make wait` ou consulter `make ps`. |

Commandes de diagnostic :

```bash
docker compose ps
docker compose logs --tail=100 logstash
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

## Documentation

Les documents détaillés (architecture, ingestion, rapport de sprint, PDF) sont
conservés localement dans `docs/` et ne sont pas versionnés. Le README reste la
référence pour démarrer et utiliser le projet.

## Suivi Jira

La mise à jour des tickets **SCRUM-66 à SCRUM-71** reste manuelle : passer les
tickets au statut Done après validation, en joignant le rapport et les preuves
d'exécution.
