# Installation des trois VM

## Prérequis

PC Windows avec Hyper-V disponible et activé, PowerShell administrateur, au moins 12 Go de RAM libres pour les invités en plus de Windows, espace disque suffisant sur I:. Les ISO doivent être les médias complets Ubuntu Server 24.04 LTS et CentOS Stream 9 DVD x86_64, téléchargés auprès de leurs éditeurs et contrôlés par leur somme de contrôle. Les ISO ne sont pas incluses.

Le réseau proposé est 192.168.50.0/24 avec passerelle 192.168.50.1. Vérifier qu'il n'entre pas en conflit avec LAN, VPN ou réseau Hyper-V existant. Le NAT Windows peut nécessiter une adaptation s'il existe déjà un autre réseau NAT sur le poste. Le script ne résout pas automatiquement ces conflits.

Les noms `bastion`, `pg01`, `ase01` doivent être libres. Le script refuse de remplacer une VM ou un dossier existant. Ne pas lancer `-Destroy` pour supprimer des VM d'un autre projet.

## Lancement

Depuis PowerShell administrateur :

```powershell
Set-Location 'I:\POC\RT_Meteo_ASE'
Get-Help .\infra\hyperv\create_vms.ps1 -Detailed
# Adapter les chemins aux ISO réellement présentes.
.\infra\hyperv\create_vms.ps1 `
  -UbuntuIso 'K:\ShareLinux\Image ISO\ubuntu-server.iso' `
  -CentosIso 'K:\ShareLinux\Image ISO\centos-stream9-dvd.iso'
```

Le mot de passe est demandé à l'exécution. Ne pas le saisir en clair dans une commande enregistrée. Une clé publique SSH locale est détectée si présente dans le profil utilisateur qui exécute PowerShell. Les VM et disques sont créés dans `I:\POC\HyperV\RT_Meteo_ASE`, hors du répertoire Git.

Ce script automatise la configuration et l'installation après démarrage de l'installateur, mais n'édite pas les ISO :

- Ubuntu : confirmer `yes` si l'installateur le demande. Si nécessaire, ajouter `autoinstall` à la ligne du noyau via le menu GRUB.
- CentOS : sélectionner l'installation au menu de démarrage. `ks.cfg` est recherché sur le volume OEMDRV.

Laisser les consoles ouvertes pour suivre l'installation. Un délai dépassé n'autorise aucune suppression automatique. Sur échec, vérifier les consoles ; les graines peuvent contenir le mot de passe en clair et doivent rester dans un dossier accessible uniquement aux administrateurs. Après succès, elles sont détachées puis supprimées.

Le disque système CentOS est explicitement `sda` ; le disque graine est attaché au contrôleur SCSI à l'emplacement 1. Vérifier cette correspondance dans l'installateur avant toute adaptation matérielle. Le modèle efface le disque système de la VM.

## Validation Windows et invités

Le script exige un marqueur écrit en fin d'installation sur chacune des graines, puis retire les ISO et graines, redémarre les invités et attend leur port TCP 22. L'ouverture de ce port ne vérifie ni l'authentification ni l'exécution complète de cloud-init.

```powershell
Get-VM -Name bastion,pg01,ase01 | Select-Object Name,State,MemoryAssigned
ssh admin01@192.168.50.10
ssh admin01@192.168.50.11
ssh admin01@192.168.50.21
```

Sur chaque Ubuntu, exécuter `sudo cloud-init status --wait --long`, puis vérifier `hostname`, `ip -br address`, `ip route`, `getent hosts pg01 ase01 bastion`. Sur CentOS, vérifier ces mêmes commandes réseau et `systemctl is-active sshd`.

Le compte est membre de sudo/wheel et utilise son mot de passe pour sudo. Conserver la vérification des clés d'hôte SSH. Une recréation change ces clés : vérifier la nouvelle empreinte en console avant de mettre à jour known_hosts.

## Recréation volontaire

```powershell
# Destructif : demande de confirmation OUI et contrôle du marqueur du projet.
.\infra\hyperv\create_vms.ps1 -Destroy -Only ase01
# Puis recréer uniquement cette VM avec le média CentOS.
.\infra\hyperv\create_vms.ps1 -Only ase01 -CentosIso 'K:\ShareLinux\Image ISO\centos-stream9-dvd.iso'
```

Sans `-Only`, `-Destroy` cible les trois VM du projet. Le réseau est toujours conservé. Les anciennes VM créées par le script d'origine n'ont pas le marqueur de propriété et sont volontairement refusées : les examiner manuellement, sans fabriquer de marqueur pour contourner ce contrôle.

## Suite

Installer PostgreSQL sur pg01, Grafana sur bastion puis ASE depuis un média SAP et une licence adaptés. Installer ensuite le client/driver PostgreSQL, le driver ASE et l'agent Python sur ase01. Aucune de ces étapes applicatives n'est encore effectuée par cette livraison.

## Références

- https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html
- https://canonical-subiquity.readthedocs-hosted.com/en/latest/explanation/cloudinit-autoinstall-interaction.html
- https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/automatically_installing_rhel/starting-kickstart-installations_rhel-installer
