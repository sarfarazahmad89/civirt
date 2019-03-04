#!/usr/bin/env python2
from __future__ import print_function
import logging
import sys
import string
import random
import copy
import yaml
from virtualmachine import VirtualMachine

LOGGER = logging.getLogger() #TODO: Using the root logger sets loglevels everywhere
logformat = logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
stdouthandler = logging.StreamHandler(sys.stdout)
stdouthandler.setFormatter(logformat)
LOGGER.addHandler(stdouthandler)
LOGGER.setLevel(logging.INFO)

def update_metadata(vmsettings=None):
    '''
    Conveniently merges any metadata with ipaddr for configure_eth0
    '''
    vmsettings['metadata'] = {}
    ipaddr = vmsettings['ipaddr']
    # We only provision to the default virbr0 :/
    vmsettings['metadata']['network-interfaces'] = ('iface eth0 inet static\n'
                                                    'address {}\nnetwork '
                                                    '192.168.122.0\nnetmask '
                                                    '255.255.255.0\ngateway '
                                                    '192.168.122.1'.format(ipaddr))
    vmsettings['metadata']['instance_id'] = (vmsettings['fqdn'] +
                                             ''.join(random.choice(string.ascii_uppercase
                                                     + string.digits) for _ in range(5)))
    vmsettings['metadata']['local-hostname'] = vmsettings['fqdn']


def populate_config(configfile):
    '''
    Builds config from config file, returns a list of VirtualMachine class objects.
    '''
    vm_configs = {}
    try:
        with open(configfile, 'r') as configfd:
            config = yaml.load(configfd)
    except (IOError, yaml.YAMLError) as err:
        LOGGER.critical('failure reading configuration file. %s', err)
        raise
    for vm in config['vms']:
        try:
            # Import global settings from "common" dictionary
            vm_configs[vm['fqdn']] = {}
            # Create a deepcopy otherwise both keys end up using the same dict object
            vm_configs[vm['fqdn']] = copy.deepcopy(config.get('common'))
            vm_configs[vm['fqdn']].update(vm)
            # Add metadata to configure network
            update_metadata(vm_configs[vm['fqdn']])
            LOGGER.info('%s - configuration built ', vm['fqdn'])
        except Exception as err:
            LOGGER.exception('%s - failed to generate valid config %s', vm['fqdn'], err)
    return vm_configs


def provision_yaml(configfile):
    '''
    merge and return common/specific vm setings
    '''
    vm_configs = populate_config(configfile)
    for vm_fqdn, vm_config in vm_configs.items():
        try:
            vm = VirtualMachine(**vm_config)
            vm.build()
        except Exception as err:
            LOGGER.critical("%s : failed to provision virtual machine. Err: %s",
                            vm_fqdn, err)


def delete_yaml(configfile):
    '''
    deprovision virtual machines
    '''
    # Build config
    vm_configs = populate_config(configfile)
    for vm_fqdn, vm_config in vm_configs.items():
        try:
            vm = VirtualMachine(**vm_config)
            vm.delete()
            LOGGER.info("%s : removed virtual machine and its files.", vm_fqdn)
        except Exception:
            LOGGER.critical("%s : failed to delete virtual machine. either vm"
                            " has already been removed or its files are in use"
                            , vm.fqdn)


def _create_vm_object(configfile, fqdn, ip):
    '''
    builds a functions.VirtualMachine object from fqdn, ipaddress and common
    settings from config file.
    '''
    with open(configfile, 'r') as conf_fd:
        config = yaml.load(conf_fd)
    vm_config = config['common']
    vm_config['fqdn'] = fqdn
    vm_config['ipaddr'] = ip
    functions.update_metadata(vm_config)
    vm = functions.VirtualMachine(**vm_config)
    return vm


def build_instance(configfile, fqdn, ip):
    '''
    quickly spin up a single instance using "common" settings.
    '''
    vm = _create_vm_object(configfile, fqdn, ip)
    vm.build()


def delete_instance(configfile, fqdn, ip='0.0.0.0'):
    '''
    delete a previously spun up instance with all its files.
    '''
    vm = _create_vm_object(configfile, fqdn, ip)
    vm.delete()
