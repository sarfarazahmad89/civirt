cloudinit-kvm lets you easily provision linux virtual machines on your 
personal laptop or workstation using cloud-init's nocloud isos and 
cloud disk images(qcow2).

It is rather dumb and was intended as a learning exercise.

It lets you describe a set of vms belonging to a pet project in a yaml
file. You could club puppet, cloud-init's nocloud files and the config
here to have your virtual machines reproducible (as code).


Usage: civirt [OPTIONS] COMMAND [ARGS]...

  utility to build virtual machines using nocloud isos and cloudimgs.

Options:
  --help  Show this message and exit.

Commands:
  build             provision a bunch of virtual machines using config file.
  build-instance    quickly spin up a single instance using "common"...
  cleanup           remove previously provisioned virtual machines.
  cleanup-instance  delete a previously spun up instance with all its files.
 
