#cloud-config
# Installation automatique d'Ubuntu Server (autoinstall) - genere par create_vms.ps1
autoinstall:
  version: 1
  locale: fr_FR.UTF-8
  keyboard:
    layout: {{KEYBOARD}}
  network:
    version: 2
    ethernets:
      hyperv:
        match:
          driver: hv_netvsc
        dhcp4: false
        addresses: [{{IP}}/24]
        routes:
          - to: default
            via: {{GATEWAY}}
        nameservers:
          addresses: [8.8.8.8, 1.1.1.1]
  storage:
    layout:
      name: lvm
      sizing-policy: all
      match:
        size: largest
  ssh:
    install-server: true
    allow-pw: true
  late-commands:
    - mkdir -p /mnt/rt-seed
    - mount /dev/disk/by-label/CIDATA /mnt/rt-seed
    - sh -c 'printf "%s\n" "{{NAME}}" > /mnt/rt-seed/INSTALL_OK'
    - sync
    - umount /mnt/rt-seed
  shutdown: poweroff
  user-data:
    hostname: {{NAME}}
    timezone: Europe/Paris
    ssh_pwauth: true
    users:
      - name: {{USER}}
        groups: [sudo]
        shell: /bin/bash
        lock_passwd: false
        {{SSHKEYS}}
    chpasswd:
      expire: false
      users:
        - {name: {{USER}}, password: "{{PASSWORD}}", type: text}
    write_files:
      - path: /etc/hosts
        append: true
        content: |
{{HOSTS}}
    runcmd:
      - systemctl enable --now ssh
