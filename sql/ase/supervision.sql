-- Requete executee par le scrutateur sur chaque instance ASE (identique a SQL_PROCESSUS dans scrutateur/ase.py ;
-- tests/test_coherence.py verifie que les deux textes restent identiques).
-- UNE SEULE requete : le tableau obtenu est lu en memoire par le scrutateur, qui en tire tous les indicateurs
-- (duree de blocage, duree d'execution des requetes) et la liste des processus actifs, bloques et bloquants.
-- A essayer d'abord sous isql avec le login de supervision, depuis le bastion :
--   isql -S <nom_serveur> -U <login> -w 250 -i sql/ase/supervision.sql
--
-- Colonnes lues dans master..sysprocesses :
--   blocked        spid du processus bloqueur, 0 si le processus n'est pas bloque
--   time_blocked   duree du blocage, en secondes (NULL si le processus n'est pas bloque)
--   execution_time duree de la requete en cours, en secondes ; vaut 0 (et non NULL) pour une session AWAITING COMMAND
--   uid            identifiant d'utilisateur dans la base courante du processus
-- Lignes retenues : requete en cours (cmd <> 'AWAITING COMMAND' : sans cela toutes les sessions inactives, dont
-- execution_time vaut 0, rempliraient le tableau) OU bloque OU bloqueur d'un autre processus (le bloqueur est
-- souvent inactif : sans cette clause il ne serait pas dans le tableau et resterait anonyme).
--
-- Origine : requete validee sous isql par l'utilisateur sur une instance reelle, ASE 16.0 SP04 PL06
-- (colonne execution_time presente). Exclusions voulues : uid > 0 (taches systeme) et le processus interne
-- d'ASE dont program_name = 'JOB SCHEDULER' ; isnull() evite d'ecarter les sessions sans program_name.
-- Cette colonne n'apparait pas dans la page de documentation SAP consultee pour sysprocesses : le sens
-- (secondes de la requete en cours) est celui indique par l'utilisateur.
-- A VALIDER sur l'instance reelle :
--   1. le login de supervision peut lire master..sysprocesses ;
--   2. les exclusions (uid > 0, JOB SCHEDULER) ne laissent aucune autre tache interne dans le tableau et
--      n'ecartent aucune session applicative attendue ;
--   3. execution_time croit en secondes pendant une requete longue (ex. WAITFOR DELAY '00:00:30' dans une session) ;
--   4. blocked / time_blocked refletent un blocage provoque a la main
--      (session 1 : begin tran + update sans commit ; session 2 : update de la meme ligne).
-- Creation d'un login dedie (a adapter, mot de passe a choisir) :
--   sp_addlogin scrutateur, '<mot_de_passe>'

SELECT p.spid, p.uid, suser_name(p.suid), p.status, p.hostname, p.program_name, p.hostprocess,
       p.cmd, p.blocked, p.time_blocked, p.execution_time
FROM master..sysprocesses p
WHERE ((p.execution_time IS NOT NULL AND isnull(p.cmd, '') <> 'AWAITING COMMAND')
       OR p.time_blocked IS NOT NULL
       OR p.spid IN (SELECT b.blocked FROM master..sysprocesses b WHERE b.blocked <> 0))
  AND p.uid > 0 AND isnull(p.program_name, '') <> 'JOB SCHEDULER' AND p.spid <> @@spid
go
