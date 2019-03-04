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
def delete(configfile):
    '''
    remove previously provisioned virtual machines.
    '''
    functions.delete_yaml(configfile)


@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
@click.option('--fqdn', '-f', help="fqdn for the vm", required=True)
@click.option('--ipaddr', '-i', help="ip address for the vm", required=True)
def build_instance(configfile, fqdn, ipaddr):
    '''
    quickly spin up a single instance using "common" settings.
    '''
    functions.build_instance(configfile, fqdn, ipaddr)

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
@click.option('--fqdn', '-f', help="fqdn for the vm", required=True)
def delete_instance(configfile, fqdn):
    '''
    delete a single running instance
    '''
    functions.delete_instance(configfile, fqdn)

civirt.add_command(build)
civirt.add_command(delete)
civirt.add_command(build_instance)
civirt.add_command(delete_instance)
