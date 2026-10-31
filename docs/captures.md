# Captures d'écran (Release 1)

Captures prises sur les VM de test (SAP ASE 16.0 SP04, scrutateur et Grafana sur le bastion), dans `images/Release1/`. Les scénarios et les commandes qui les produisent sont décrits dans [scrutateur.md](scrutateur.md). Les seuils sont les seuils par défaut (voir [architecture.md](architecture.md)), provisoires.

## Synthèse

| Image | Scénario | Ce que l'on voit |
|---|---|---|
| [01_soleil.png](../images/Release1/01_soleil.png) | Instance sans anomalie | Tuile `ase01` : soleil, bordure verte, « relevé il y a 22 s ». |
| [02_nuage_requete.png](../images/Release1/02_nuage_requete.png) | Requête longue en cours (`WAITFOR DELAY`) | Tuile `ase01` : nuage, bordure orange. |
| [03_orage_requete.png](../images/Release1/03_orage_requete.png) | Requête longue, au-delà du seuil d'alarme | Tuile `ase01` : orage, bordure rouge. |
| [07_lune_arret.png](../images/Release1/07_lune_arret.png) | ASE arrêté | Tuile `ase01` : lune endormie (inconnu), « relevé en erreur ». |
| [08_liste_soleil.png](../images/Release1/08_liste_soleil.png) | Instance sans anomalie, vue liste | Une ligne par instance : icône, état, relevé, âge du relevé, erreur. |

## Détail d'une instance

| Image | Scénario | Ce que l'on voit |
|---|---|---|
| [04_detail_requete.png](../images/Release1/04_detail_requete.png) | Requête longue (`WAITFOR`) | Temps max et moyen des requêtes à 68 s : nuage (seuil 60 s) ; la session `spid 18` (`WAITFOR`, `alarm sleep`) figure dans le tableau des processus. |
| [05_detail_blocage.png](../images/Release1/05_detail_blocage.png) | Blocage | `spid 19` (`UPDATE`, `lock sleep`) est bloqué par `spid 18`, le bloqueur, inactif (`AWAITING COMMAND`) mais identifié. Le temps moyen de blocage (16 s, seuil 10 s) donne un nuage ; le bloqueur a aussi une transaction ouverte (47 s). |
| [06_detail_transaction.png](../images/Release1/06_detail_transaction.png) | Transaction ouverte inactive | Aucune requête en cours ni blocage ; `spid 18` garde une transaction ouverte depuis 140 s (tableau des transactions, de la plus longue à la plus courte). Soleil : sous le seuil de 300 s. |

Pour remplacer une capture : garder le nom du fichier, remplacer l'image, mettre à jour la légende ci-dessus.
