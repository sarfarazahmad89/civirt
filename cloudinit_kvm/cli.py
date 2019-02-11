import logging
import click
import sys
from functions import *

# pylint: disable=W0614

LOGGER = logging.getLogger()

@click.group()
def hostsmanage():
    _setup_logging()

@hostsmanage.command()
@click.option('--fqdn', '-f', help="FQDN for the entry.", required=True)
@click.option('--ipaddr', '-i', help="IP for the entry.", required=True)
def add_entry(fqdn, ipaddr):
    '''add entry to 'hosts' file.'''
    try:
        add_hostsentry(fqdn, ipaddr)
    except IOError as err:
        LOGGER.critical('action failed with : %s', err)


@hostsmanage.command()
@click.option('--fqdn', '-f', help="FQDN for the entry.", required=True)
def delete_entry(fqdn):
    '''delete entry from 'hosts' file, by <fqdn>'''
    try:
        delete_hostsentry(fqdn)
    except IOError as err:
        LOGGER.critical('action failed with : %s', err)


@hostsmanage.command()
def show_entries():
    '''show all current added entries in /etc/hosts.'''
    show_hostsentries()


@click.command()
@click.option('--userdata', help="path to userdata file.", required=True)
@click.option('--metadata', help="path to metadata file.", required=True)
@click.option('--outdisk', help="path to the output iso file.", required=True)
def createiso(userdata, metadata, outdisk):
    '''Create a cloud-init iso from {user-/meta-}data files.'''
    _setup_logging()
    create_iso(userdata, metadata, outdisk)


@click.command()
@click.option('--bdisk', help="path to the backing disk image.", required=True)
@click.option('--outdisk', help="path to the output disk image.", required=True)
@click.option('--size', help="size of the output disk image. Use K/M/G.")
def createdsk(bdisk, outdisk, size):
    '''Create a qcow2 disk using a backing disk.'''
    _setup_logging()
    create_disk(bdisk, outdisk, size)


@click.group()
def civirt():
    pass

@civirt.command()
@click.option('--configfile', '-c', help="path to the yaml file.", required=True)
def createyaml(configfile):
    '''
    Provision virtual machines from a yaml file.
    '''
    _setup_logging()
    provision_yaml(configfile)


@click.group()
@click.option('--bdisk', '-b', help="path to backing disk", required=True)
@click.option('--bsize', '-s', help="size of virtual machine disk", required=True)
@click.option('--name', '-n', help=" name of virtual machine", required=True)
@click.option('--userdata', '-u', help="path to nocloud user-data file", required=True)
@click.option('--metadata', '-m', help="path to nocloud meta-data file", required=True)
@click.option('--cpu', '-u', help="number of cpu threads to allocate, default 1 CPU")
@click.option('--mem', '-m', help="size of ram to allocate to VM, unit is MB, this option"
              " accepts integers only, defaults to 512")
@click.option('--savedir', '-o', help="directory to keep all the VM files.", required=True)
def createvm():
    '''
    Provision a virt-machine using {user,meta}data/cloud-imgs
    '''
    _setup_logging()
    provision(name, bdisk, userdata, metadata, savedir,
              cpu=1, mem=512, size=None)


def _setup_logging(loglevel=logging.INFO):
    logformat = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setFormatter(logformat)
    LOGGER.addHandler(stdouthandler)
    LOGGER.setLevel(loglevel)

civirt.add_command(createvm)
civirt.add_command(createyaml)
