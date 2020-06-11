from setuptools import setup
setup(name='civirt',
      version='0.2',
      description=("A simpler vagrant alternative. Uses libvirt and"
                   " cloud-init to build vms. Primary advantage being that "
                   " this uses vanilla cloud qcow2 images instead of Vagrant's "
                   " boxes."),
      author='Sarfaraz Ahmad',
      author_email='sarfaraz.ahmad@live.in',
      license='MIT',
      packages=['civirt'],
      install_requires=['pycdlib', 'click', 'pyyaml'],
      zip_safe=False,
      entry_points='''
        [console_scripts]
        civirt=civirt.cli:main
      ''',
     )
