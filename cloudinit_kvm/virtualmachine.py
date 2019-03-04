"""
This module provides a 'virtual machine' class that lets you provision
virtual machines using libvirt/nocloud
"""
from __future__ import print_function
import os
import re
import shlex
import logging
import subprocess
from io import BytesIO
import pycdlib
import yaml

LOGGER = logging.getLogger(__name__)
HOSTSFILE = "/etc/hosts"
HOSTS_ENTRY_SUFFIX = "\t# added by civirt"

class VirtualMachine(object):
    '''
    A class with methods to let you do the following for each of the class objects,
    * add/remove entry to hosts file,
    * create/remove nocloud iso, qcow2 disk off of a backing disk
    * start virtual machines with the said files/features.
    '''
    def __init__(self, fqdn, ipaddr, bdisk, outdir, userdata,
                 metadata, cpu=1, mem=512, size=None):
        self.fqdn = fqdn
        self.ipaddr = ipaddr
        self.bdisk = bdisk
        self.outdir = outdir
        self.cpu = cpu
        self.mem = mem
        self.size = size
        self.userdata = userdata
        self.metadata = metadata
        self.outdir = outdir
        self.outdisk = os.path.join(os.path.abspath(outdir), fqdn+".qcow2")
        self.ci_iso = os.path.join(os.path.abspath(outdir), fqdn+"_ci.iso")


    def __str__(self):
        return yaml.dump(self.__dict__, default_flow_style=False)


    def build(self):
        '''
        calls all other relevant methods to start the virtual machine
        '''

        LOGGER.info("%s : output directory doesn't exist. creating it ..", self.fqdn)
        if not os.path.isdir(os.path.abspath(self.outdir)):
            os.makedirs(self.outdir)

        # Create nocloud iso
        self.create_iso()
        # Create backing disk
        self.create_disk()
        # Add hostsentry
        self.add_hostsentry()
        # Run virt-install
        self.create_vm()
        LOGGER.info('%s : successfully built.', self.fqdn)


    def delete(self):
        '''
        deprovision the virtual machine and cleanup
        '''
        # Libvirt cleanup
        self.cleanup_libvirt()
        # Remove qcow2 disk
        self.delete_file(self.outdisk)
        # Remove nocloud ISO
        self.delete_file(self.ci_iso)
        # Remove entry from hostsfile
        self.delete_hostsentry()
        # Remove the output directory
        if len(os.listdir(self.outdir)) == 0:
            os.rmdir(self.outdir)
        LOGGER.info('%s : successfully removed.', self.fqdn)

    def add_hostsentry(self):
        '''
        add an entry to the hosts file.
        '''
        ipaddr = self.ipaddr
        fqdn = self.fqdn
        entry = "{} {} {} {}".format(ipaddr, fqdn, fqdn.split('.', 1)[0],
                                     HOSTS_ENTRY_SUFFIX)
        try:
            with open(HOSTSFILE, 'r+') as fhandle:
                for line in fhandle:
                    if self._is_fqdn_in_line(line):
                        LOGGER.warn('%s : entry already exists. skipping ..', fqdn)
                        return False
                fhandle.write(entry+'\n')
                LOGGER.info('%s : added "%s" to %s', fqdn, entry, HOSTSFILE)
                return True
        except IOError as err:
            LOGGER.critical('%s : unable to edit hosts file. %s', fqdn, err)
            raise


    def create_vm(self):
        '''
        create libvirt/kvm domain using virt-install
        '''
        cmd = ['virt-install', '--import', '--os-variant=rhel7', '--noautoconsole',
               '--network', 'bridge=virbr0,model=virtio', '--vcpus', str(self.cpu),
               '--ram', str(self.mem)]

        cmd.extend(['--name', self.fqdn])
        cmd.extend(['--disk', os.path.abspath(self.outdisk)+',format=qcow2,bus=virtio'])
        cmd.extend(['--disk', os.path.abspath(self.ci_iso)+',device=cdrom'])

        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            LOGGER.info('%s : virtual machine successfully created', self.fqdn)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : failed to start virtual machine. output: %s',
                            self.fqdn, err.output)
            raise


    def create_disk(self):
        '''
        create a qcow2 disk for the virtual machine.
        '''
        cmd = ['qemu-img', 'create', '-b', self.bdisk, '-f', 'qcow2',
               '-F', 'qcow2', self.outdisk]
        if not os.path.isfile(self.bdisk):
            raise IOError('{} : backing disk at {} does not exist '.
                          format(self.fqdn, self.bdisk))
            #"Backing Disk doesn't exist %s", self.bdisk)
        if self.size:
            cmd.append(self.size)
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            LOGGER.info('%s : created qcow2 disk at %s', self.fqdn, self.outdisk)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : failure creating qcow2 disk. command output: %s',
                            self.fqdn, err.output)
            raise


    def create_iso(self):
        '''
        create a cloud-init iso from {user/meta}data dictionaries.
        '''
        # Create an ISO
        iso = pycdlib.PyCdlib()
        # Set label to "cidata"
        iso.new(interchange_level=3,
                joliet=True,
                sys_ident='LINUX',
                vol_ident='cidata'
               )
        metadata = yaml.dump(self.metadata, default_style="|")
        userdata = "#cloud-config\n" + yaml.dump(self.userdata, default_style="|")
        # Calculate sizes of the files to write.
        msize = len(metadata)
        usize = len(userdata)
        # Add files to iso
        iso.add_fp(BytesIO(userdata), usize, '/USERDATA.;1', joliet_path='/user-data')
        iso.add_fp(BytesIO(metadata), msize, '/METADATA.;1', joliet_path='/meta-data')
        try:
            # Write the iso file
            iso.write(self.ci_iso)
            LOGGER.info('%s : created nocloud iso at %s', self.fqdn, self.ci_iso)
        except IOError:
            LOGGER.critical('%s : failed to create nocloud iso at %s',
                            self.fqdn, self.ci_iso)
            raise


    def delete_hostsentry(self):
        '''
        delete an entry from the hosts file.
        '''
        # TODO: Poor logic. Complains on unable to write to file even if entry
        #       doesn't exist
        match = False
        with open(HOSTSFILE, 'r+') as hstreader:
            all_entries = hstreader.readlines()
            hstreader.seek(0)
            for line in all_entries:
                if not line.endswith(HOSTS_ENTRY_SUFFIX+'\n'):
                    hstreader.write(line)
                else:
                    if self._is_fqdn_in_line(line):
                        LOGGER.info('%s : removed entry from %s', self.fqdn, HOSTSFILE)
                        match = True
                    else:
                        hstreader.write(line)
            hstreader.truncate()
            if not match:
                LOGGER.warn('%s : no entry found in /etc/hosts', self.fqdn)


    def delete_file(self, filepath):
        '''
        delete file on disk.
        :param filepath: file to delete
        :type filepath: str
        '''
        try:
            os.remove(filepath)
            LOGGER.info('%s : removed the disk at %s', self.fqdn, filepath)
        except IOError as err:
            LOGGER.critical('%s : failed to remove file from disk. %s', self.fqdn,
                            err)
            raise


    def cleanup_libvirt(self):
        '''
        stop and cleanup virtual machine config from libvirt.
        '''
        stopcmd = "virsh destroy {}".format(self.fqdn)
        delcmd = "virsh undefine {}".format(self.fqdn)

        try:
            subprocess.call(shlex.split(stopcmd), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            subprocess.check_output(shlex.split(delcmd), stderr=subprocess.STDOUT)
            LOGGER.info('%s : cleaned up libvirt config.', self.fqdn)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : command returned :: %s', self.fqdn,
                            err.output.rstrip('\n'))


    def _is_fqdn_in_line(self, line):
        '''
        check whether line matches the fqdn or not.
        '''
        regex = '\t| '
        fqdn_on_line = re.split(regex, line)
        if self.fqdn == fqdn_on_line[1]:
            return True
        return False
