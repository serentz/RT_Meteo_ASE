# Architecture et règles du monitoring

```
 bastion (192.168.50.10)                       pg01 (192.168.50.11)        ase01 (192.168.50.21)
┌──────────────────────────┐   meteo.instance   ┌───────────────────┐      ┌──────────────────┐
│ scrutateur (Python)      │◄───────────────────│ PostgreSQL        │      │ SAP ASE 16       │
│  1 relevé / instance /   │  meteo.enregistrer │  schéma meteo     │      │  port 5000 (TDS) │
│  minute, en parallèle    │───────────────────►│  + vues etat_*    │      └──────────────────┘
│                          │   TDS 5000                                            ▲
│                          │───────────────────────────────────────────────────────┘
│ Grafana                  │◄── vues meteo.etat_instance / etat_indicateur (rôle grafana_ro)
└──────────────────────────┘
```

Le scrutateur tourne sur le bastion et interroge chaque instance ASE **à distance** : plus aucun agent ni client PostgreSQL sur ase01.

## Périmètre

Le monitoring des deadlocks est **retiré du POC** : il n'y a plus de lecture du log ASE, de suivi de rotation ni de dédoublonnage d'événements. Cela permet de placer le script Python sur le bastion. Les indicateurs sont au nombre de quatre.

## Collecte

Intervalle : 60 secondes (`SCRUTATEUR_INTERVALLE_S`), cadence fixe sans dérive. À chaque cycle, le scrutateur relit la table `meteo.instance` ; une instance ajoutée, modifiée ou désactivée (`actif`) est prise en compte au cycle suivant sans redémarrage.

| Colonne de `meteo.instance` | Rôle |
|---|---|
| `nom` | nom de l'instance, affiché ; sert aussi de nom d'hôte si `host` est vide |
| `login`, `password` | compte ASE utilisé par le scrutateur |
| `host`, `port` | adresse de connexion si elle diffère du nom ; port 5000 par défaut |
| `actif` | `false` : l'instance n'est plus relevée ni affichée |

`host` et `port` s'ajoutent aux trois champs demandés (nom, login, mot de passe), car le scrutateur étant distant il doit savoir où se connecter.

**Parallélisme.** Chaque instance est relevée dans son propre thread (16 au maximum, `SCRUTATEUR_MAX_PARALLELE`). La panne ou la lenteur d'une instance ne retarde pas les autres. Si le relevé précédent d'une instance n'est pas terminé, elle est sautée au lieu d'empiler des relevés. Les délais de connexion (10 s) et de requête (15 s) bornent la durée d'un relevé à 40 s.

**Unité de travail.** `collecter_et_enregistrer(instance, source, depot)` (module `scrutateur/collecte.py`) relève une instance et met à jour PostgreSQL ; elle ne lève jamais d'exception. Un échec devient une mesure `erreur`. L'écriture se fait par un seul appel à la fonction SQL `meteo.enregistrer_mesure(...)`.

**Sources ASE** (vérifiées dans la documentation SAP, requêtes dans `sql/ase/supervision.sql`) :

- `master..sysprocesses.blocked` : spid du bloqueur, 0 si aucun ; `time_blocked` : durée du blocage **en secondes**.
- `master..systransactions.starttime` : début de chaque transaction ouverte. `sysprocesses` ne donne que le nom de la transaction, jamais sa date de début, d'où cette seconde source.
- Sont exclus : la connexion du scrutateur (`@@spid`) et les tâches système (`suid > 0`, hypothèse à valider sur l'instance réelle).

**Limites assumées.** La durée de la requête en cours n'est pas collectée : elle n'est pas disponible sans activer les tables de monitoring (MDA). Seule la durée de la transaction ouverte est retenue, qui est l'indicateur utile pour les verrous.

**Sécurité.** Les identifiants ASE sont en clair dans `meteo.instance` (choix du POC). Seul le rôle `scrutateur` les lit ; `grafana_ro` n'a aucun droit sur les colonnes `login` et `password`. Utiliser un login ASE dédié, en lecture seule. Le mot de passe PostgreSQL du scrutateur est dans `/etc/scrutateur/scrutateur.env` (mode 0640, hors Git). Les mots de passe ne figurent jamais dans les journaux ni dans les messages d'erreur stockés.

## Indicateurs affichés

| Indicateur (`code`) | Définition | Unité |
|---|---|---|
| Temps max blocage (`blocage_max`) | Maximum des durées de blocage des processus actuellement bloqués | secondes |
| Temps moyen blocage (`blocage_moyen`) | Moyenne sur les seuls processus actuellement bloqués | secondes |
| Temps max transactions (`transaction_max`) | Maximum de l'âge des transactions ouvertes | secondes |
| Temps moyen transactions (`transaction_moyenne`) | Moyenne de l'âge des transactions ouvertes | secondes |

Un relevé réussi sans blocage ni transaction donne zéro. Une mesure indisponible donne NULL et l'état « inconnu ». L'âge d'une transaction est indépendant de la durée de la dernière commande. Les processus bloqués ou en transaction sont conservés dans `meteo.processus` (spid, commande, statut, login, bloqueur, durées) : le bloqueur est identifiable.

## Seuils et écrans

Pour chaque indicateur : seuil warning W et seuil alarme A, avec 0 <= W < A, dans `meteo.seuil`. Une ligne sans `instance_id` est le seuil par défaut ; une ligne pour une instance le remplace. Valeur < W : soleil ; W <= valeur < A : nuage ; valeur >= A : orage.

Valeurs initiales **provisoires** (secondes), à ajuster selon la charge :

| Indicateur | W | A |
|---|---|---|
| blocage max | 30 | 120 |
| blocage moyen | 10 | 60 |
| transaction max | 300 | 900 |
| transaction moyenne | 60 | 300 |

Les vues `meteo.etat_indicateur` (une ligne par instance et par indicateur : valeur, seuils, niveau) et `meteo.etat_instance` (une ligne par instance : pire niveau) alimentent l'affichage. Le niveau est `soleil`, `nuage`, `orage` ou `inconnu`.

**État inconnu.** Il s'affiche si l'instance n'a jamais été relevée, si le dernier relevé est en erreur, s'il est périmé ou si les seuils manquent : il n'y a jamais de faux soleil. La péremption est de 180 secondes (3 cycles), réglable dans `meteo.parametre` (`peremption_s`). Le message d'erreur et la date du dernier relevé sont dans les vues.

**Niveau d'une instance.** Il reprend le plus grave de ses indicateurs, dans l'ordre orage > inconnu > nuage > soleil : une alarme connue prime, mais on n'affiche jamais soleil ni nuage s'il manque une mesure. L'icône « inconnu » est la lune endormie (`images/iconnes/lune dors.png`).

Vue globale : une tuile cliquable par instance, avec son icône. Vue détail : une ligne par indicateur avec valeur, unité, icône et seuils. Les tableaux de bord Grafana restent à réaliser (`grafana/`).

## Acceptation fonctionnelle

1. Instance sans anomalie : soleil et quatre valeurs valides.
2. Blocage contrôlé : nuage puis orage aux seuils, avec bloqueur identifiable dans `meteo.processus`.
3. Transaction longue : durée indépendante de la durée de la dernière commande.
4. Instance injoignable, login refusé ou PostgreSQL indisponible : aucun faux soleil ; retour à la normale après reprise et relevé valide.
5. Parallélisme : une instance lente ou en panne ne retarde pas le relevé des autres.
6. Instance ajoutée ou désactivée dans `meteo.instance` : prise en compte sans redémarrage.

Les points 4 (partiellement), 5 et 6 sont couverts par les tests automatiques ; les points 1 à 3 demandent une vraie instance ASE (voir `docs/scrutateur.md`, section « État de validation »).
