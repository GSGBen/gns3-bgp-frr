# gns3-bgp-frr

A lightweight GNS3 BGP lab using Free Range Routing docker containers and Python automation.
Addresses are automatically assigned to links, configs are generated and applied. WIP.

Control the entire simulation from the commandline, break it manually and reset it, or extend it with your own commands.

## Topology

![topology](images/topology.png)

## Commandline

Control is via subcommands and options sent to `manage.py`.

![commandline](images/commandline.png)

Usage: `python manage.py <global options> <command> <command options>`

## Setup

* [Install GNS3 and the GNS3 VM](https://docs.gns3.com/docs/getting-started/installation/windows)
* Open GNS3 > edit > preferences > docker containers > add a new one
  * name: `docker-frrouting-frr-8.2.2`
  * image: `frrouting/frr:v8.2.2`
  * adapters: `8`
* Add another
  * name: `alpine`
  * image: `alpine`
  * adapters: `1`
* File > import portable project > import `project.gns3project`
  * If the  import doesn't work, manually create the topology like the above
* Clone/download this project and open a PowerShell (or other) shell in the folder
* Copy `settings.example.py` to `settings.py` and fill out
* Create a virtual environment and activate it
  * `python -m venv env`
  * (PowerShell) `env/scripts/activate.ps1`
* Install dependencies
  * `pip install -r requirements.txt`

## Usage

### Start nodes

![start](images/start.png)

* Make your GNS3 and shell windows both visible
* Run `python manage.py start-all`
* Look at GNS3 - all the nodes should be starting

### Set up services

![daemons](images/daemons.png)

* Open an aux console to any FRR node
* Run `python manage.py set-up`
* Watch the console - the config file should be updated
* Once `set-up` finishes, re-open the console and run `ps -a`. You should see `ospfd` and `bgpd` running.
  * If not, run `set-up` again or restart GNS3

### Generate addresses and configs

![template](images/template.png)

* Run `python manage.py generate-configs`.
* Review the configs in the `generated/` folder
  * You should see subnets within the supernet you assigned in `settings.py` and external addressing for `asn1border` `1` and `2`
  * OSPF and iBGP will be configured for `asn1` routers
  * eBGP will be configured for border routers

### Apply configs

![config](images/config.png)

* Open an aux console to any FRR node
* Run `python manage.py apply-configs`
* Watch the console - the config should be applied through `vtysh`'s config mode

## Testing

TODO: expand.

* `python manage.py test`
* `pytest --no-header --tb=line -rA`