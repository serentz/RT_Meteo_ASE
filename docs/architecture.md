# Architecture et règles du monitoring — cible à implémenter

Agent Python sur ase01 → PostgreSQL sur pg01 → Grafana sur bastion.

## Collecte

Intervalle proposé : 5 secondes, configurable. L'agent lit ASE localement et transmet les résultats à PostgreSQL. Le compte Grafana disposera uniquement de droits de lecture ; l'agent aura des droits d'écriture limités aux tables nécessaires. Secrets en configuration locale hors Git.

Chaque échantillon conserve : identifiant d'instance, horodatage de collecte UTC, SPID, durée de requête si disponible, durée de transaction ouverte, durée de blocage, SPID bloqueur, commande/statut et état de collecte. La source exacte et les unités doivent être vérifiées sur le SP/PL ASE installé avant d'écrire les requêtes. La durée d'une requête n'est pas la durée de sa transaction.

Les logs ASE sont lus avec suivi de fichier/position et gestion de rotation. Un événement deadlock doit être identifié et dédoublonné ; le nombre de lignes d'un rapport n'est pas le nombre de deadlocks. Une reprise ne doit pas recompter les mêmes événements.

## Indicateurs affichés

| Indicateur | Définition proposée | Unité |
|---|---|---|
| Temps max blocage | Maximum des attentes de blocage en cours au dernier échantillon | secondes |
| Temps moyen blocage | Moyenne sur les seuls processus actuellement bloqués | secondes |
| Temps max transactions | Maximum de l'âge des transactions ouvertes | secondes |
| Temps moyen transactions | Moyenne de l'âge des transactions ouvertes | secondes |
| Nombre de deadlocks | Événements distincts sur les 5 dernières minutes | nombre |

Les processus système et l'agent sont exclus des agrégats utilisateurs. Une collecte réussie sans blocage/transaction donne zéro ; une mesure indisponible donne NULL et l'état inconnu. Les unités, exclusions et fenêtres seront documentées avec les requêtes finales.

## Seuils et écrans

Pour chaque métrique et instance : seuil warning W, seuil alarme A, avec 0 <= W < A. Valeur < W : soleil ; W <= valeur < A : nuage ; valeur >= A : orage. Les valeurs initiales restent à définir selon la charge.

Vue globale : une tuile cliquable par instance ; vue détail : une ligne par indicateur avec valeur, unité, icône et seuils. L'état global reprend le niveau le plus grave. Si une collecte ou une métrique est indisponible, afficher explicitement l'état inconnu ; une alarme connue reste visible avec un signal de données incomplètes.

Proposition de péremption : au-delà de 20 secondes sans collecte à cadence 5 secondes, déclarer les données périmées. Le journal d'erreurs et la date de dernière collecte réussie doivent être visibles. La fraîcheur des logs deadlock est suivie séparément de celle des requêtes SQL.

## Acceptation fonctionnelle future

1. Instance sans anomalie : soleil et cinq valeurs valides.
2. Blocage contrôlé : nuage puis orage aux seuils, avec bloqueur identifiable.
3. Transaction longue : durée indépendante de la durée de la dernière commande.
4. Deadlock contrôlé : un événement compté une seule fois, même après reprise de l'agent.
5. Agent arrêté, ASE indisponible ou PostgreSQL indisponible : aucun faux soleil ; retour à la normale après reprise et collecte valide.
6. Rotation du log : absence de double comptage et signalement de toute perte de couverture.
