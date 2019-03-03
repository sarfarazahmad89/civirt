from setuptools import setup
setup(name='cloudinit-kvm',
      version='0.2',
      description=('Provisions VM on KVM/libvirt with cloud-init(NoCloud) isos and'
                   'cloud linux images(qcow2).'),
      author='Sarfaraz Ahmad',
      author_email='sarfaraz.ahmad@live.in',
      license='MIT',
      packages=['cloudinit_kvm'],
      install_requires=['pycdlib', 'click', 'pyyaml'],
      zip_safe=False,
      entry_points='''
        [console_scripts]
        civirt=cloudinit_kvm.cli:civirt
      ''',
)
