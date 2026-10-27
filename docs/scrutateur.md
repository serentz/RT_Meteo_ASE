# Scrutateur : installation, exploitation, tests

Le scrutateur est le script Python du bastion. Chaque minute il lit `meteo.instance` dans PostgreSQL, interroge en parallèle chaque instance ASE active et enregistre le résultat par `meteo.enregistrer_mesure(...)`. Règles et indicateurs : [architecture](architecture.md).

## Avant de commencer : où taper quoi

Chaque bloc de commandes de ce document est précédé de la **machine** sur laquelle le taper. Une commande tapée au mauvais endroit échoue ou ne fait rien. Les invites (le texte affiché avant le curseur) indiquent où l'on est :

| Où | Comment s'y connecter | Invite affichée | Pour en sortir |
|---|---|---|---|
| PowerShell, sur le PC Windows | menu Démarrer, « PowerShell » | `PS I:\POC\RT_Meteo_ASE>` | fermer la fenêtre |
| VM `pg01` (Ubuntu) | depuis PowerShell : `ssh admin01@192.168.50.11` | `admin01@pg01:~$` | `exit` |
| VM `bastion` (Ubuntu) | depuis PowerShell : `ssh admin01@192.168.50.10` | `admin01@bastion:~$` | `exit` |
| VM `ase01` (CentOS) | depuis PowerShell : `ssh admin01@192.168.50.21` | `[admin01@ase01 ~]$` | `exit` |
| Console PostgreSQL (`psql`) | sur pg01 : `sudo -u postgres psql -d meteo` | `meteo=#` | `\q` |
| Console ASE (`isql` ou `tsql`) | voir section 2 | `1>` | `quit` (`isql`), `exit` (`tsql`) |

- Le mot de passe de `ssh` et de `sudo` est celui choisi pour `admin01` au lancement de `create_vms.ps1`.
- À la première connexion à une VM, `ssh` affiche une empreinte et demande `Are you sure you want to continue connecting`. Répondre `yes`.
- Dans une console PostgreSQL, chaque instruction SQL se termine par `;`. Dans `isql` et `tsql`, on tape `go` sur une ligne seule pour exécuter ce qu'on vient de saisir.
- Copier-coller dans PowerShell : clic droit. Une ligne de bloc = une commande, sauf les lignes qui se terminent par `\` (la commande continue sur la ligne suivante).

Trois mots de passe sont à choisir et sont désignés ainsi dans le document :

| Nom | Sert à |
|---|---|
| `MOT_DE_PASSE_1` | rôle PostgreSQL `scrutateur` (utilisé par le script) |
| `MOT_DE_PASSE_2` | rôle PostgreSQL `grafana_ro` (utilisé plus tard par Grafana) |
| `MOT_DE_PASSE_ASE` | login ASE `scrutateur`, qui lit `sysprocesses` |

Éviter l'apostrophe et l'antislash dans ces mots de passe.

## 1. PostgreSQL sur pg01

### 1.1 Envoyer les scripts SQL sur pg01 (PowerShell, sur Windows)

Dans `I:\POC\RT_Meteo_ASE`, après un `git pull --ff-only` :

```powershell
scp -r I:\POC\RT_Meteo_ASE\sql admin01@192.168.50.11:/tmp/
```

### 1.2 Installer PostgreSQL et créer la base (sur pg01)

Se connecter : `ssh admin01@192.168.50.11`. Puis :

```bash
sudo apt update
sudo apt install -y postgresql
psql --version
sudo -u postgres createdb meteo
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 -f /tmp/sql/postgresql/001_schema.sql
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 \
  -v pwd_scrutateur='MOT_DE_PASSE_1' -v pwd_grafana='MOT_DE_PASSE_2' -f /tmp/sql/postgresql/002_roles.sql
```

- `psql --version` doit afficher PostgreSQL **15 ou plus** (Ubuntu 24.04 installe la 16) : le schéma utilise `UNIQUE NULLS NOT DISTINCT`.
- Remplacer `MOT_DE_PASSE_1` et `MOT_DE_PASSE_2` par les mots de passe choisis, en gardant les apostrophes.
- Pourquoi `sudo -u postgres` et pas simplement `psql` : sans option, `psql` se connecte avec le nom de l'utilisateur Linux (`admin01`) et PostgreSQL répond `FATAL: role "admin01" does not exist`. Le compte administrateur de PostgreSQL s'appelle `postgres`, et `sudo -u postgres` lance la commande sous ce compte.

Vérifier que le schéma et les rôles existent :

```bash
sudo -u postgres psql -d meteo -c "\dt meteo.*"
sudo -u postgres psql -d meteo -c "\du"
```

La première commande liste les tables `instance`, `mesure`, `processus`, `indicateur`, `seuil` et `parametre`. La seconde montre les rôles `scrutateur` et `grafana_ro`.

### 1.3 Autoriser le bastion à se connecter (sur pg01)

Par défaut PostgreSQL n'écoute que sur lui-même. Les commandes ci-dessous supposent l'organisation Debian/Ubuntu (`/etc/postgresql/<version>/main/`) :

```bash
ls /etc/postgresql
```

Cette commande affiche le numéro de version (par exemple `16`). Si ce n'est pas `16`, remplacer le nombre dans les trois commandes suivantes.

```bash
echo "listen_addresses = '*'" | sudo tee /etc/postgresql/16/main/conf.d/meteo.conf
echo "host meteo scrutateur 192.168.50.10/32 scram-sha-256" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
echo "host meteo grafana_ro 192.168.50.10/32 scram-sha-256" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
sudo systemctl restart postgresql
sudo ss -tlnp | grep 5432
```

La dernière commande doit montrer une ligne avec `0.0.0.0:5432` ou `*:5432`. Ubuntu Server n'active pas de pare-feu par défaut : aucune règle à ajouter sur pg01.

### 1.4 Déclarer une instance ASE à surveiller (sur pg01, dans la console PostgreSQL)

Ouvrir la console PostgreSQL :

```bash
sudo -u postgres psql -d meteo
```

L'invite devient `meteo=#`. Taper alors l'instruction suivante (en remplaçant le mot de passe) :

```sql
INSERT INTO meteo.instance (nom, login, password, host, port) VALUES ('ASE01', 'scrutateur', 'MOT_DE_PASSE_ASE', '192.168.50.21', 5000);
```

La console répond `INSERT 0 1`. Vérifier :

```sql
SELECT nom, host, port, actif FROM meteo.instance;
```

Puis quitter la console avec `\q`.

Autres opérations, à taper dans la même console (`meteo=#`) :

```sql
-- Instance sur un autre port ou un autre nom de machine :
INSERT INTO meteo.instance (nom, login, password, host, port) VALUES ('ase_prod1', 'supervision', 'MOT_DE_PASSE', 'srv-ase1.exemple.fr', 5000);
-- Changer un mot de passe :
UPDATE meteo.instance SET password = 'NOUVEAU_MOT_DE_PASSE' WHERE nom = 'ASE01';
-- Activer une instance déclarée mais inactive :
UPDATE meteo.instance SET actif = true WHERE nom = 'ASE01';
-- Retirer une instance de la surveillance :
UPDATE meteo.instance SET actif = false WHERE nom = 'ASE01';
```

- Si le mot de passe contient une apostrophe, la doubler (`''`).
- `nom` est le nom affiché : ici le nom du serveur ASE (`ASE01`). Quand `host` est vide, il sert aussi de nom de machine ; renseigner `host` avec l'adresse IP dès que ce n'est pas un nom de machine résolu par le bastion.
- Le nom doit ensuite être écrit **exactement** pareil (majuscules comprises) dans `--tester` (section 3.4).
- Le scrutateur relit cette table à chaque cycle : aucune relance n'est nécessaire.
- Le mot de passe est stocké en clair : n'accorder aucun autre droit sur cette table (voir `sql/postgresql/002_roles.sql`).

### 1.5 Vérifier que le bastion atteint PostgreSQL (sur le bastion)

Se connecter : `ssh admin01@192.168.50.10`. Puis :

```bash
sudo apt update
sudo apt install -y postgresql-client
psql -h pg01 -U scrutateur -d meteo -c "SELECT nom, actif FROM meteo.instance"
```

`psql` demande le mot de passe : taper `MOT_DE_PASSE_1`. Le résultat doit lister l'instance déclarée en 1.4. Ici `-h` désigne la machine PostgreSQL, `-U` le rôle et `-d` la base. En cas d'échec, voir le dépannage en fin de document.

## 2. Instance ASE

### 2.0 Préparer le compte d'installation (sur ase01)

Installer et lancer ASE sous un compte Linux **dédié, non root**, et non avec `sudo` : sinon le serveur tourne en root et tous ses fichiers appartiennent à root, ce qui gêne l'exploitation ensuite. Se connecter à ase01 (`ssh admin01@192.168.50.21`), puis :

```bash
sudo useradd -m sybase
sudo mkdir -p /opt/sap
sudo chown sybase:sybase /opt/sap
sudo -i -u sybase
```

La dernière commande ouvre un terminal sous le compte `sybase` (invite `[sybase@ase01 ~]$`). Lancer l'installateur SAP depuis ce terminal, avec `/opt/sap` comme répertoire d'installation ; `exit` ramène au compte `admin01`. Le nom du compte et le répertoire sont des exemples : en prendre d'autres si l'équipe a une convention.

- Les prérequis système (bibliothèques, paramètres du noyau, mémoire partagée) sont ceux de la documentation d'installation de SAP ASE 16.0 SP04 pour Linux. Ils ne sont pas vérifiés dans ce dépôt, et CentOS Stream 9 n'est pas une plate-forme certifiée pour ASE (voir le README).
- Sur la VM de test de ce POC, ASE 16.0 SP04 PL08 a été installé avec l'installateur de SAP (`setup.bin`) sous le compte `admin01`, dans `/opt/sap`, serveur `ASE01`, port 5000. Cela fonctionne ; `admin01` étant le compte d'administration de la VM, un compte dédié reste préférable.
- Après une installation faite par erreur avec `sudo` : arrêter ASE s'il tourne, puis déplacer ou supprimer l'ancien répertoire d'installation (et les devices créés ailleurs) avant de recommencer. Ne pas installer deux fois dans le même répertoire.

### 2.1 Se connecter à ASE avec `isql` (sur ase01 ou sur le serveur de l'instance)

`isql` est le client en ligne de commande d'ASE. Il s'utilise sous le compte `sybase` créé en 2.0 (`sudo -i -u sybase`) et après chargement de l'environnement ASE :

```bash
. /CHEMIN/INSTALLATION_ASE/SYBASE.sh
export LANG=en_US.UTF-8
isql -U sa -S NOM_DU_SERVEUR_ASE -w 250
```

- `/CHEMIN/INSTALLATION_ASE/` est le répertoire d'installation d'ASE ; `SYBASE.sh` y charge les variables d'environnement.
- `NOM_DU_SERVEUR_ASE` est le nom du serveur déclaré dans le fichier `interfaces` d'ASE (`ps -eo cmd | grep [d]ataserver` l'affiche après `-s`).
- `export LANG=en_US.UTF-8` est nécessaire quand la session est en `fr_FR.UTF-8` : `isql` refuse toute locale absente de `locales.dat` (voir le dépannage). **Ne pas le mettre dans `~/.bash_profile`** d'une machine où l'on lance aussi `psql` : si la locale `en_US.UTF-8` n'est pas générée dans Ubuntu (cas du bastion), `psql` affiche `perl: warning: Setting locale failed`. Deux solutions : taper l'`export` seulement dans la session où l'on lance `isql`, ou générer la locale une fois (sur le bastion : `sudo locale-gen en_US.UTF-8 && sudo update-locale LANG=en_US.UTF-8`, puis se reconnecter) ; avec elle, `isql` et `psql` sont satisfaits tous les deux.
- `isql` demande le mot de passe. L'invite devient `1>`. Taper l'instruction, puis `go` sur la ligne suivante pour l'exécuter. Quitter avec `quit`.

Pour une instance existante, utiliser un compte d'administration habituel. Créer le login de supervision (dans `isql`) :

```
1> sp_addlogin scrutateur, 'MOT_DE_PASSE_ASE'
2> go
```

Le login doit pouvoir lire `master..sysprocesses`, seule table lue par le scrutateur. Le vérifier en 2.3. Voir aussi `sql/ase/supervision.sql`.

### 2.2 Vérifier l'accès réseau depuis le bastion (sur le bastion)

L'instance doit écouter sur le réseau (fichier `interfaces`, pas seulement `localhost`). Le pare-feu CentOS de ase01 ouvre déjà SSH et le port 5000/tcp. Depuis le bastion :

```bash
nc -zv 192.168.50.21 5000
```

La réponse doit contenir `succeeded`. Sinon : l'instance n'est pas démarrée, n'écoute pas sur le réseau, ou le port est différent.

### 2.3 Essayer la requête du scrutateur depuis le bastion (sur le bastion)

Se connecter : `ssh admin01@192.168.50.10`. Puis :

```bash
sudo apt install -y freetds-bin
TDSVER=5.0 tsql -H 192.168.50.21 -p 5000 -U scrutateur
```

**Attention :** sur le bastion, la commande `isql` n'est pas celle d'ASE. Le paquet `unixodbc` (installé en 3.2) fournit un autre outil du même nom, qui s'utilise avec un nom de source de données (`isql -v NOM_DSN`) et ne comprend pas `-S`. Sur le bastion, utiliser `tsql`. Le vrai `isql` d'ASE se trouve sur les machines où le serveur ou le client SAP est installé (sous `.../OCS-16_0/bin/` après `. SYBASE.sh`).

`tsql` (client FreeTDS) demande le mot de passe `MOT_DE_PASSE_ASE`, puis affiche l'invite `1>`. Coller la requête de `sql/ase/supervision.sql`, du `SELECT` jusqu'à la ligne `go` incluse. Le tableau des processus s'affiche (il peut être vide si personne n'exécute de requête). Quitter avec `exit`.

Pour une instance existante, remplacer l'adresse et le port : `TDSVER=5.0 tsql -H srv-ase1.exemple.fr -p 5000 -U supervision`.

### 2.4 Démarrer ASE au démarrage de la VM (sur ase01) — non testé

L'installation par `setup.bin` ne crée aucun service : après un redémarrage de ase01, ASE est arrêté. Trouver d'abord le script de démarrage :

```bash
ls /opt/sap/ASE-16_0/install/RUN_*
```

Puis créer le service (`sudo nano /etc/systemd/system/ase.service`), en remplaçant `RUN_ASE01` si le nom diffère :

```ini
[Unit]
Description=SAP ASE ASE01
After=network-online.target
Wants=network-online.target

[Service]
User=admin01
Environment=LANG=en_US.UTF-8
ExecStart=/bin/bash -c '. /opt/sap/SYBASE.sh && exec /opt/sap/ASE-16_0/install/RUN_ASE01'
Restart=on-failure
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ase
systemctl status ase
```

Si ASE tourne déjà (lancé à la main), l'arrêter avant : `isql -Usa -SASE01`, puis `shutdown` et `go`. Pour arrêter proprement ensuite, préférer `shutdown` sous `isql` à `systemctl stop` (qui envoie un signal au processus).

## 3. Scrutateur sur le bastion

### 3.1 Récupérer le code sur le bastion (sur le bastion)

Se connecter : `ssh admin01@192.168.50.10`. Puis :

```bash
sudo apt update
sudo apt install -y git
git clone --branch poc/hyperv-3-vms https://github.com/serentz/RT_Meteo_ASE.git
cd RT_Meteo_ASE
```

Si le dépôt est privé ou si le bastion n'a pas d'accès à Internet, copier le dossier depuis Windows. Dans PowerShell (sur Windows), puis `cd ~` sur le bastion :

```powershell
scp -r I:\POC\RT_Meteo_ASE\scrutateur admin01@192.168.50.10:~/
```

Les commandes suivantes se tapent dans le dossier qui contient `scrutateur/`.

### 3.2 Installer (sur le bastion)

```bash
sudo apt install -y python3-venv unixodbc tdsodbc freetds-bin
sudo useradd --system --home-dir /opt/scrutateur --shell /usr/sbin/nologin scrutateur
sudo mkdir -p /opt/scrutateur/app /etc/scrutateur
sudo cp -r scrutateur /opt/scrutateur/app/
sudo python3 -m venv /opt/scrutateur/venv
sudo /opt/scrutateur/venv/bin/pip install -r /opt/scrutateur/app/scrutateur/requirements.txt
sudo install -m 0640 -o root -g scrutateur scrutateur/deploy/scrutateur.env.example /etc/scrutateur/scrutateur.env
sudo install -m 0644 scrutateur/deploy/scrutateur.service /etc/systemd/system/scrutateur.service
sudo systemctl daemon-reload
```

### 3.3 Renseigner le mot de passe PostgreSQL (sur le bastion)

```bash
sudo nano /etc/scrutateur/scrutateur.env
```

Le fichier contient une ligne `SCRUTATEUR_PG_DSN=...`. Remplacer `CHANGER_MOI` par `MOT_DE_PASSE_1`, pour obtenir :

```
SCRUTATEUR_PG_DSN=postgresql://scrutateur:MOT_DE_PASSE_1@pg01:5432/meteo
```

Enregistrer avec `Ctrl+O` puis `Entrée`, quitter avec `Ctrl+X`. Si le mot de passe contient `@ : / ? # %`, encoder ces caractères en pourcentage dans l'URL (`@` devient `%40`).

### 3.4 Essayer, puis démarrer (sur le bastion)

Ces commandes lancent le script sous le compte de service `scrutateur`, avec les variables du fichier ci-dessus.

Essai d'une instance, sans rien écrire dans PostgreSQL (remplacer `ASE01` par le nom déclaré en 1.4, majuscules comprises) :

```bash
sudo -u scrutateur bash -c 'set -a; . /etc/scrutateur/scrutateur.env; set +a; cd /opt/scrutateur/app && /opt/scrutateur/venv/bin/python -m scrutateur --tester ASE01'
```

Le script lit l'instance dans `meteo.instance` (PostgreSQL doit donc être joignable et l'instance déclarée), interroge ASE et affiche en JSON les indicateurs (`nb_bloques`, `blocage_max_s`, `requete_max_s`, ...) et le tableau des processus lus (`details`). Si l'instance est absente ou inactive, il liste celles qu'il connaît ; si ASE ne répond pas, il affiche une ligne d'erreur.

Un cycle complet (écrit dans PostgreSQL), puis démarrage du service :

```bash
sudo -u scrutateur bash -c 'set -a; . /etc/scrutateur/scrutateur.env; set +a; cd /opt/scrutateur/app && /opt/scrutateur/venv/bin/python -m scrutateur --une-fois -v'
sudo systemctl enable --now scrutateur
journalctl -u scrutateur -f
```

`journalctl -f` suit le journal du service ; `Ctrl+C` arrête le suivi, pas le service.

### 3.5 Lire le résultat (sur pg01)

```bash
sudo -u postgres psql -d meteo -c "SELECT * FROM meteo.etat_instance"
```

Pour voir les indicateurs de chaque instance, remplacer `meteo.etat_instance` par `meteo.etat_indicateur`.

## 4. Grafana sur le bastion (écrans soleil / nuage / orage)

Tout se tape **sur le bastion** (`ssh admin01@192.168.50.10`), à partir du dossier cloné en 3.1 (`~/RT_Meteo_ASE`, à mettre à jour avec `git pull`). Non testé sur les VM au moment de l'écriture : à valider et à corriger ici si besoin.

### 4.1 Installer Grafana

```bash
sudo apt-get install -y apt-transport-https wget gpg
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
grafana-server --version
```

Les tableaux de bord demandent Grafana 10.4 ou plus récent (cellules « image » des tableaux, source `grafana-postgresql-datasource`).

La synthèse en tuiles (icône, nom dessous) utilise le greffon Grafana « Business Text » :

```bash
sudo grafana cli plugins install marcusolsson-dynamictext-panel
sudo systemctl restart grafana-server
```

Sans ce greffon, l'écran « Météo des instances ASE » affiche une erreur de panneau ; utiliser alors l'écran « (liste) », qui n'en a pas besoin. Le greffon 6.x demande Grafana 11 ou 12, le 5.x Grafana 10 ou 11 (le dépôt du greffon est archivé depuis septembre 2025).

### 4.2 Déployer la configuration du dépôt

```bash
cd ~/RT_Meteo_ASE
sudo mkdir -p /var/lib/grafana/dashboards/meteo /usr/share/grafana/public/img/meteo \
  /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards
sudo cp grafana/dashboards/*.json /var/lib/grafana/dashboards/meteo/
sudo cp grafana/provisioning/datasources/meteo.yaml /etc/grafana/provisioning/datasources/
sudo cp grafana/provisioning/dashboards/meteo.yaml /etc/grafana/provisioning/dashboards/
sudo cp images/iconnes/*.png /usr/share/grafana/public/img/meteo/
```

Les icônes sont servies par Grafana sous `/public/img/meteo/` (à recopier après une mise à jour du paquet Grafana).

### 4.3 Donner à Grafana le mot de passe du rôle `grafana_ro`

Le mot de passe n'est pas dans Git : le fichier de la source de données le lit dans l'environnement du service.

```bash
echo 'METEO_GRAFANA_PWD=MOT_DE_PASSE_2' | sudo tee -a /etc/default/grafana-server > /dev/null
sudo systemctl enable --now grafana-server
systemctl status grafana-server
```

`MOT_DE_PASSE_2` est celui donné à `002_roles.sql` (voir « où taper quoi »). Éviter les guillemets et les espaces dans ce mot de passe.

### 4.4 Ouvrir les écrans

Depuis le navigateur du PC Windows : `http://192.168.50.10:3000`. Premier accès : utilisateur `admin`, mot de passe `admin`, que Grafana demande de changer. Menu *Dashboards* :

- **Météo des instances ASE** : une tuile par instance avec son icône (soleil, nuage, orage, lune) et son nom en dessous, bordure de la couleur de l'état, âge du relevé. Un clic ouvre le détail. Rafraîchi toutes les 30 s.
- **Météo des instances ASE (liste)** : la même synthèse en tableau, sans greffon (secours).
- **Détail d'une instance ASE** : choisir l'instance en haut ; état, un indicateur par ligne (valeur, unité, seuils, icône) et le tableau des processus du dernier relevé (requêtes en cours, bloqués avec leur bloqueur).

Si les tableaux sont vides ou en erreur : *Connections → Data sources → meteo → Save & test*. Une erreur d'authentification vient de `METEO_GRAFANA_PWD` ou de la ligne `grafana_ro` dans `pg_hba.conf` (1.3) ; `sudo journalctl -u grafana-server -n 30 --no-pager` donne le détail.

## Mettre à jour une base déjà installée (transactions ouvertes)

Si le schéma a été installé avant l'ajout des transactions ouvertes, la table `meteo.transaction_ouverte` et la fonction `meteo.enregistrer_transactions` manquent : sans elles, le scrutateur ne peut plus enregistrer ses mesures. Sur pg01, après avoir copié les fichiers du dépôt (section 1.1) :

```bash
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 -f /tmp/sql/postgresql/001_schema.sql
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 -c "GRANT EXECUTE ON FUNCTION meteo.enregistrer_transactions(bigint, jsonb) TO scrutateur; GRANT SELECT ON meteo.transaction_ouverte TO grafana_ro;"
```

`001_schema.sql` peut être rejoué sans risque (il ne supprime rien) ; les messages « already exists, skipping » sont normaux. Mettre ensuite à jour le scrutateur sur le bastion (`git pull`, puis la copie de la section 3.2 et `sudo systemctl restart scrutateur`) et les tableaux de bord Grafana (section 4.2). Le login ASE de supervision doit pouvoir lire `master..systransactions` (essai : `sql/ase/transactions.sql` sous `isql` avec ce login).

## Réglages

Variables de `/etc/scrutateur/scrutateur.env` (valeurs par défaut entre parenthèses) : `SCRUTATEUR_INTERVALLE_S` (60), `SCRUTATEUR_MAX_PARALLELE` (16), `SCRUTATEUR_ASE_LOGIN_TIMEOUT_S` (10), `SCRUTATEUR_ASE_REQUETE_TIMEOUT_S` (15), `SCRUTATEUR_ODBC_PILOTE` (FreeTDS), `SCRUTATEUR_TDS_VERSION` (5.0). Après modification : `sudo systemctl restart scrutateur`. Le scrutateur avertit au démarrage si un relevé peut dépasser l'intervalle.

## Dépannage

| Message ou symptôme | Où | Piste |
|---|---|---|
| `psql: FATAL: role "admin01" does not exist` | pg01 | `psql` a été lancé sans `sudo -u postgres` : utiliser `sudo -u postgres psql -d meteo`. |
| `Connection refused` (port 5432) | bastion | `listen_addresses` non appliqué ou PostgreSQL non redémarré : refaire 1.3 et vérifier avec `sudo ss -tlnp \| grep 5432` sur pg01. |
| `no pg_hba.conf entry for host` | bastion | Ligne `host meteo scrutateur 192.168.50.10/32 ...` absente de `pg_hba.conf` : refaire 1.3. |
| `password authentication failed for user "scrutateur"` | bastion | `MOT_DE_PASSE_1` différent de celui donné à `002_roles.sql`, ou caractère spécial non encodé dans `scrutateur.env`. |
| `Connexion a PostgreSQL impossible (OperationalError)` ou `failed to resolve host 'xxx@pg01'` | bastion | Le mot de passe contient un caractère spécial (`@`, `:`, `/`, `#`, `%`, `?`) : dans l'URL il doit être encodé (`@` devient `%40`). Obtenir la forme encodée : `python3 -c "import urllib.parse,getpass;print(urllib.parse.quote(getpass.getpass(),safe=''))"` puis coller le résultat dans `scrutateur.env`. Le plus simple : choisir un mot de passe sans caractère spécial. |
| `could not translate host name "pg01"` | bastion | Résolution de nom : remplacer `pg01` par `192.168.50.11` dans la commande ou dans `scrutateur.env`. |
| `Can't open lib 'FreeTDS'` | bastion | Paquet `tdsodbc` absent, ou pilote non déclaré dans `/etc/odbcinst.ini` : régler `SCRUTATEUR_ODBC_PILOTE` sur le nom qui y figure. |
| `Login timeout expired`, `Unable to connect` | bastion | Réseau, port 5000, `interfaces` d'ASE qui n'écoute pas sur le réseau, nom non résolu. Essayer 2.2 puis 2.3. |
| `The context allocation routine failed when it tried to load localization files` / `Locale name "fr_FR.UTF-8" doesn't exist` | ase01 | `isql` lancé dans une session dont la locale est inconnue d'ASE : `export LANG=en_US.UTF-8` puis relancer. |
| `Login failed` | bastion | Mauvais login ou mot de passe dans `meteo.instance` (corriger avec le `UPDATE` de 1.4). |
| `Invalid column name 'execution_time'` ou droit refusé sur `sysprocesses` | bastion | La colonne n'existe pas sur cette version d'ASE, ou le login de supervision ne lit pas `master..sysprocesses` : essayer la requête de `sql/ase/supervision.sql` sous `isql`. |
| Caractères accentués illisibles | bastion | Régler `ClientCharset` (en dur dans `scrutateur/ase.py`) selon le jeu de caractères d'ASE. |
| Instance en « inconnu » alors qu'elle répond | pg01 | Relevé périmé (plus de 180 s) : lire `journalctl -u scrutateur` sur le bastion et la colonne `erreur` de `meteo.etat_instance`. |

## Tests

Sans dépendance externe, depuis la racine du dépôt (sur une machine Linux avec Python 3) :

```bash
python3 -m unittest discover -s tests -t . -v
```

Test du schéma PostgreSQL, sur une base **jetable** (tout est annulé à la fin du test). D'abord, dans PowerShell sur Windows :

```powershell
scp -r I:\POC\RT_Meteo_ASE\tests admin01@192.168.50.11:/tmp/
```

Puis sur pg01 (les scripts `sql` ont été envoyés en 1.1) :

```bash
sudo -u postgres createdb meteo_test
sudo -u postgres psql -d meteo_test -v ON_ERROR_STOP=1 -f /tmp/sql/postgresql/001_schema.sql
sudo -u postgres psql -d meteo_test -v ON_ERROR_STOP=1 -v pwd_scrutateur='x' -v pwd_grafana='y' -f /tmp/sql/postgresql/002_roles.sql
sudo -u postgres psql -d meteo_test -v ON_ERROR_STOP=1 -f /tmp/tests/postgresql/test_schema.sql
sudo -u postgres dropdb meteo_test
```

Le test affiche `OK : tous les controles du schema sont passes` avant la dernière commande, qui supprime la base jetable.

## État de validation

Réalisé dans l'environnement de préparation (Linux) :

- 63 tests Python (calculs sur le tableau, transactions ouvertes, lecture ASE avec un faux pilote, parallélisme, panne d'une instance, instance bloquée non relancée, relecture de `meteo.instance`, panne de PostgreSQL, mot de passe masqué, cohérence entre la requête, le fichier SQL et le schéma) ;
- schéma, vues, fonction d'écriture et droits des rôles testés sur un vrai PostgreSQL 16 ;
- code du scrutateur exécuté de bout en bout contre ce PostgreSQL, avec une instance ASE simulée.

**Validé sur les VM de test (ASE01 16.0 SP04 PL08, PostgreSQL 16 sur pg01, scrutateur et Grafana sur le bastion)** : connexion à ASE par pyodbc et FreeTDS (TDS 5.0) avec le login `scrutateur`, écriture dans PostgreSQL, service systemd, vues, `execution_time` en millisecondes (converti en secondes), exclusion des sessions `AWAITING COMMAND`, blocage et bloqueur identifiés (scénarios d'acceptation 1 à 3), retour au soleil après un blocage, écrans Grafana (tuiles, liste, détail).

**Non réalisé ou à valider** : arrêt d'ASE (la tuile « lune » inconnu, scénario 4), la requête des transactions ouvertes par le scrutateur dans le service (validée sous `isql`), l'instance de travail en PL06, le démarrage automatique d'ASE (2.4), les seuils (provisoires), et l'installation de Grafana sur un bastion neuf (section 4 écrite d'après l'installation faite ensemble).
