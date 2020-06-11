import os
import re
import shlex
import logging
import subprocess
from io import BytesIO
import pycdlib
import yaml
from civirt.exceptions import *

LOGGER = logging.getLogger(__name__)
HOSTSFILE = "/etc/hosts"
HOSTS_ENTRY_SUFFIX = "# added by civirt"

class VirtualMachine:
    def __init__(self, settings):
        # Update domain settings
        self.domain = {'fqdn': settings['fqdn'],
                       'ipaddr': settings['ipaddr'],
                       'cpu': settings.get('cpu', 1),
                       'mem': settings.get('mem', 512)}
        self.directory = settings['directory']

        # Copy cloudinit settings to a dedicated dict.
        self.cloudinit = {'metadata': settings['metadata'],
                          'userdata': settings['userdata']}

        # Save the fully qualified paths for qcow2/iso files in self.disks
        self.qcow2 = {}
        self.qcow2['bdisk'] =  settings['backingdisk']
        self.qcow2['size'] = settings['size']
        self.qcow2['path'], self.cloudinit['path'] = [os.path.join(settings['directory'],
                                                      f"{settings['fqdn']}.{disk}")
                                                      for disk in ['qcow2', 'iso']]

        # The 'entry' to be added to the HOSTSFILE for this vm
        self.entry = (f"{self.domain['ipaddr']}\t{self.domain['fqdn']}\t"
                      f"{self.domain['fqdn'].split('.', 1)[0]}\t"
                      f"{HOSTS_ENTRY_SUFFIX}")


    def __repr__(self):
        return yaml.dump(self.__dict__, default_flow_style=False)


    def create(self):
        '''
        Provision the virtual machine
        '''
        # Update disk settings
        if not os.path.isdir(self.directory):
            os.makedirs(self.directory)

        # Add entry to hosts file if it doesnt exist already.
        self._add_entry()
        # Create backing disk
        self.create_disk()
        # Generate xml with virt-install
        self.create_vm()
        # Ready network config that is to be written to NoCloud Iso
        self.generate_netdata()
        # Create nocloud iso
        self.create_iso()
        # Attach the iso file
        self.attach_iso()
        # Start the VM
        self.start_vm()


    @staticmethod
    def domain_is_defined(domain):
        cmd = ['virsh', 'dumpxml', domain]
        return subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode

    def delete(self):
        '''
        Delete the virtual machine
        '''
        # Libvirt cleanup
        if not VirtualMachine.domain_is_defined(self.domain['fqdn']):
            self.cleanup_libvirt()
        else:
            LOGGER.info(f"{self.domain['fqdn']} - Libvirt needs no cleanup.")

        # Remove qcow2 disk
        if os.path.isfile(self.qcow2['path']):
            self.delete_file(self.qcow2['path'])
        else:
            LOGGER.info(f"{self.domain['fqdn']} - Qcow2 disk does not exist.")

        # Remove nocloud ISO
        if os.path.isfile(self.qcow2['path']):
            self.delete_file(self.cloudinit['path'])
        else:
            LOGGER.info(f"{self.domain['fqdn']} - Cloudinit iso does not exist.")

        # Remove entry from hostsfile
        self._delete_entry()

        # Remove the output directory
        if os.listdir(self.directory) is None:
            os.rmdir(self.directory)
        LOGGER.info(f"{self.domain['fqdn']} - Successfully deleted. ")

    def _entryexists(self):
        '''
        Check whether entry exists in /etc/hosts or not.
        '''
        with open(HOSTSFILE, 'r') as hostfd:
            hosts = hostfd.readlines()
        return True if f'{self.entry}\n' in hosts else False


    def _add_entry(self):
        fqdn = self.domain['fqdn']
        # entry is just for logging purposes. newline is stripped away.
        if not self._entryexists():
            try:
                with open(HOSTSFILE, 'a') as hosts_fd:
                    hosts_fd.write(f'{self.entry}\n')
                    LOGGER.info(f'{fqdn} - Added "{self.entry}" to {HOSTSFILE}')
            except IOError as err:
                LOGGER.exception(f'{fqdn} - Unable to edit hosts file. {err}')
                raise
            except Exception as err:
                LOGGER.exception(f'{fqdn} - Exception adding {self.entry} to hosts file.'
                                 f'{err}')
                raise
        else:
            LOGGER.warning(f'{fqdn} - Required entry already present. '
                           f'Will not add "{self.entry}" to hosts file')


    def _delete_entry(self):
        fqdn = self.domain['fqdn']
        removed = False
        # entry is just for logging purposes. newline is stripped away.
        try:
            with open(HOSTSFILE, 'r+') as hostfd:
                hosts = hostfd.readlines()
                for index, entry in enumerate(hosts[:]):
                    if entry == f'{self.entry}\n':
                        removed = True
                        hosts.pop(index)
                        LOGGER.info(f'{fqdn} - Removing {self.entry} from hosts'
                                    f'file.')
                if removed:
                    hostfd.seek(0)
                    hostfd.writelines(hosts)
                    hostfd.truncate()
                else:
                    LOGGER.info(f'{fqdn} - No entries matching "{self.entry}" '
                                f'were found.')
        except IOError as err:
            LOGGER.exception(f'{fqdn} - Unable to edit hosts file. {err}')
            raise
        except Exception as err:
            LOGGER.exception(f'{fqdn} - Exception removing entry from hosts '
                             f'file. {err}')
            raise


    def create_disk(self):
        '''
        create a qcow2 disk for the virtual machine.
        '''
        if not os.path.isfile(self.qcow2['bdisk']):
            raise BackingDiskException(f"{self.domain['fqdn']} - Backing disk at "
                                       f"{self.qcow2['bdisk']} does not exist.")

        cmd = ['qemu-img', 'create', '-b', self.qcow2['bdisk'], '-f', 'qcow2',
               '-F', 'qcow2', self.qcow2['path']]
        # Append the new disk's size to the qemu-img, if configured.
        if self.qcow2['size']:
            cmd.append(self.qcow2['size'])
        try:
            subprocess.check_call(cmd, stderr=subprocess.STDOUT)
            LOGGER.info(f"{self.domain['fqdn']} - Created qcow2 disk at "
                        f"{self.qcow2['path']}.")
        except subprocess.CalledProcessError as err:
            LOGGER.critical(f"{self.domain['fqdn']} : Exception creating qcow2 disk at "
                            f"{self.qcow2['path']} "
                            f"Command output: {str(err.output)}")
            raise


    def create_vm(self):
        '''
        create libvirt/kvm domain using virt-install
        '''
        fqdn = self.domain['fqdn']
        cmd = ['virt-install', '--import', '--os-variant=rhel7.0',
               '--noautoconsole', '--network', 'bridge=virbr0,model=virtio',
               '--vcpus', str(self.domain['cpu']), '--ram', str(self.domain['mem']),
               '--print-xml']

        cmd.extend(['--name', self.domain['fqdn']])
        cmd.extend(['--disk', os.path.abspath(self.qcow2['path'])+',format=qcow2,bus=virtio'])
        try:
            # generate the xml configuration
            self.domainxml = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            #self.domainxml.decode('utf-8')
        except subprocess.CalledProcessError as err:
            LOGGER.critical(f'{fqdn} - Failure generating libvirt xml. '
                            f'Cmd output: {str(err.output)}')
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
            LOGGER.critical(f'{fqdn} - Exception creating virtual machine '
                            f'using virsh.')
            raise subprocess.CalledProcessError
        else:
            LOGGER.info(f'{fqdn} : Successfully defined virtual machine'
                        f' using virsh.')


    def generate_netdata(self):
        '''
        Builds NoCloud network config for the given IP
        '''
        # Code to pull in mac address
        pattern = re.compile('<mac address=(.*)/>')
        try:
            macaddr = pattern.search(self.domainxml.decode('utf-8')).groups()[0]
        except AttributeError:
            LOGGER.critical('%s : no mac address found in vm\'s xml. '
                            'This will result in broken network config.')
            raise NoMacAddressException

        self.cloudinit['netdata'] = {
            'version': 2,
            'ethernets': {
                'interface0': {
                    'match': {'macaddress': macaddr.strip('\"')},
                    'set-name': 'eth0',
                    'addresses': [str(self.domain['ipaddr'])+'/24'],
                    'gateway4': '192.168.122.1',
                    'nameservers' : {'addresses': ['192.168.122.1']}
                    }
             }
        }


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
        metadata = yaml.dump(self.cloudinit['metadata'], default_style="\\")
        userdata = "#cloud-config\n" + yaml.dump(self.cloudinit['userdata'], default_style="\\")
        netdata = yaml.dump(self.cloudinit['netdata'], default_style="\\")

        # Calculate sizes of the files to write.
        msize = len(metadata)
        usize = len(userdata)
        nwsize = len(netdata)

        # Add files to iso
        iso.add_fp(BytesIO(f"{userdata}".encode()), usize, '/USERDATA.;1', joliet_path='/user-data')
        iso.add_fp(BytesIO(f"{metadata}".encode()), msize, '/METADATA.;1', joliet_path='/meta-data')
        iso.add_fp(BytesIO(f"{netdata}".encode()), nwsize, '/NETWORKCONFIG.;1', joliet_path='/network-config')

        try:
            # Write the iso file
            iso.write(self.cloudinit['path'])
            LOGGER.info(f"{self.domain['fqdn']} - Created nocloud iso at "
                        f"{self.cloudinit['path']}")
        except IOError:
            LOGGER.critical(f"{self.domain['fqdn']} - Failure creating the "
                            f"nocloud iso at {self.cloudinit['path']}")
            raise


    def attach_iso(self):
        '''
        Attach created iso to the virtual machine
        '''
        cmd = ['virsh', 'attach-disk', '--persistent', self.domain['fqdn'],
               self.cloudinit['path'], 'hdc', '--type', 'cdrom']
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            LOGGER.info(f"{self.domain['fqdn']} - Attached nocloud iso to the vm.")
        except subprocess.CalledProcessError as err:
            LOGGER.critical(f"{self.domain['fqdn']} - Failure attaching iso. Cmd output:"
                            f"{str(err.output)}")
            raise


    def start_vm(self):
        '''
        Start the virtual machine
        '''
        cmd = ['virsh', 'start', self.domain['fqdn']]
        try:
            subprocess.check_call(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            LOGGER.info(f"{self.domain['fqdn']} - Successfully started.")
        except subprocess.CalledProcessError as err:
            LOGGER.critical(f"{self.domain['fqdn']} - Failure starting virtual "
                            f"machine. Cmd output: {str(err.output)}")
            raise




    def delete_file(self, filepath):
        '''
        delete file on disk.
        :param filepath: file to delete
        :type filepath: str
        '''
        try:
            os.remove(filepath)
            LOGGER.info(f"{self.domain['fqdn']} -  Removed {filepath}")
        except IOError as err:
            LOGGER.critical(f"{self.domain['fqdn']} - Exception removing "
                            f"{filepath}. {err}")
            raise


    def cleanup_libvirt(self):
        '''
        stop and cleanup virtual machine config from libvirt.
        '''
        stopcmd = f"virsh destroy {self.domain['fqdn']}"
        delcmd = f"virsh undefine {self.domain['fqdn']}"

        try:
            subprocess.call(shlex.split(stopcmd), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            subprocess.check_output(shlex.split(delcmd), stderr=subprocess.STDOUT)
            LOGGER.info(f"{self.domain['fqdn']} - Stopped and undefined in "
                        f"libvirt")
        except subprocess.CalledProcessError as err:
            err_output = str(err.output.rstrip('\n'))
            LOGGER.critical(f"{self.domain['fqdn']} - Failure stopping or undefining "
                            f"virtual machine in libvirt. Cmd output: "
                            f"{err_output}")
