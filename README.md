# RT_Meteo_ASE

POC de monitoring SAP/Sybase ASE avec collecte Python locale, stockage PostgreSQL et restitution Grafana.

## Livraison initiale : infrastructure

Cette version prépare trois VM Hyper-V et installe leurs OS. Elle n'installe pas encore ASE, PostgreSQL, Grafana, ni l'agent. Les répertoires correspondants sont réservés pour les étapes suivantes.

| VM | OS prévu | IP par défaut | Ressources | Rôle cible |
|---|---|---|---|---|
| bastion | Ubuntu Server 24.04 LTS | 192.168.50.10 | 2 CPU, 4 Go, 30 Go | Grafana |
| pg01 | Ubuntu Server 24.04 LTS | 192.168.50.11 | 2 CPU, 4 Go, 30 Go | PostgreSQL |
| ase01 | CentOS Stream 9 | 192.168.50.21 | 2 CPU, 4 Go, 40 Go | ASE 16 + agent Python |

CentOS Stream est le choix hérité du script fourni ; sa compatibilité avec le SP/PL exact d'ASE doit être vérifiée avant installation du moteur. Aucune certification SAP de cette configuration n'est revendiquée.

Voir [Installation des VM](docs/installation_vm.md), [Synchronisation Windows/GitHub](docs/transfert_github.md) et [Spécification du monitoring](docs/architecture.md).

## Organisation

- `infra/hyperv/create_vms.ps1` et `infra/hyperv/templates/` : infrastructure et modèles d'installation.
- `infra/hyperv/check_vms.ps1` : diagnostic en lecture seule (Hyper-V, réseau de l'hôte, ping, port 22, bannière SSH).
- `images/iconnes/` : icônes météo (soleil, nuages, orages, lune endormie) pour l'affichage.
- `agent/` : futur collecteur et service systemd.
- `sql/ase/` : futures requêtes et prérequis ASE.
- `sql/postgresql/` : futur schéma et vues de restitution.
- `grafana/` : futurs tableaux de bord et provisioning.
- `tests/` : futurs scénarios d'intégration.

## État de validation

Contrôles statiques des scripts, des modèles et des remplacements effectués. Exécution PowerShell et installation Hyper-V non réalisées dans l'environnement de préparation Linux. Le premier essai (hors dépôt) s'est arrêté à l'accès SSH aux VM : lancer `infra/hyperv/check_vms.ps1` puis suivre la section « Dépannage SSH » de [Installation des VM](docs/installation_vm.md). Validation Windows et consoles des trois VM indispensable avant de déclarer l'infrastructure opérationnelle.
