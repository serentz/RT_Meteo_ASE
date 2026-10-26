-- Requetes executees par le scrutateur sur chaque instance ASE (identiques a scrutateur/ase.py ;
-- tests/test_coherence.py verifie que les deux textes restent identiques).
-- A essayer d'abord sous isql avec le login de supervision, depuis le bastion :
--   isql -S <nom_serveur> -U <login> -w 200 -i sql/ase/supervision.sql
-- A VALIDER sur l'instance reelle (non verifie ici, aucune instance ASE disponible) :
--   1. le login peut lire master..sysprocesses et master..systransactions ;
--   2. suid > 0 exclut bien les taches systeme (housekeeper, checkpoint...) et elles seules ;
--   3. blocked <> 0 / time_blocked (secondes) refletent un blocage provoque a la main
--      (session 1 : begin tran + update sans commit ; session 2 : update de la meme ligne).
-- Creation d'un login dedie (a adapter, mot de passe a choisir) :
--   sp_addlogin scrutateur, '<mot_de_passe>'

SELECT p.spid, p.status, p.cmd, suser_name(p.suid), p.blocked, p.time_blocked
FROM master..sysprocesses p
WHERE p.suid > 0 AND p.spid <> @@spid
go

SELECT t.spid, datediff(ss, t.starttime, getdate())
FROM master..systransactions t
WHERE t.spid > 0 AND t.type = 1
go
