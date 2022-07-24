from copy import deepcopy
import re
from time import sleep
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from pathlib import Path
from gns3_bgp_frr import addressing, gns3, logging
from netaddr import IPNetwork, IPAddress
import gns3fy
import settings

# load jinja2 templates from the templates folder in the base
parent_path = Path(__file__).resolve().parent
root_path = parent_path / ".."
templates_folder_path = root_path / "templates"
env = Environment(
    loader=FileSystemLoader(templates_folder_path), autoescape=select_autoescape()
)

# write to this folder
output_folder_path = root_path / "generated"
# ensure it exists
output_folder_path.mkdir(parents=True, exist_ok=True)

# mark which interfaces of asn1 devices should form ospf adjacencies.
ospf_interfaces = {
    "asn1border1": ["eth0", "eth1"],
    "asn1border2": ["eth0", "eth1"],
    "asn1border3": ["eth6", "eth7"],
    "asn1internal1": ["eth0", "eth6", "eth7"],
    "asn1internal2": ["eth0", "eth6", "eth7"],
}

# mark which interfaces of asn1 border devices should form iBGP peers
asn1_ibgp_interfaces = {
    "asn1border1": ["eth0", "eth1"],
    "asn1border2": ["eth0", "eth1"],
    "asn1border3": ["eth6", "eth7"],
}


def generate_configs(log=False):
    """
    Creates FRR configs for each router, in the `<project root>/generated` folder.
    """
    if log:
        logging.log(
            f"generating configs for routers in [cyan]{output_folder_path.resolve()}[/]",
            "info",
        )

    # template that applies to all routers
    base_template = env.get_template("base.j2")
    # template that applies to ospf routers in asn 1
    ospf_template = env.get_template("ospf.j2")
    # template that applies to all border routers
    bgp_template = env.get_template("bgp.j2")

    # IP addresses for the interfaces of all routers
    interface_ips = addressing.get_interface_ips(log=log)
    # asn1 p2p links summarised
    asn1_supernet = addressing.get_asn1_supernet()

    for node in gns3.project.nodes:
        if node.name is None or not gns3.is_router(node):
            continue

        node_interface_ips = interface_ips[node.name]

        # save with a cisco extension to get better highlighting
        file_name = f"{node.name}.ios"

        if log:
            logging.log(f"generating [cyan]{file_name}[/]", "info")

        # generate separate config sections
        base_config = base_template.render({"interface_ips": node_interface_ips})
        ospf_config = generate_ospf_config(node.name, ospf_template, asn1_supernet)
        bgp_config = generate_bgp_config(node, bgp_template, interface_ips)

        output_path = output_folder_path / file_name
        # write a single combined config file
        config = base_config + "\n" + ospf_config + "\n" + bgp_config
        with open(output_path, "w") as output_file:
            output_file.write(config)


def generate_ospf_config(
    node_name: str, ospf_template: Template, asn1_supernet: IPNetwork
) -> str:
    """
    Generate and return the OSPF part of the config for asn1 devices.
    @see `generate_configs()`.
    """
    if node_name.startswith("asn1"):

        # required, as it won't redistribute from bgp
        default_information_originate = (
            True
            if node_name.endswith("border1") or node_name.endswith("border2")
            else False
        )

        node_ospf_interfaces = ospf_interfaces[node_name]
        ospf_config = ospf_template.render(
            {
                "ospf_interfaces": node_ospf_interfaces,
                "asn1_supernet": asn1_supernet,
                "router_id": generate_router_id(node_name),
                "default_information_originate": default_information_originate,
            }
        )
    else:
        ospf_config = ""

    return ospf_config


def generate_bgp_config(
    node: gns3fy.Node, bgp_template: Template, interface_ips: Dict[str, Dict[str, str]]
) -> str:
    """
    Generate and return the BGP part of the config for border devices.
    @see `generate_configs()`.
    """
    # only generate for border and CPE devices
    if node.name and (node.name.find("border") != -1 or node.name.find("cpe") != -1):

        asn = gns3.get_asn(node.name)
        # directly connected and border only, sonly only eBGP. Not asn1 or asn6 iBGP
        neighbors = gns3.get_neighboring_border_routers_info(node, interface_ips)

        if node.name.startswith("asn1"):
            # summarise ASN 1 at its edge
            advertised_networks = [addressing.get_asn1_supernet()]
            redistribute_connected = False
            # enable iBGP by also peering with all interfaces of other asn1 border nodes
            neighbors.extend(get_asn1_ibgp_peers_info(node, interface_ips))
        else:
            advertised_networks = []
            # non-ASN-1 devices just advertise their connected links instead
            redistribute_connected = True

        # configure external BGP or a default route for asn1border1 and asn1border2
        external_default_gateway = None
        if node.name == "asn1border1" or node.name == "asn1border2":
            if settings.ENABLE_EXTERNAL_GATEWAY_BGP:
                neighbors.append(
                    gns3.NeighboringBorderRouterInfo(
                        asn=settings.EXTERNAL_GATEWAY_ASN,
                        name="EXTERNAL",
                        ip=settings.EXTERNAL_GATEWAY,
                    )
                )
                # and advertise the local network too. Same local network for both
                external_ip_subnet = IPNetwork(interface_ips[node.name]["eth7"])
                external_subnet = (
                    f"{external_ip_subnet.network}/{external_ip_subnet.prefixlen}"
                )
                advertised_networks.append(IPNetwork(external_subnet))
            else:
                external_default_gateway = settings.EXTERNAL_GATEWAY

        bgp_config = bgp_template.render(
            {
                "asn": asn,
                "neighbors": neighbors,
                "advertised_networks": advertised_networks,
                "redistribute_connected": redistribute_connected,
                "router_id": generate_router_id(node.name),
                "external_default_gateway": external_default_gateway,
            }
        )
    else:
        bgp_config = ""

    return bgp_config


def get_asn1_ibgp_peers_info(
    asn1_node: gns3fy.Node, interface_ips: Dict[str, Dict[str, str]]
) -> List[gns3.NeighboringBorderRouterInfo]:
    """
    Given an asn1 node, returns neighbor info on which BGP peers to set up to create
    iBGP for ASN1.
    """

    # get the peers and interfaces that aren't us
    other_asn1_ibgp_interfaces = {
        name: interfaces
        for (name, interfaces) in asn1_ibgp_interfaces.items()
        if name != asn1_node.name
    }

    ibgp_neighbors = []
    for name, interfaces in other_asn1_ibgp_interfaces.items():
        for interface in interfaces:
            ip = interface_ips[name][interface].split("/")[0]
            ibgp_neighbors.append(
                gns3.NeighboringBorderRouterInfo(
                    asn=1, name=f"{name}-{interface}", ip=ip
                )
            )

    return ibgp_neighbors


def generate_router_id(node_name: str) -> IPAddress:
    """
    Generate a router ID based on the ASN and router number to make things clearer.

    Border routers get 0.0.asn.num - e.g. asn1border1 is 0.0.1.1
    Internal routers get 0.1.asn.num.
    CPE routers get 0.2.asn.num.
    All others get 0.255.asn.num.

    If asn or num are missing or the given name can't be parsed, 255s will be used.
    """
    if node_name.find("border") != -1:
        type_id = 0
    elif node_name.find("internal") != -1:
        type_id = 1
    elif node_name.find("cpe") != -1:
        type_id = 2
    else:
        type_id = 255

    match = re.match(r"asn(\d+)[a-zA-Z]+(\d+)", node_name)
    if match:
        asn = match.group(1) if match.group(1) else "255"
        num = match.group(2) if match.group(2) else "255"
        router_id = f"0.{type_id}.{asn}.{num}"
    else:
        router_id = f"0.{type_id}.255.255"

    return IPAddress(router_id)


def apply_frr_configs(log=False):
    """
    Apply the generated configs to the frr devices.
    Configs must have been generated first.
    Automatically starts the nodes.
    """
    gns3.start_all(log=log)

    if log:
        logging.log("applying frr configs", "info")

    for config_file_path in output_folder_path.iterdir():
        node_name = config_file_path.name.split(".")[0]

        if log:
            logging.log(f"    [cyan]{node_name}[/]", "info")

        node = gns3.project.get_node(name=node_name)
        if node is None:
            continue

        with open(config_file_path) as config_file:
            config_lines = config_file.read().splitlines()
            # enter config mode
            config_lines.insert(0, "vtysh")
            config_lines.insert(1, "conf t")
            # save
            config_lines.append("end")
            config_lines.append("wr mem")

            gns3.run_shell_commands(node, config_lines)


def clear_frr_configs(log=False):
    """
    Clears the config on frr nodes.
    """
    # they need to be started for us to run commands on them
    gns3.start_all(log=log)

    if log:
        logging.log("clearing frr configs", "info")

    for node in gns3.project.nodes:
        if gns3.is_router(node):

            if log:
                logging.log(f"    [cyan]{node.name}[/]", "info")

            # delete all frr config files and conf.sav files
            gns3.run_shell_command(node, "rm /etc/frr/*.conf*")

    if log:
        logging.log("restarting to apply:", "info")

    # they need to be restarted for it to apply
    gns3.stop_all(log=log)
    gns3.start_all(log=log)


def configure_alpine(log=False):
    """
    Apply network settings to the alpine-1 endpoint.
    Automatically starts the node.
    """
    # get the alpine-1 endpoint and its router from the project
    alpine_1 = gns3.project.get_node("alpine-1")
    asn6cpe1 = gns3.project.get_node("asn6cpe1")
    if alpine_1 is None:
        raise TypeError("Couldn't find node named 'alpine-1'")
    if asn6cpe1 is None:
        raise TypeError("Couldn't find node named 'asn6cpe1'")

    if log:
        logging.log("starting [cyan]alpine-1[/]", "info")

    alpine_1.start()

    # get the CIDR IP of the router's interface.
    # this will tell us the subnet and give us the default gateway IP
    device_ips = addressing.get_interface_ips()
    asn6cpe1_network = IPNetwork(device_ips["asn6cpe1"]["eth0"])

    # asn6cpe1 was the only device automatically addressed on the link so assume it got
    # the first IP in the subnet. Give us the second
    subnet_ips = asn6cpe1_network.iter_hosts()
    next(subnet_ips)  # first
    alpine_1_ip = next(subnet_ips)  # second

    if log:
        logging.log("setting [cyan]alpine-1[/] network config", "info")

    # configure
    commands = [
        # clear existing
        "rm /etc/network/interfaces",
        "echo 'auto eth0' >> /etc/network/interfaces",
        "echo 'iface eth0 inet static' >> /etc/network/interfaces",
        f"echo '       address {alpine_1_ip}' >> /etc/network/interfaces",
        f"echo '       netmask {asn6cpe1_network.netmask}' >> /etc/network/interfaces",
        f"echo '       gateway {asn6cpe1_network.ip}' >> /etc/network/interfaces",
    ]
    gns3.run_shell_commands(alpine_1, commands)

    if log:
        logging.log("restarting [cyan]alpine-1[/] to apply", "info")

    # apply
    alpine_1.stop()
    alpine_1.start()


def clear_alpine_config(log=False):
    """
    Resets the alpine  node back to default.
    """

    # get the alpine-1 endpoint from the project
    alpine_1 = gns3.project.get_node("alpine-1")
    if alpine_1 is None:
        raise TypeError("Couldn't find node named 'alpine-1'")

    if log:
        logging.log("starting [cyan]alpine-1[/] ", "info")

    alpine_1.start()

    if log:
        logging.log("clearing [cyan]alpine-1[/] network config", "info")

    gns3.run_shell_command(alpine_1, "rm /etc/network/interfaces")

    # apply
    if log:
        logging.log("restarting [cyan]alpine-1[/] to apply ", "info")

    alpine_1.stop()
    alpine_1.start()
