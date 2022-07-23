# gns3-bgp-frr

A lightweight GNS3 BGP lab using Free Range Routing docker containers and Python automation, with external connectivity.
Addresses are automatically assigned to links, configs are generated and applied. WIP.

Control the entire simulation from the commandline, break it manually and reset it, or extend it with your own commands.

## Topology

![topology](images/topology.png)

## Commandline

Control is via subcommands and options sent to `manage.py`.

![commandline](images/commandline.png)

Usage: `python manage.py <global options> <command> <command options>`

## Base Setup

* [Install GNS3 and the GNS3 VM](https://docs.gns3.com/docs/getting-started/installation/windows)
* Open GNS3 > edit > preferences > docker containers > add a new one
  * name: `docker-frrouting-frr-8.2.2`
  * image: `frrouting/frr:v8.2.2`
  * adapters: `8`
  * advanced > additional persistent directories: `/etc/frr`
    * if you can't find this during the creation), create the template then right click > edit it
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
![interface ip labels](images/interface_ip_labels.png)

* Open an aux console to any FRR node
* Run `python manage.py apply-configs`
* Watch the console - the config should be applied through `vtysh`'s config mode
* Check the GNS3 GUI - all interface labels should now show IPs

**Note**: router IDs in OSPF and BGP are `0.type.asn.num`, for easier understanding. GNS3 doesn't allow changing the router labels from their hostname though. `type` is 0 for border routers, 1 for internal, 2 for CPE. `asn` is asn and `num` is the last number in the hostname. So e.g. `asn1border3` has a router ID of `0.0.1.3`.

## External Connectivity

Note: this uses public AS numbers (1-6) for simplicity. Don't use the BGP method with a device that's peering with other real public ASes.

## Testing

TODO: expand.

* `python manage.py test`
* `pytest --no-header --tb=line -rA`

## Troubleshooting

* `telnetlib` is occasionally throwing errors. Sometimes it'll print a stack trace other times it'll abort so rich-click prints `Aborted`. Stop and start all nodes if it happens then run the step again. If it's still no good restart the GNS3 server. Might be related to CPU on the GNS3 server.

## Misc notes

* Thought I was losing my mind before I found this: FRR 7.4+ requirements have changed for BGP.
  * You have to define an out filter to send routes and an in filter to receive them (I knew this one)
  * But ALSO now set [`no bgp network import-check`](https://docs.frrouting.org/en/latest/bgp.html#clicmd-bgp-network-import-check) to allow advertising routes that aren't in the local routing table (I assumed it was still the original behaviour). What threw me is that `show ip bgp all` on the local router still listed the routes.
* Debugging FRR:

```sh
mkdir -p /var/log/frr
touch /var/log/frr/debug.log
chmod 666 /var/log/frr/debug.log
vtysh
 conf t
  log file /var/log/frr/debug.log
  # check and enable what you need to
  debug ?
```

* You need to call `node.get_links()` before `node.links`
* In FRR you have to create the prefix list before specifying it in the BGP config if you want all the routes to work immediately. It'll apply the other way, but you'll be missing some BGP routes and only clearing the session or restarting fixes it.
* ASN 1 peers iBGP on interface IPs for lab simplicity. If you're feeling fired up you can convert it to loopbacks.
* You can't change GNS3 node labels (even in the GUI), they always reflect the hostname. This is why `node.update(label=new_label_dict)` isn't working.

## TODO

* Clean up iBGP / OSPF interaction
* Generate and peer on loopbacks