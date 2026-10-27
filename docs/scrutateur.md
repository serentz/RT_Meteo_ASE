# Scrutateur : installation, exploitation, tests

Le scrutateur est le script Python du bastion. Chaque minute il lit `meteo.instance` dans PostgreSQL, interroge en parallèle chaque instance ASE active et enregistre le résultat par `meteo.enregistrer_mesure(...)`. Règles et indicateurs : [architecture](architecture.md).

## 1. PostgreSQL sur pg01

```bash
sudo apt install -y postgresql
sudo -u postgres createdb meteo
# Copier le dossier sql/ du dépôt sur pg01 (lisible par l'utilisateur postgres), par exemple vers /tmp/sql
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 -f /tmp/sql/postgresql/001_schema.sql
sudo -u postgres psql -d meteo -v ON_ERROR_STOP=1 \
  -v pwd_scrutateur='MOT_DE_PASSE_1' -v pwd_grafana='MOT_DE_PASSE_2' -f /tmp/sql/postgresql/002_roles.sql
```

Les deux mots de passe ne doivent contenir ni apostrophe ni antislash. Autoriser le bastion à se connecter :

- `postgresql.conf` : `listen_addresses = '*'` (ou `'192.168.50.11'`) ;
- `pg_hba.conf` : `host meteo scrutateur 192.168.50.10/32 scram-sha-256` et `host meteo grafana_ro 192.168.50.10/32 scram-sha-256` ;
- `sudo systemctl restart postgresql`.

Ubuntu Server n'active pas de pare-feu par défaut : aucune règle à ajouter sur pg01.

Déclarer une instance (une ligne par instance ASE ; `nom` doit être résolu depuis le bastion : `/etc/hosts` contient `ase01`) :

```sql
INSERT INTO meteo.instance (nom, login, password) VALUES ('ase01', 'scrutateur', 'MOT_DE_PASSE_ASE');
-- Autre port ou autre nom d'hôte : colonnes port et host. Retirer une instance : UPDATE meteo.instance SET actif = false WHERE nom = 'ase01';
```

Le mot de passe est stocké en clair : n'accorder aucun autre droit sur cette table (voir `002_roles.sql`).

## 2. Instance ASE

1. Créer un login de supervision dédié (voir `sql/ase/supervision.sql`) et vérifier qu'il lit `master..sysprocesses`. Aucune autre table n'est lue.
2. L'instance doit écouter sur le réseau (fichier `interfaces`, pas seulement `localhost`). Le pare-feu CentOS de ase01 ouvre déjà SSH et le port 5000/tcp.
3. Depuis le bastion, avant d'installer le scrutateur : `TDSVER=5.0 tsql -H ase01 -p 5000 -U scrutateur` (paquet `freetds-bin`), puis coller la requête de `sql/ase/supervision.sql` : elle rend le tableau des processus dont le scrutateur tire ses indicateurs.

## 3. Scrutateur sur le bastion

Depuis la racine du dépôt cloné sur le bastion :

```bash
sudo apt install -y python3-venv unixodbc tdsodbc freetds-bin
sudo useradd --system --home-dir /opt/scrutateur --shell /usr/sbin/nologin scrutateur
sudo mkdir -p /opt/scrutateur/app /etc/scrutateur
sudo cp -r scrutateur /opt/scrutateur/app/
sudo python3 -m venv /opt/scrutateur/venv
sudo /opt/scrutateur/venv/bin/pip install -r /opt/scrutateur/app/scrutateur/requirements.txt

sudo install -m 0640 -o root -g scrutateur scrutateur/deploy/scrutateur.env.example /etc/scrutateur/scrutateur.env
sudo nano /etc/scrutateur/scrutateur.env          # remplacer CHANGER_MOI (mot de passe du rôle scrutateur)
sudo install -m 0644 scrutateur/deploy/scrutateur.service /etc/systemd/system/scrutateur.service
sudo systemctl daemon-reload
```

Essai d'une instance, sans rien écrire dans PostgreSQL :

```bash
sudo -u scrutateur bash -c 'set -a; . /etc/scrutateur/scrutateur.env; set +a; cd /opt/scrutateur/app && /opt/scrutateur/venv/bin/python -m scrutateur --tester ase01'
```

Un cycle complet (écrit dans PostgreSQL), puis démarrage du service :

```bash
sudo -u scrutateur bash -c 'set -a; . /etc/scrutateur/scrutateur.env; set +a; cd /opt/scrutateur/app && /opt/scrutateur/venv/bin/python -m scrutateur --une-fois -v'
sudo systemctl enable --now scrutateur
journalctl -u scrutateur -f
```

Vérification côté PostgreSQL : `sudo -u postgres psql -d meteo -c "SELECT * FROM meteo.etat_instance"`.

Réglages (variables de `scrutateur.env`) : `SCRUTATEUR_INTERVALLE_S` (60), `SCRUTATEUR_MAX_PARALLELE` (16), `SCRUTATEUR_ASE_LOGIN_TIMEOUT_S` (10), `SCRUTATEUR_ASE_REQUETE_TIMEOUT_S` (15), `SCRUTATEUR_ODBC_PILOTE` (FreeTDS), `SCRUTATEUR_TDS_VERSION` (5.0). Le scrutateur avertit au démarrage si un relevé peut dépasser l'intervalle.

## Dépannage

| Message ou symptôme | Piste |
|---|---|
| `Can't open lib 'FreeTDS'` | Paquet `tdsodbc` absent, ou pilote non déclaré dans `/etc/odbcinst.ini` : régler `SCRUTATEUR_ODBC_PILOTE` sur le nom qui y figure. |
| `Login timeout expired`, `Unable to connect` | Réseau, port 5000, `interfaces` d'ASE qui n'écoute pas sur le réseau, nom non résolu depuis le bastion. Essayer `tsql` (section 2). |
| `Login failed` | Mauvais login ou mot de passe dans `meteo.instance`. |
| `Invalid column name 'execution_time'` ou droit refusé sur `sysprocesses` | La colonne n'existe pas sur cette version d'ASE, ou le login de supervision ne lit pas `master..sysprocesses` : essayer la requête de `sql/ase/supervision.sql` sous `isql`. |
| Caractères accentués illisibles | Régler `ClientCharset` (en dur dans `scrutateur/ase.py`) selon le jeu de caractères d'ASE. |
| Instance en « inconnu » alors qu'elle répond | Relevé périmé (plus de 180 s) : lire `journalctl -u scrutateur` et `erreur` dans `meteo.etat_instance`. |

## Tests

Sans dépendance externe, depuis la racine du dépôt :

```bash
python3 -m unittest discover -s tests -t . -v
```

Test du schéma PostgreSQL, sur une base **de test** (tout est annulé à la fin) :

```bash
psql -d meteo_test -v ON_ERROR_STOP=1 -f tests/postgresql/test_schema.sql
```

## État de validation

Réalisé dans l'environnement de préparation (Linux) :

- 49 tests Python (calculs sur le tableau, lecture ASE avec un faux pilote, parallélisme, panne d'une instance, instance bloquée non relancée, relecture de `meteo.instance`, panne de PostgreSQL, mot de passe masqué, cohérence entre la requête, le fichier SQL et le schéma) ;
- schéma, vues, fonction d'écriture et droits des rôles testés sur un vrai PostgreSQL 16 ;
- code du scrutateur exécuté de bout en bout contre ce PostgreSQL, avec une instance ASE simulée.

**Non réalisé, à valider sur les VM** : connexion réelle à ASE (pyodbc + FreeTDS, TDS 5.0), pilote `psycopg`, service systemd, exécution de la requête ASE par le scrutateur sur une vraie instance (la requête elle-même a été essayée sous `isql` par l'équipe ; restent les quatre points à valider listés dans `sql/ase/supervision.sql`, dont le sens de `execution_time` et la présence éventuelle d'autres tâches internes dans le tableau), et les scénarios d'acceptation 1 à 3.
