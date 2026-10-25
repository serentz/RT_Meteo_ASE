# Installation automatique de CentOS Stream (kickstart) - genere par create_vms.ps1
text
poweroff
cdrom
lang fr_FR.UTF-8
keyboard --vckeymap={{KEYBOARD}} --xlayouts='{{KEYBOARD}}'
timezone Europe/Paris --utc
network --bootproto=static --device=link --ip={{IP}} --netmask=255.255.255.0 --gateway={{GATEWAY}} --nameserver=8.8.8.8,1.1.1.1 --hostname={{NAME}} --activate
rootpw --lock
user --name={{USER}} --groups=wheel --plaintext --password={{PASSWORD}}
{{SSHKEYS}}
firstboot --disable
firewall --enabled --ssh
services --enabled=sshd
ignoredisk --only-use=sda
zerombr
clearpart --all --initlabel --drives=sda
autopart --type=lvm
bootloader --location=mbr

# Outils utiles a ASE (extraction de l'archive, bibliotheques) ; --ignoremissing : un nom absent ne bloque pas l'installation
%packages --ignoremissing
@^minimal-environment
openssh-server
tar
bzip2
unzip
libaio
ncurses-compat-libs
libnsl
nc
net-tools
%end

%post --erroronfail
cat >> /etc/hosts <<'EOT'
{{HOSTS}}
EOT
%end

# Marqueur lu par PowerShell avant de retirer les medias.
%post --nochroot --erroronfail
mkdir -p /mnt/rt-seed
mount /dev/disk/by-label/OEMDRV /mnt/rt-seed
printf '%s\n' '{{NAME}}' > /mnt/rt-seed/INSTALL_OK
sync
umount /mnt/rt-seed
%end
