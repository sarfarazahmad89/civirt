# civirt
civirt is barebones, quite-stupid *_vagrant-lookalike_* except it,

* let's you use qcow2 cloud-images that most distributions make readily available online, so you are not limited to vagrant's boxes.
* uses [cloudinit](https://cloudinit.readthedocs.io/en/latest/) to configure your vms. More specifically, it uses cloudinit's ['NoCloud'](https://cloudinit.readthedocs.io/en/latest/topics/datasources/nocloud.html) feature and simply compiles an iso file comprising of {user,meta}-data and attaches the iso file to your virtual machine with which the vm bootstraps on first boot. You don't need a metadata service running to use cloudinit ;)
* can use qcow2 backing-disk feature so that the new harddrives for your vms only record the deltas and remain quite small in size.


### Requirements
requires pycdlib, yaml and click

### Limitations
I didn't really much care about the networking bits so it just assigns the ip to the one interface that ```virt-install``` command adds by default.
Again the default libvirt bridge is 192.168.122.0/24 and it expects the ip address
to be from that subnet.
 
### Installing

1. Clone the git repo.
2. Run pip install
```
git clone https://github.com/sarfarazahmad89/civirt
pip install civirt
```

## Usage
```
Usage: civirt [OPTIONS] COMMAND [ARGS]...

  Utility to build virtual machines using cloud-init and qcow2 images.

Options:
  --help  Show this message and exit.

Commands:
  create    Create virtual machines.
  delete    Delete virtual machines.
  recreate  Delete everything from previous run and create afresh.
```

### Sample config
```
---    # Sample config
project: 'my-dockerlab'
common:
  backingdisk: /home/guest/Desktop/debian-10.4.1-20200515-openstack-amd64.qcow2
  size: 10G
  directory: /home/guest/Desktop/my-dockerlab
  cpu: 1
  mem: 512
  userdata:
    # cloud-config
    preserve_hostname: false
    password: cloudimg
    ssh_pwauth: true
    users:
      - name: local
        groups: wheel
        sudo: ['ALL=(ALL) NOPASSWD:ALL']
        ssh_authorized_keys:
          - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDE4g1A0NaYp16wpa624yk1gvric4oeTkgdG7rojH2zzYFURAt612T4obzFLir55QCmWvjsbRDtEK9N1ZW8oFY+REPgSczJFqfnoLeDv3iPy/a+TK6yG8WuhfiKlk519G8c021fduqo7njiY5T/wyRcyBefr5ogfALr5F5irsJcQjv62H+9DTJmS5lYf2ge1OggVCYtEO1k8pqy9xAKc9R/yMcKO9arTtfYYeGgkTKBLPa/83DS5pNDYAJ/DEY2Efx8B7npW5KwT6cKKHA/SjGd45VUsSEkU747VkT5zP5ImXYfjI7cMMxJBm7KQboBWeCDLYSmExtEG7TY9rCwnZ9VOEgivIDT6CauA7N2Db2YnQih92xs2D+ryRLjEar580Z40FaUCCqVAZlJSIZqw379bv3KVLClImLHxzKU7v1a4j29SOrmsK7h2gTAsVcl4r6q9XfQJ7bj9YG4z9TSf16pMbXa08czXBQMyy+41JXVD+SQjnFWebr/o3tGaGjAnHE= ahmad@mymachine
    runcmd:
      - 'sudo apt update; sudo apt-get install apt-transport-https ca-certificates -y'
      - 'sudo apt install curl gnupg-agent software-properties-common -y '
      - 'curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -'
      - 'apt-key fingerprint 0EBFCD88 -y'
      - 'add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"'
      - 'sudo apt-get install docker-ce docker-ce-cli containerd.io'
vms:
  - fqdn: docker101.lab                 # fqdn for the virtual machine
    ipaddr: 192.168.122.100             # ipaddr for the virtual machine
  - fqdn: docker102.lab
    ipaddr: 192.168.122.50
```

### Notes
* Settings common to all the vm's can be placed under the 'common' dictionary. Same
set of keys can be overridden for each individual vm as well. (under the vms list)

* Descriptions of the key-value pairs are below..
```
fqdn:     	# FQDN of the virtual machine.
ipaddr:   	# IPADDR of the virtual machine assumed to be from default virbr0
cpu:		# No. of cpus to allocate to the VM.
mem:    	# Amount of memory to allocate in megabytes (accepts an integer)
backingdisk:    # Path to the backing qcow2 disk image.
size:     	# Size to allocate to the new disk (Use units G,M,K)
directory:      # Directory to place all relevant files. (qcow2/iso)
userdata: 	# Cloudinit's user-data

```


## Links
https://cloudinit.readthedocs.io/en/latest/topics/datasources/nocloud.html
