# cloudinit-kvm 

cloudinit-kvm is a python2 module that lets you easily provision linux virtual machines on your 
personal laptop or workstation using cloud-init's nocloud isos and 
cloud disk images(qcow2).

Use Vagrant (I wrote this because Vagrant's libvirt provider was ugly then.)

It lets you describe a set of vms belonging to a pet project in a yaml
file. You could club puppet, cloud-init's nocloud files and the config
here to have your virtual machines reproducible (as code).


### Requirements
requires pycdlib, yaml and click 

### Installing

1. Clone the git repo.
2. Run pip install
```
git clone https://github.com/sarfarazahmad89/cloudinit-kvm
cd cloudinit-kvm
pip install .
```

## Usage
```
Usage: civirt [OPTIONS] COMMAND [ARGS]...

  utility to build virtual machines using nocloud isos and cloudimgs.

Options:
  --help  Show this message and exit.

Commands:
  build             provision a bunch of virtual machines using config file.
  build-instance    quickly spin up a single instance using "common" settings.
  delete           remove previously provisioned virtual machines.
  delete-instance  delete a previously spun up instance with all its files.
```



### Sample config
```
---    # sample config for building vms using cloudinit-kvm
projectname: 'my-dockerlab'
common:
  bdisk: /tmp/rhel7.qcow2 
  size: 10G 
  outdir: /tmp/my-dockerlab/ 
  cpu: 1 # No. of CPUs to 
  mem: 512 
  userdata: # NoCloud user-data
    # cloud-config
    preserve_hostname: false
    ssh_pwauth: true
    users:
      - name: local
        groups: wheel
        sudo: ['ALL=(ALL) NOPASSWD:ALL']
        ssh_authorized_keys:
          - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDaeYEAr6oO6hE5DdCUY69jO0Up1t2u8FLpdQXXhtFqfZBtQXWn73vvPxS11emsNivzlGDMPFfQIAsxgicQW+hhJBMgITjhYqm8CpYrsp2H5P0Jd+EUScmYxirJYmei7pHv9sjlWa+e8E9hjXSmCTWKxm7wnWXyWgAbgWustUDUQ06p4fOKrjaClzEShitEt88Qe+Q245LQzBgaEaQ1EFjq46WtTlzZLrziNjANO4wfiSuGXwLpjMFBOnGvnYutvawIyXV2bpJIZIC4OHKozA0wItQYvlURmLsREpJxz1x1wO6yaVk0U6Vt+axk+pUgPqMrw/hKymKsjuus3rsfYpPB ahmad@mymachine
    runcmd:
      - 'sudo apt update; sudo apt-get install apt-transport-https ca-certificates -y'
      - 'sudo apt install curl gnupg-agent software-properties-common -y '
      - 'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -'
      - 'apt-key fingerprint 0EBFCD88 -y'
      - 'add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"'
vms: # Individual virtual machines settings, any key:value pair from common can be overridden here.
  - fqdn: docker101.lab                 # fqdn for the virtual machine
    ipaddr: 192.168.122.100          # ipaddr for the virtual machine
  - fqdn: docker102.lab
    ipaddr: 192.168.122.50

```

### Mandatory config fields (key:value pairs)
Each virtual machine requires the following mandatory k:v pairs to be successfully built. ("common" and individual pairs get merged.

```
fqdn:     # FQDN of the virtual machine.
ipaddr:   # IPADDR of the virtual machine assumed to be from default virbr0
cpu:      # No. of cpus to allocate to the VM.
mem:      # Amount of memory to allocate in megabytes (accepts an integer)
bdisk:    # Path to the backing cloudimg
size:     # Size to allocate to the new disk (Use units G,M,K)
outdir:   # Directory to place all relevant files.
userdata: # Cloudinit's user-data
metadata: # Cloudinit's meta-data (virtual machine's interface is automatically configured to use the ipaddr value.)

```

Note that you can write per virtual machine user-data config as well. That way you can build machines with different cloud-init settings.

## Links
https://cloudinit.readthedocs.io/en/latest/topics/datasources/nocloud.html

