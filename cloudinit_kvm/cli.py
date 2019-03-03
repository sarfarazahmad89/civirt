''' Cli wrapper for cloudinit_kvm using Click '''
from __future__ import print_function
import click
import yaml
from cloudinit_kvm import functions
# pylint: disable=W0614

@click.group()
def civirt():
    '''
    utility to build virtual machines using nocloud isos and cloudimgs.
    '''
    pass

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
def build(configfile):
    '''
    provision a bunch of virtual machines using config file.
    '''
    functions.provision_yaml(configfile)

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
def cleanup(configfile):
    '''
    remove previously provisioned virtual machines.
    '''
    functions.cleanup_yaml(configfile)

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
@click.option('--fqdn', '-f', help="fqdn for the vm", required=True)
@click.option('--ip', '-i', help="ip address for the vm", required=True)
def build_instance(configfile, fqdn, ip):
    '''
    quickly spin up a single instance using "common" settings.
    '''
    with open(configfile, 'r') as conf_fd:
        config = yaml.load(conf_fd)
    vm_config = config['common']
    vm_config['fqdn'] = fqdn
    vm_config['ipaddr'] = ip
    functions.update_metadata(vm_config)
    vm = functions.VirtualMachine(**vm_config)
    vm.build()

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
@click.option('--fqdn', '-f', help="fqdn for the vm", required=True)
@click.option('--ip', '-i', help="ip address for the vm", required=True)
def cleanup_instance(configfile, fqdn, ip):
    '''
    delete a previously spun up instance with all its files.
    '''
    with open(configfile, 'r') as conf_fd:
        config = yaml.load(conf_fd)
    vm_config = config['common']
    vm_config['fqdn'] = fqdn
    vm_config['ipaddr'] = ip
    functions.update_metadata(vm_config)
    vm = functions.VirtualMachine(**vm_config)
    vm.delete()

civirt.add_command(build)
civirt.add_command(cleanup)
civirt.add_command(build_instance)
civirt.add_command(cleanup_instance)
