#!/usr/bin/env python3
"""
The main user entrypoint.
Usage is

    python manage.py <global options> <command> <command options>

"""

import click
from gns3_bgp_frr import configs, gns3

# define global group to make subcommands available
@click.group()
def cli():
    pass


@cli.command()
def start_all():
    """
    Starts all nodes.
    """
    gns3.start_all(log=True)


@cli.command()
def stop_all():
    """
    Stops all nodes.
    """
    gns3.stop_all(log=True)


@cli.command()
def set_up():
    """
    Enable the required OSPF and BGP daemons on each node.
    Run twice or restart GNS3 after running once if one of them doesn't start (check a
    node with `ps -a`)
    """
    gns3.set_daemon_state_all(True, log=True)


@cli.command()
def reset():

    """
    Resets the entire project to default. If you configure something in the project, add
    a reset_<thing>() function to undo it and call it from here.
    """
    gns3.set_daemon_state_all(False, log=True)
    configs.clear_frr_configs(log=True)
    configs.clear_alpine_config(log=True)


@cli.command()
def generate_configs():
    """
    Automatically generate addresses then create FRR configs for each router, in the
    `<project root>/generated` folder.
    Automatically starts the nodes (required to avoid errors when reading links).
    """
    configs.generate_configs(log=True)


@cli.command()
def apply_configs():
    """
    Apply the generated configs to the devices.
    Configs must have been generated first.
    Automatically starts the nodes.
    """
    configs.apply_frr_configs(log=True)
    configs.configure_alpine(log=True)


# make subcommands available
if __name__ == "__main__":
    cli()
