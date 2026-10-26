# RT_Meteo_ASE

POC de monitoring SAP/Sybase ASE : un scrutateur Python (sur le bastion) relève chaque minute, en parallèle, les instances ASE listées dans PostgreSQL ; Grafana restitue l'état sous forme soleil / nuage / orage.

## Infrastructure

Le script Hyper-V prépare trois VM et installe leurs OS. Il n'installe ni ASE, ni PostgreSQL, ni Grafana, ni le scrutateur (voir [docs/scrutateur.md](docs/scrutateur.md)).

| VM | OS prévu | IP par défaut | Ressources | Rôle cible |
|---|---|---|---|---|
| bastion | Ubuntu Server 24.04 LTS | 192.168.50.10 | 2 CPU, 4 Go, 30 Go | Scrutateur Python + Grafana |
| pg01 | Ubuntu Server 24.04 LTS | 192.168.50.11 | 2 CPU, 4 Go, 30 Go | PostgreSQL |
| ase01 | CentOS Stream 9 | 192.168.50.21 | 2 CPU, 4 Go, 40 Go | ASE 16 seul (interrogé à distance, ni agent ni client PostgreSQL) |

CentOS Stream est le choix hérité du script fourni ; sa compatibilité avec le SP/PL exact d'ASE doit être vérifiée avant installation du moteur. Aucune certification SAP de cette configuration n'est revendiquée.

Voir [Installation des VM](docs/installation_vm.md), [Scrutateur](docs/scrutateur.md), [Synchronisation Windows/GitHub](docs/transfert_github.md) et [Spécification du monitoring](docs/architecture.md).

## Fonctionnement

- Le scrutateur lit la table `meteo.instance` (nom, login, mot de passe) et, chaque minute, relève en parallèle toutes les instances actives.
- Quatre indicateurs par instance : temps max et moyen de blocage, temps max et moyen des requêtes en cours. Ils sont tous calculés à partir d'un seul tableau lu sur `master..sysprocesses`. Le monitoring des deadlocks est retiré du POC.
- Chaque indicateur est comparé à des seuils (warning / alarme) : soleil, nuage, orage ; « inconnu » (lune) si la mesure manque ou est périmée. L'instance affiche son pire niveau.

## Organisation

- `infra/hyperv/create_vms.ps1` et `infra/hyperv/templates/` : infrastructure et modèles d'installation.
- `infra/hyperv/check_vms.ps1` : diagnostic en lecture seule (Hyper-V, réseau de l'hôte, ping, port 22, bannière SSH).
- `images/iconnes/` : icônes météo (soleil, nuages, orages, lune endormie) pour l'affichage.
- `scrutateur/` : le script Python (une fonction par relevé d'instance, boucle parallèle), son service systemd et son modèle de configuration.
- `sql/ase/` : la requête de supervision exécutée sur chaque instance ASE.
- `sql/postgresql/` : schéma `meteo` (instances, mesures, seuils, vues d'état, fonction d'écriture) et rôles.
- `grafana/` : futurs tableaux de bord et provisioning.
- `tests/` : tests Python (`unittest`) et test SQL du schéma.

## État de validation

Scrutateur et schéma PostgreSQL : 47 tests Python et un test SQL passent, et le code a été exécuté de bout en bout contre un PostgreSQL 16 réel avec une instance ASE simulée ; la connexion à une vraie instance ASE n'est pas encore validée (détail dans [docs/scrutateur.md](docs/scrutateur.md)). Pour l'infrastructure : contrôles statiques des scripts, des modèles et des remplacements effectués. Exécution PowerShell et installation Hyper-V non réalisées dans l'environnement de préparation Linux. Le premier essai (hors dépôt) s'est arrêté à l'accès SSH aux VM : lancer `infra/hyperv/check_vms.ps1` puis suivre la section « Dépannage SSH » de [Installation des VM](docs/installation_vm.md). Validation Windows et consoles des trois VM indispensable avant de déclarer l'infrastructure opérationnelle.
