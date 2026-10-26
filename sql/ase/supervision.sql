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
--   execution_time duree de la requete en cours, en secondes (NULL si aucune requete en cours)
--   uid            identifiant d'utilisateur dans la base courante du processus
-- Lignes retenues : requete en cours OU bloque OU bloqueur d'un autre processus (le bloqueur est souvent
-- inactif : sans cette clause il ne serait pas dans le tableau et resterait anonyme).
--
-- Origine : requete validee sous isql par l'utilisateur sur une instance reelle (colonne execution_time presente).
-- Cette colonne n'apparait pas dans la page de documentation SAP consultee pour sysprocesses : le sens
-- (secondes de la requete en cours) est celui indique par l'utilisateur.
-- A VALIDER sur l'instance reelle :
--   1. le login de supervision peut lire master..sysprocesses ;
--   2. "uid > 1" ecarte les taches systeme, mais aussi toute session dont l'utilisateur dans sa base courante
--      est dbo (uid 1) : verifier que les sessions applicatives attendues sont bien listees ;
--   3. execution_time croit en secondes pendant une requete longue (ex. WAITFOR DELAY '00:00:30' dans une session) ;
--   4. blocked / time_blocked refletent un blocage provoque a la main
--      (session 1 : begin tran + update sans commit ; session 2 : update de la meme ligne).
-- Creation d'un login dedie (a adapter, mot de passe a choisir) :
--   sp_addlogin scrutateur, '<mot_de_passe>'

SELECT p.spid, p.uid, suser_name(p.suid), p.status, p.hostname, p.program_name, p.hostprocess,
       p.cmd, p.blocked, p.time_blocked, p.execution_time
FROM master..sysprocesses p
WHERE (p.execution_time IS NOT NULL OR p.time_blocked IS NOT NULL
       OR p.spid IN (SELECT b.blocked FROM master..sysprocesses b WHERE b.blocked <> 0))
  AND p.uid > 1 AND p.spid <> @@spid
go
