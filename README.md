# Kiosque

**Transparence médiatique en France.** Kiosque agrège chaque matin les titres de ~65 médias français, regroupe les articles par sujet, et révèle la concentration de la couverture par groupe propriétaire.

Qui couvre quoi — et qui ne couvre rien.

---

## Pourquoi

Six groupes industriels contrôlent la majorité des médias français. Le même événement peut faire la une de 15 titres appartenant au même propriétaire, pendant qu'un autre sujet n'est couvert que par un indépendant. Kiosque rend cette réalité visible, chaque jour, sans éditorialiser.

Le projet ne republie aucun contenu — il agrège des titres et des liens, mesure la diversité de la couverture, et signale les angles morts.

## Comment ça marche

Chaque matin à 06h00 UTC :

1. **Collecte** — Une Azure Function parcourt les flux RSS, sitemaps et fallbacks Google News des ~65 sources.
2. **Normalisation** — Les articles bruts sont nettoyés, dédupliqués, et structurés dans un schéma commun.
3. **Clustering** — Un pipeline NLP regroupe les articles qui traitent du même sujet en *stories* (embeddings multilingues + clustering agglomératif).
4. **Ownership** — Chaque article est rattaché à son groupe propriétaire (données Acrimed).
5. **Métriques** — Indice HHI de concentration, détection des angles morts, KPI du jour.
6. **Publication** — Un `snapshot.json` est généré et poussé vers le site statique.

Le site est consultable vers 06h45.

## Architecture

```
Sources RSS ──► Azure Functions ──► ADLS Gen2 ──► Databricks ──► snapshot.json ──► Blob Static Website ──► CDN
                (collecte)          (medallion)    (6 notebooks)   (gold)           ($web container)
```

| Composant | Service | Détail |
|-----------|---------|--------|
| Ingestion | Azure Functions (Consumption, Python) | Timer trigger, ~65 sources, async |
| Stockage | ADLS Gen2 | Medallion : raw → bronze → silver → gold |
| Traitement | Databricks Workflow + Unity Catalog | 6 notebooks Spark (DBR 18 LTS ML), tables Delta gérées dans le catalogue kiosque, lignage de raw à gold |
| Frontend | Azure Blob Static Website + CDN | Fichier HTML unique, routing CSS pur, 0 build step |
| Monitoring | Application Insights | Alertes : workflow échoué, sources en erreur, snapshot périmé |

Coût estimé : **~7–18€/mois**.

## Structure du repo

```
kiosque/
├── infra/                  # Terraform (Azure + Databricks workspace + alertes)
├── functions/              # Azure Function App (Python, modèle v2)
│   ├── function_app.py     # Timers : collecte 06:00 UTC, fraîcheur 07:30 UTC
│   ├── collector.py
│   ├── freshness.py
│   ├── storage.py
│   ├── parsers/            # rss.py, sitemap.py, gnews.py
│   └── tests/
├── pipeline/               # Package Python kiosque_pipeline (logique Databricks)
│   ├── src/kiosque_pipeline/
│   │   ├── normalize.py  cluster.py  ownership.py  metrics.py  publish.py
│   │   └── snapshot.schema.json   # Contrat snapshot.json (frontend)
│   └── tests/
├── notebooks/              # 00_ref … 05_publish (wrappers Databricks)
├── frontend/               # kiosque.html (à venir)
├── config/
│   ├── sources.yaml        # Médias, flux, groupe propriétaire
│   └── groups.yaml         # Groupes propriétaires
├── databricks.yml          # Bundle Databricks : job quotidien
├── run_local.py            # Collecte locale → ./output/raw
└── run_pipeline.py         # Pipeline locale → ./output/$web/snapshot.json
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

`owner_group` encode la **propriété capitalistique** — c'est la seule base du HHI (les indépendants y sont comptés séparément). Le bucket `independant` signifie « hors des six groupes nommés » : il rassemble aussi bien Le Figaro, Libération ou Ouest-France que des titres de lignes éditoriales très diverses.

Source des données de propriété : [Acrimed](https://www.acrimed.org/).

> **Réseau Stérin / Périclès.** Le rachat de *Valeurs actuelles* (finalisé déc. 2025) par le trio La Combe / Caude / Stérin et le financement, via la galaxie Périclès, de l'école de journalisme (ILDJ) qui irrigue CNews, Le Figaro, Valeurs actuelles, Boulevard Voltaire et Causeur, dessinent un **réseau d'influence** émergent. Comme il s'agit d'influence et non de contrôle capitalistique direct, ce réseau est suivi comme **signal qualitatif** (champ `influence`, optionnel) et reste **exclu du calcul du HHI**.

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
scripts/deploy_functions.sh            # copie config/sources.yaml puis publie
```

### 3. Déployer le frontend

```bash
az storage blob upload-batch \
  --source frontend/ \
  --destination '$web' \
  --account-name stkiosqueprod
```

Le pipeline publie lui-même `$web/snapshot.json` ; seul `kiosque.html` est à téléverser.

### 4. Déployer le pipeline Databricks

```bash
export DATABRICKS_HOST="https://$(terraform -chdir=infra output -raw databricks_workspace_url)"
databricks secrets create-scope kiosque
databricks secrets put-secret kiosque datalake-connection-string \
  --string-value "$(terraform -chdir=infra output -raw datalake_connection_string)"
databricks bundle deploy -t prod --var alert_email=<email>
```

## Données et métriques

- **HHI** (Herfindahl-Hirschman Index) : concentration **capitalistique** par sujet, calculée sur les médias distincts (pas le nombre d'articles). Chaque média indépendant compte comme un propriétaire distinct ; le service public compte comme un seul. 0 = diversité totale, 10 000 = monopole. Ne mesure que la propriété — jamais la tendance éditoriale.
- **Angle mort** : `single_group` (tous les médias appartiennent au même groupe, hors indépendants) ou `ignored_by_majors` (≥ 3 médias, aucun des six grands groupes).
- **Part du dominant** : pourcentage d'articles d'un sujet provenant du groupe le plus représenté.
- **Lignage (audit)** : chaque métrique publiée est traçable dans Unity Catalog jusqu'aux fichiers bruts du collecteur (`kiosque.raw.feeds`) et à la table de propriété `kiosque.ref.sources`.
- **Tendance** : axe éditorial non suivi par Kiosque — impossible à sourcer objectivement. Seule la propriété est mesurée.

## Principes

- **Pas de republication** — Kiosque affiche des titres et des liens. Le contenu reste chez l'éditeur.
- **Propriété = seul axe** — Kiosque mesure la concentration capitalistique, pas la ligne éditoriale. Classer les médias sur un axe politique nécessiterait une source institutionnelle fiable — elle n'existe pas.
- **Périmètre éditorial** — Tout média français couvrant l'actualité générale est intégré, quelle que soit sa ligne. En revanche, les publications négationnistes ou de haine explicite sont **exclues** — faible valeur de clustering, et risque juridique.
- **Couleur = propriété** — Les couleurs ne sont jamais décoratives. Chaque teinte encode un groupe propriétaire, renforcée par un pattern (rayures, points, hachures) pour l'accessibilité.
- **Zéro build frontend** — Le site est un fichier HTML unique. Pas de bundler, pas de framework, pas de node_modules.
- **Coût minimal** — Tout est serverless ou near-zero idle cost. Le budget cible est <20€/mois.
- **Transparence méthodologique** — La page « Méthode » du site documente les sources, les limites du clustering, et les seuils utilisés.

## Exploitation

**Horaires (UTC)** : collecte 06:00 → job Databricks 06:20 → site à jour ≈ 06:45 → contrôle de fraîcheur 07:30.

**Alertes (email)** : job Databricks en échec ; plus de 5 sources en erreur ; collecteur non exécuté depuis 24 h ; `snapshot.json` non daté du jour.

**Relancer une journée** : `databricks bundle run kiosque_daily -t prod --params run_date=YYYY-MM-DD`. Le job est idempotent : il réécrit les fichiers du jour. Si `raw/feeds/<date>/_report.json` manque, relancer d'abord la collecte (portail Azure → Function → `collect_feeds` → Exécuter).

**Ajouter un média** : ajouter l'entrée dans `config/sources.yaml` avec un `owner_group` présent dans `config/groups.yaml`. Les tests échouent sinon.

**En local** :

```bash
python run_local.py --limit 5                   # → output/raw/feeds/<date>/
brew install openjdk@21                         # Spark 4 requiert Java 17 ou 21
pip install -e "pipeline[spark,embed]"
python run_pipeline.py                          # → output/$web/snapshot.json
```

## Licence

À définir.

## Références

- [Acrimed](https://www.acrimed.org/) — Observatoire des médias, données de propriété
- [dataclimat.fr](https://dataclimat.fr/) — Inspiration design
- [atlasflux.saynete.net](https://atlasflux.saynete.net/) — Annuaire de flux RSS presse française
