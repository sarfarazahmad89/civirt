from __future__ import print_function
import os
import re
import logging
import subprocess
import pycdlib
import yaml
from jsonschema import validate, FormatChecker, ValidationError


LOGGER = logging.getLogger(__name__)
HOSTSFILE = "/etc/hosts"
DEFAULT_ISOPATH = os.path.join(os.getcwd(), 'cidata.iso')
HOSTS_ENTRY_SUFFIX = "\t# added by cloudinit-kvm"
CONFIG_SCHEMA = '''
$schema: 'http://json-schema.org/draft-04/schema#'
type: object
title: "configfile for cloudinit-kvm"

properties:
    'project': {'type': "string"}
    'vms':
        type: "array"
        items: { "$ref": "#/definitions/virtualmachine"}
required: ['vms']

definitions:
    "virtualmachine":
        type: object
        properties:
            'name': {'type': 'string', 'pattern': '.*\\..*'}
            'cpu': {'type': 'number'}
            'ipaddr': {'type': 'string', 'format': 'ipv4'}
            'mem': {'type': 'number'}
            'backingdisk': {'type': 'string'}
            'disksize': {'type': 'string'}
            'userdata': {'type': 'string'}
            'metadata': {'type': 'string'}
            'savedir': {'type': 'string'}
        required: ['name', 'ipaddr', 'backingdisk', 'userdata', 'metadata', 'savedir']
'''

def add_hostsentry(fqdn, ipaddr):
    '''
    Add an entry to the hosts file.
    :param fqdn: fqdn for the hosts entry
    :param ipaddr: ipaddr for the hosts entry
    '''
    entry = "{} {} {} {}".format(ipaddr, fqdn, fqdn.split('.', 1)[0],
                                 HOSTS_ENTRY_SUFFIX)
    try:
        with open(HOSTSFILE, 'r+') as fhandle:
            for line in fhandle:
                if _is_fqdn_in_line(fqdn, line):
                    LOGGER.warn('entry for "%s" already exists. skipping ..', fqdn)
                    return False

            fhandle.write(entry+'\n')
            LOGGER.info('added "%s" to %s', entry, HOSTSFILE)
            return True
    except IOError as err:
        LOGGER.critical('unable to edit hosts file. %s', err)
        raise


def create_vm(name, disk, ci_iso, cpu=1, mem=512):
    '''
    Create libvirt/kvm domain using virt-install
    :param name: name of the virtual machine
    :param disk: qcow2 disk image for the virtual machine
    :param name: name of the virtual machine
    '''
    cmd = ['virt-install', '--import', '--os-variant=rhel7', '--noautoconsole',
           '--network', 'bridge=virbr0,model=virtio', '--vcpus', str(cpu),
           '--ram', str(mem)]

    cmd.extend(['--name', name])
    cmd.extend(['--disk', os.path.abspath(disk)+',format=qcow2,bus=virtio'])
    cmd.extend(['--disk', os.path.abspath(ci_iso)+',device=cdrom'])

    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        LOGGER.info('created virtual machine: %s', name)
    except subprocess.CalledProcessError as err:
        LOGGER.critical('failed to start virtual machine. output: %s',
                        err.output)
        raise



def create_disk(backingdisk, outdisk, size=None):
    '''
    Create a qcow2 disk for the virtual machine.

    :param backingdisk: path to backing qcow2 image.
    :param outdisk: path to output qcow2 image.
    :param size: size of the output qcow2 image. (default: same size
                 as backing disk.)
    '''

    cmd = ['qemu-img', 'create', '-b', backingdisk, '-f', 'qcow2',
           '-F', 'qcow2', outdisk]
    if size:
        cmd.append(size)
    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        LOGGER.info('created qcow2 disk at %s', os.path.abspath(outdisk))
    except subprocess.CalledProcessError as err:
        LOGGER.critical('failure creating qcow2 disk. command output: %s',
                        err.output)
        raise


def create_iso(userdata, metadata, outdisk):
    '''
    Create a cloud-init iso from {user-/meta-}data files.

    :param userdata: path to userdata file
    :type userdata: str
    :param metadata: path to metadata file
    :type metadata: str
    :param outdisk: path to the output file, defaults to <cwd>/cidata.iso
    :type outdisk: str
    '''

    # Create an ISO
    iso = pycdlib.PyCdlib()
    outdisk = os.path.abspath(outdisk)
    # Set label to "cidata"
    iso.new(interchange_level=3,
            joliet=True,
            sys_ident='LINUX',
            vol_ident='cidata'
           )

    def file_exception_reader(filename):
        try:
            filereader = open(filename, 'rb')
            return filereader
        except IOError as err:
            LOGGER.critical('could not read %s. %s', filename, err)
            raise

    # File handles for {user,meta}-data
    udata_fd = file_exception_reader(userdata)
    udata_size = len(udata_fd.read())
    udata_fd.seek(0)

    mdata_fd = file_exception_reader(metadata)
    mdata_size = len(mdata_fd.read())
    mdata_fd.seek(0)

    iso.add_fp(udata_fd, udata_size, '/USERDATA.;1', joliet_path='/user-data')
    iso.add_fp(mdata_fd, mdata_size, '/METADATA.;1', joliet_path='/meta-data')
    try:
        iso.write(outdisk)
        LOGGER.info('created nocloud iso at %s', outdisk)
    except IOError:
        LOGGER.critical('failed to create nocloud iso at %s', outdisk)
        raise


def delete_hostsentry(fqdn):
    '''
    Delete an entry from the hosts file.
    '''
    # TODO: Poor logic. Complains on unable to write to file even if entry
    #       doesn't exist
    match = False
    with open(HOSTSFILE, 'r+') as hstreader:
        hstreader = open(HOSTSFILE, 'r+')
        all_entries = hstreader.readlines()
        hstreader.seek(0)
        for line in all_entries:
            if not line.endswith(HOSTS_ENTRY_SUFFIX+'\n'):
                hstreader.write(line)
            else:
                if _is_fqdn_in_line(fqdn, line):
                    LOGGER.info('removed entry "%s" for %s', line.rstrip(),
                                HOSTSFILE)
                    match = True
                else:
                    hstreader.write(line)
        hstreader.truncate()
        if not match:
            LOGGER.warn('no entry found for %s in /etc/hosts', fqdn)


def delete_file(file):
    '''
    Delete file on disk.
    :param file: file to delete
    :type file: str
    '''
    try:
        os.remove(file)
        LOGGER.info('removed the disk at %s', file)
    except IOError as err:
        LOGGER.critical('failed to remove file from disk. %s', err)
        raise


def provision_yaml(configfile):
    '''
    Provision VMs from a yaml file.
    '''

    try:
        with open(configfile, 'r') as configfd:
            config = yaml.load(configfd)
            validate(config, yaml.load(CONFIG_SCHEMA),
                     format_checker=FormatChecker())
            LOGGER.info('__readconfig__ - configuration valid. will provision vms now ..')
    except (IOError, ValidationError, yaml.YAMLError) as err:
        LOGGER.critical('failure reading configuration file. %s', err)
        raise

    # now that the config looks alright, create vms
    for vm in config['vms']:
        try:
            provision(**vm)
        except Exception as err:
            LOGGER.critical('%s - provisioning failed. ', vm['name'])


def provision(name, ipaddr, backingdisk, userdata, metadata, savedir,
              cpu=1, mem=512, disksize=None):
    '''
    Provision VMs from nocloud isos and cloud imgs.
    '''
    LOGGER.info('%s - start provisioning ', name)
    # If "savedir" doesn't exist, create it
    savedir = os.path.abspath(savedir)
    if not os.path.isdir(savedir):
        LOGGER.info("%s - savedir doesn't exist. creating it.", name)
        os.mkdir(savedir)

    # Create cidata.iso
    LOGGER.info('%s - creating nocloud iso .. ', name)
    ci_iso = os.path.join(savedir, 'cidata.iso')

    create_iso(userdata, metadata, ci_iso)

    # Create qcow2 image
    LOGGER.info('%s - creating qcow2 disk .. ', name)
    backingdisk = os.path.abspath(backingdisk)
    outdisk = os.path.join(savedir, name+".qcow2")
    create_disk(backingdisk, outdisk, disksize)

    # Add entry to /etc/hosts
    LOGGER.info('%s - adding entry to hosts file .. ', name)
    add_hostsentry(name, ipaddr)

    # Now that qcow2/iso files have been created, provision the VM
    create_vm(name, outdisk, ci_iso, cpu, mem)


def show_hostsentries():
    '''
    print all current entries in hosts file
    '''
    print("-- currently managed entries in {} --  \n ".format(HOSTSFILE))
    ourentries = False
    with open(HOSTSFILE, 'r') as fhandle:
        for line in fhandle:
            if line.endswith(HOSTS_ENTRY_SUFFIX+'\n'):
                print(line, end='')
                ourentries = True
    if not ourentries:
        print('-- no entries --')



def _is_fqdn_in_line(fqdn, line):
    '''
    Check whether line matches the fqdn or not.
    '''
    regex = '\t| '
    fqdn_on_line = re.split(regex, line)
    if fqdn == fqdn_on_line[1]:
        return True
    return False
