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
def start():
    """
    Starts all nodes.
    """
    gns3.start()


# make subcommands available
if __name__ == "__main__":
    cli()
