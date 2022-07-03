#!/usr/bin/env python3
"""
The main user entrypoint.
Usage is

    python manage.py <global options> <command> <command options>

"""

import click
from gns3_bgp_frr import gns3

# define global group to make subcommands available
@click.group()
def cli():
    pass


@cli.command()
def start_all():
    """
    Starts all nodes.
    """
    gns3.start_all()


@cli.command()
def stop_all():
    """
    Stops all nodes.
    """
    gns3.stop_all()


@cli.command()
def reset():
    """
    Undoes all automated changes.
    """
    gns3.reset_all()


@cli.command()
def set_up():
    """
    Enable the required OSPF and BGP daemons on each node.
    Run twice or restart GNS3 after running once if one of them doesn't start.
    """
    gns3.set_daemon_state(True)


# make subcommands available
if __name__ == "__main__":
    cli()
