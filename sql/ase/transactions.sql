-- Transactions ouvertes d'une instance ASE, de la plus longue a la plus courte.
-- Seconde (et derniere) requete du scrutateur, executee sur la meme connexion que supervision.sql :
-- lecture seule de master..systransactions et master..sysprocesses (tables systeme, PAS les tables MDA mon*).
--
-- Colonnes : spid, login, hostname, program_name, hostprocess, cmd, status, debut (debut de la plus ancienne
-- transaction de la session), duree_s (secondes ecoulees depuis ce debut, heure du serveur ASE).
-- Une ligne par session ; les memes exclusions que supervision.sql (uid > 0, JOB SCHEDULER, session du scrutateur).
-- Le scrutateur ne conserve que les 50 premieres lignes.
--
-- Valide sous isql sur ASE01 (16.0 SP04 PL08) : session sa AWAITING COMMAND avec une transaction ouverte
-- depuis 28 s -> 1 ligne. A valider aussi sur l'instance de travail (PL06), et par le login de supervision.
--
-- Essai : ouvrir une session isql, begin tran + une insertion sans commit, puis lancer cette requete.
SELECT t.spid, suser_name(p.suid), p.hostname, p.program_name, p.hostprocess, p.cmd, p.status,
       min(t.starttime) AS debut, datediff(ss, min(t.starttime), getdate()) AS duree_s
FROM master..systransactions t, master..sysprocesses p
WHERE p.spid = t.spid
  AND p.uid > 0 AND isnull(p.program_name, '') <> 'JOB SCHEDULER' AND p.spid <> @@spid
GROUP BY t.spid, suser_name(p.suid), p.hostname, p.program_name, p.hostprocess, p.cmd, p.status
ORDER BY duree_s DESC
go
