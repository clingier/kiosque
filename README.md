# Kiosque

**Transparence médiatique en France.** Kiosque agrège chaque matin les titres de ~62 médias français, regroupe les articles par sujet, et révèle la concentration de la couverture par groupe propriétaire.

Qui couvre quoi — et qui ne couvre rien.

---

## Pourquoi

Six groupes industriels contrôlent la majorité des médias français. Le même événement peut faire la une de 15 titres appartenant au même propriétaire, pendant qu'un autre sujet n'est couvert que par un indépendant. Kiosque rend cette réalité visible, chaque jour, sans éditorialiser.

Le projet ne republie aucun contenu — il agrège des titres et des liens, mesure la diversité de la couverture, et signale les angles morts.

## Comment ça marche

Chaque matin à 06h00 UTC :

1. **Collecte** — Une Azure Function parcourt les flux RSS, sitemaps et fallbacks Google News des 62 sources.
2. **Normalisation** — Les articles bruts sont nettoyés, dédupliqués, et structurés dans un schéma commun.
3. **Clustering** — Un pipeline NLP regroupe les articles qui traitent du même sujet en *stories*.
4. **Ownership** — Chaque article est rattaché à son groupe propriétaire (données Acrimed).
5. **Métriques** — Indice HHI de concentration, détection des angles morts, KPI du jour.
6. **Publication** — Un `snapshot.json` est généré et poussé vers le site statique.

Le site est consultable vers 06h45.

## Architecture

```
Sources RSS ──► Azure Functions ──► ADLS Gen2 ──► Databricks ──► snapshot.json ──► Blob Static Website ──► CDN
                (collecte)          (medallion)    (5 notebooks)   (gold)           ($web container)
```

| Composant | Service | Détail |
|-----------|---------|--------|
| Ingestion | Azure Functions (Consumption, Python) | Timer trigger, ~62 sources, async |
| Stockage | ADLS Gen2 | Medallion : raw → bronze → silver → gold |
| Traitement | Databricks Workflow | 5 notebooks chaînés, single-node job cluster |
| Frontend | Azure Blob Static Website + CDN | Fichier HTML unique, routing CSS pur, 0 build step |
| Monitoring | Application Insights | Alertes : workflow échoué, sources en erreur, snapshot périmé |

Coût estimé : **~7–18€/mois**.

## Structure du repo

```
kiosque/
├── infra/                  # Terraform (Azure + Databricks workspace)
│   ├── main.tf
│   ├── storage.tf
│   ├── functions.tf
│   ├── databricks.tf
│   ├── monitoring.tf
│   ├── cdn.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars    # (gitignored)
│
├── functions/              # Azure Function App (Python)
│   ├── collector/
│   │   ├── __init__.py
│   │   └── function.json
│   ├── parsers/
│   │   ├── rss.py
│   │   ├── sitemap.py
│   │   └── gnews.py
│   ├── host.json
│   └── requirements.txt
│
├── notebooks/              # Databricks notebooks
│   ├── 01_normalize.py
│   ├── 02_cluster.py
│   ├── 03_ownership.py
│   ├── 04_metrics.py
│   └── 05_publish.py
│
├── frontend/               # Site statique
│   └── kiosque.html        # Fichier unique (HTML + CSS + JS minimal)
│
├── config/
│   ├── sources.yaml        # Liste des 62 médias, feeds, groupes propriétaires
│   └── ownership.yaml      # Mapping média → groupe (ref. Acrimed)
│
├── tests/
│   ├── fixtures/           # Snapshots de flux RSS réels pour les tests
│   ├── test_parsers.py
│   └── test_snapshot.py
│
├── docs/
│   ├── architecture.md
│   ├── snapshot-schema.json
│   └── operations.md
│
└── README.md
```

## Groupes propriétaires suivis

| Groupe | Exemples de titres | Couleur |
|--------|-------------------|---------|
| Bolloré / Vivendi | CNews, Canal+, Europe 1, Le JDD | Rouge |
| Niel / Le Monde | Le Monde, L'Obs, Télérama, Courrier International | Bleu |
| Bouygues / TF1 | TF1, LCI, TF1 Info | Orange |
| Arnault / LVMH | Les Échos, Le Parisien, Radio Classique | Violet |
| Kretinsky | Marianne, Elle, Franc-Tireur | Vert |
| Saadé / CMA CGM | La Provence, BFM TV, RMC, La Tribune Dimanche | Sarcelle |
| Service public | France Info, France Inter, France 2, Arte | Gris |
| Indépendant | Mediapart, Blast, Reporterre, Alternatives Économiques | Gris clair |

Source des données de propriété : [Acrimed](https://www.acrimed.org/).

## Prérequis

- **Azure** : un abonnement avec les droits de créer des ressources.
- **Terraform** ≥ 1.5
- **Python** ≥ 3.11
- **Azure CLI** (`az`) authentifié
- **Databricks CLI** (optionnel, pour le déploiement des notebooks)

## Démarrage rapide

### 1. Provisionner l'infrastructure

```bash
# Créer manuellement le backend Terraform (une seule fois)
az storage account create -n stkiosquetfstate -g rg-tfstate -l westeurope --sku Standard_LRS
az storage container create -n tfstate --account-name stkiosquetfstate

# Déployer
cd infra
terraform init
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

### 2. Déployer la Function App

```bash
cd functions
func azure functionapp publish func-kiosque-prod
```

### 3. Déployer le frontend

```bash
az storage blob upload-batch \
  --source frontend/ \
  --destination '$web' \
  --account-name stkiosqueprod
```

### 4. Configurer Databricks

Importer les notebooks dans le workspace, configurer le Workflow (5 tasks chaînées), et connecter le stockage ADLS.

## Données et métriques

- **HHI** (Herfindahl-Hirschman Index) : mesure de concentration par sujet. 0 = diversité totale, 10 000 = monopole.
- **Angle mort** : sujet couvert par un seul groupe propriétaire ou ignoré par les grands groupes.
- **Part du dominant** : pourcentage d'articles d'un sujet provenant du groupe le plus représenté.

## Principes

- **Pas de republication** — Kiosque affiche des titres et des liens. Le contenu reste chez l'éditeur.
- **Couleur = propriété** — Les couleurs ne sont jamais décoratives. Chaque teinte encode un groupe propriétaire, renforcée par un pattern (rayures, points, hachures) pour l'accessibilité.
- **Zéro build frontend** — Le site est un fichier HTML unique. Pas de bundler, pas de framework, pas de node_modules.
- **Coût minimal** — Tout est serverless ou near-zero idle cost. Le budget cible est <20€/mois.
- **Transparence méthodologique** — La page « Méthode » du site documente les sources, les limites du clustering, et les seuils utilisés.

## Licence

À définir.

## Références

- [Acrimed](https://www.acrimed.org/) — Observatoire des médias, données de propriété
- [dataclimat.fr](https://dataclimat.fr/) — Inspiration design
- [atlasflux.saynete.net](https://atlasflux.saynete.net/) — Annuaire de flux RSS presse française
