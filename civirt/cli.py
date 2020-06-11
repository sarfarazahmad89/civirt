'''The cli module '''
import click
from civirt import orchestrate
# pylint: disable=W0614

@click.group()
def main():
    '''
    Utility to build virtual machines using cloud-init and qcow2 images.
    '''
    pass

@main.command()
@click.option('--config', '-c', help="Path to the config file.",
              required=True)
@click.option('--keep', '-k', help="Don't revert/undo changes on any failures.",
              is_flag=True, default=False)
def create(config, keep):
    '''
    Create virtual machines.
    '''
    if keep:
        try:
            orchestrate.create(config)
        except Exception:
            orchestrate.delete(config)
    else:
        orchestrate.create(config)

@main.command()
@click.option('--config', '-c', help="Path to the config file.",
              required=True)
def recreate(config):
    '''
    Delete everything from previous run and create afresh.
    '''
    orchestrate.delete(config)
    orchestrate.create(config)


@main.command()
@click.option('--config', '-c', help="Path to the config file.",
              required=True)
def delete(config):
    '''
    Delete virtual machines.
    '''
    orchestrate.delete(config)

main.add_command(create)
main.add_command(recreate)
main.add_command(delete)
