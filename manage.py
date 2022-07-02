#!/usr/bin/env python3
"""
The main user entrypoint.
Usage is

    python manage.py <global options> <command> <command options>

"""

import click


@click.group()
def cli():
    pass


@cli.command()
def test():
    print("should test")


if __name__ == "__main__":
    cli()