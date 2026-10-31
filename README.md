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
- Cinq indicateurs par instance : temps max et moyen de blocage, temps max et moyen des requêtes en cours (calculés sur un tableau lu dans `master..sysprocesses`), et temps max des transactions ouvertes (`master..systransactions`). Le monitoring des deadlocks est retiré du POC.
- Chaque indicateur est comparé à des seuils (warning / alarme) : soleil, nuage, orage ; « inconnu » (lune) si la mesure manque ou est périmée. L'instance affiche son pire niveau.

## Captures d'écran

Les écrans Grafana (soleil, nuage, orage, lune, blocage et bloqueur, transactions ouvertes) sont légendés dans [docs/captures.md](docs/captures.md) ; les images sont dans `images/Release1/`.

## Organisation

- `infra/hyperv/create_vms.ps1` et `infra/hyperv/templates/` : infrastructure et modèles d'installation.
- `infra/hyperv/check_vms.ps1` : diagnostic en lecture seule (Hyper-V, réseau de l'hôte, ping, port 22, bannière SSH).
- `images/Release1/` : captures d'écran Grafana (voir `docs/captures.md`).
- `images/iconnes/` : icônes météo (soleil, nuages, orages, lune endormie) pour l'affichage.
- `scrutateur/` : le script Python (une fonction par relevé d'instance, boucle parallèle), son service systemd et son modèle de configuration.
- `sql/ase/` : les deux requêtes exécutées sur chaque instance ASE (supervision des processus, transactions ouvertes).
- `sql/postgresql/` : schéma `meteo` (instances, mesures, seuils, vues d'état, fonction d'écriture) et rôles.
- `grafana/` : provisioning (source PostgreSQL, tableaux de bord synthèse et détail), voir la section 4 de `docs/scrutateur.md`.
- `tests/` : tests Python (`unittest`) et test SQL du schéma.

## État de validation

Scrutateur et schéma PostgreSQL : 63 tests Python et un test SQL passent ; sur les VM de test, le scrutateur relève une vraie instance ASE (16.0 SP04 PL08), écrit dans PostgreSQL et Grafana affiche l'état, un blocage et son bloqueur (détail et reste à valider dans [docs/scrutateur.md](docs/scrutateur.md)). Pour l'infrastructure : contrôles statiques des scripts, des modèles et des remplacements effectués. Exécution PowerShell et installation Hyper-V non réalisées dans l'environnement de préparation Linux. Sur le PC de test, le script a créé les trois VM et SSH répond sur chacune ; le blocage rencontré venait du pilote réseau de VirtualBox installé sur l'hôte (voir « Dépannage SSH » de [Installation des VM](docs/installation_vm.md)). Restent à contrôler dans les VM : fin de cloud-init, nom d'hôte, réseau et résolution des noms (section « Validation Windows et invités »).
