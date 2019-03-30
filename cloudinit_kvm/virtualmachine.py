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
        self.netconfig = None
        self.domainxml = None


    def __str__(self):
        return yaml.dump(self.__dict__, default_flow_style=False)


    def build(self):
        '''
        calls all other relevant methods to start the virtual machine
        '''

        LOGGER.info("%s : output directory doesn't exist. creating it ..", self.fqdn)
        if not os.path.isdir(os.path.abspath(self.outdir)):
            os.makedirs(self.outdir)

        # Create backing disk
        self.create_disk()
        # Add hostsentry
        self.add_hostsentry()
        # Generate xml with virt-install
        self.create_vm()
        # Create nocloud iso
        self.create_iso()
        # Attach the iso file
        self.attach_iso()
        # Start the VM
        self.start_vm()


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
        if os.listdir(self.outdir) is None:
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
        cmd = ['virt-install', '--import', '--os-variant=rhel7.0', '--noautoconsole',
               '--network', 'bridge=virbr0,model=virtio', '--vcpus', str(self.cpu),
               '--ram', str(self.mem), '--print-xml']

        cmd.extend(['--name', self.fqdn])
        cmd.extend(['--disk', os.path.abspath(self.outdisk)+',format=qcow2,bus=virtio'])
        try:
            # generate the xml configuration
            self.domainxml = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : failure generating libvirt xml. command output: %s',
                            self.fqdn, err.output)
            raise

        # create the virtual machine 
        cmd_to_define_vm = subprocess.Popen(["virsh", "define", "/dev/stdin"], 
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
        cmd_to_define_vm.stdin.write(self.domainxml)
        cmd_to_define_vm.communicate()
        cmd_to_define_vm.wait()
        if cmd_to_define_vm.returncode != 0:
            LOGGER.critical('%s : failure creating virtual machine using virsh.',
                            self.fqdn)
            raise subprocess.CalledProcessError
        else:
            LOGGER.info('%s : virtual machine defined/created in libvirt.', self.fqdn)


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

    #TODO: this should probably be a global function.
    def _gen_networkconfig(self):
        '''
        Builds NoCloud network config for the given IP
        '''
        # Code to pull in mac address
        pattern = re.compile('<mac address=(.*)/>')
        try:
            macaddr = pattern.search(self.domainxml).groups()[0]
        except AttributeError:
            LOGGER.critical('%s : no mac address found in vm\'s xml. '
                            'This will result in broken network config.')
            # We continue though network config is broken. There could be
            # other VMs to provision.
            pass

        self.netconfig = {'version': 2,
                          'ethernets':
                          {'interface0': {
                              'match': {'macaddress': macaddr.strip('\"')},
                              'set-name': 'eth0',
                              'addresses': [str(self.ipaddr)+'/24'],
                              'gateway4': '192.168.122.1',
                              'nameservers' : {'addresses': ['192.168.122.1']}
                           }
                          }
                         }

    def create_iso(self):
        '''
        create a cloud-init iso from {user/meta}data dictionaries.
        '''
        # Ready network config
        self._gen_networkconfig()

        # Create an ISO
        iso = pycdlib.PyCdlib()
        # Set label to "cidata"
        iso.new(interchange_level=3,
                joliet=True,
                sys_ident='LINUX',
                vol_ident='cidata'
               )
        metadata = yaml.dump(self.metadata, default_style="\\")
        userdata = "#cloud-config\n" + yaml.dump(self.userdata, default_style="\\")
        netconfig = yaml.dump(self.netconfig, default_style="\\")

        # Calculate sizes of the files to write.
        msize = len(metadata)
        usize = len(userdata)
        nwsize = len(netconfig)

        # Add files to iso
        iso.add_fp(BytesIO(userdata), usize, '/USERDATA.;1', joliet_path='/user-data')
        iso.add_fp(BytesIO(metadata), msize, '/METADATA.;1', joliet_path='/meta-data')
        iso.add_fp(BytesIO(netconfig), nwsize, '/NETWORKCONFIG.;1', joliet_path='/network-config')

        try:
            # Write the iso file
            iso.write(self.ci_iso)
            LOGGER.info('%s : created nocloud iso at %s', self.fqdn, self.ci_iso)
        except IOError:
            LOGGER.critical('%s : failed to create nocloud iso at %s',
                            self.fqdn, self.ci_iso)
            raise


    def attach_iso(self):
        '''
        Attach created iso to the virtual machine
        '''
        cmd = ['virsh', 'attach-disk', '--persistent', self.fqdn, self.ci_iso,
               'hdc', '--type', 'cdrom']
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            LOGGER.info('%s : nocloud iso attached to the vm.', self.fqdn)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : failure attaching iso. command output: %s',
                            self.fqdn, err.output)
            raise


    def start_vm(self):
        '''
        Start the virtual machine
        '''
        cmd = ['virsh', 'start', self.fqdn]
        try:
            subprocess.check_call(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            LOGGER.info('%s : vm successfully started', self.fqdn)
        except subprocess.CalledProcessError as err:
            LOGGER.critical('%s : failure starting virtual machine. command output: %s',
                            self.fqdn, err.output)
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
