# Windows et GitHub

Le dépôt est https://github.com/serentz/RT_Meteo_ASE. Les médias SAP, licences, ISO, disques et secrets restent hors Git.

## Récupérer cette première livraison

Installer Git pour Windows si nécessaire. Dans PowerShell, vérifier `git --version`.

Si `I:\POC\RT_Meteo_ASE` contient déjà des fichiers et n'est pas un clone Git, les conserver dans un dossier de sauvegarde avant de cloner. Ces commandes ne suppriment pas l'ancien contenu :

```powershell
$project = 'I:\POC\RT_Meteo_ASE'
if (Test-Path -LiteralPath $project) {
    throw 'Le dossier existe : utiliser la procédure ci-dessous avant le clonage.'
}
git clone --branch poc/hyperv-3-vms https://github.com/serentz/RT_Meteo_ASE.git $project
if ($LASTEXITCODE -ne 0) { throw 'Clonage échoué.' }
Set-Location $project
git status
```

Si le dossier existe, examiner son contenu. Pour le conserver intégralement, sans suppression :

```powershell
$project = 'I:\POC\RT_Meteo_ASE'
$backup = 'I:\POC\RT_Meteo_ASE_backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $project -Destination $backup -ErrorAction Stop
# Reprendre ensuite le bloc de clonage ci-dessus.
```

Ne pas déplacer un clone existant sans raison : si le dossier contient déjà `.git`, faire plutôt `git status`, puis `git fetch origin` et `git switch --track origin/poc/hyperv-3-vms` si la branche locale n'existe pas. Git refusera les changements incompatibles ; ne pas forcer et ne pas employer `reset --hard`.

## Envoyer les modifications suivantes

```powershell
Set-Location 'I:\POC\RT_Meteo_ASE'
git status
# Afficher les changements avant leur publication.
git diff
# Ajouter seulement les fichiers voulus, jamais les médias ni les secrets.
git add -- infra/hyperv docs images scrutateur sql tests README.md .gitignore .gitattributes
git diff --cached
git commit -m 'Adapte infrastructure Hyper-V RT_Meteo_ASE'
git push -u origin HEAD
```

La première authentification HTTPS peut ouvrir Git Credential Manager. Ne jamais inclure un jeton dans l'URL ou dans un script. Si Git demande l'identité de commit, configurer `git config user.name 'Serentz'` et `git config user.email 'ADRESSE_GITHUB_OU_NOREPLY'` dans ce dépôt avec la vraie adresse choisie.

Pour recevoir les changements après avoir enregistré ses propres modifications : `git pull --ff-only`. Si cette commande échoue, examiner la divergence avant toute fusion ; ne pas forcer.
