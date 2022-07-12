from typing import Dict
from netaddr import IPNetwork
from settings import *
from gns3_bgp_frr import gns3
import gns3fy


def get_p2p_subnets():
    """
    Get the /30s available for GNS3 device networking.
    Returns an interable of IPNetwork()s.
    Wrap with list() if you need to get all at once.
    """
    # carve up the supernet into /30 subnets
    supernet = IPNetwork(P2P_SUPERNET)
    return supernet.subnet(prefixlen=30)


def get_interface_ips() -> Dict[str, Dict[str, str]]:
    """
    Returns a dict of dicts that contains the IP address for each FRR router's connected
    interfaces.

    Returns:
        Dict[
            node.name: str,
            Dict[
                node.ports.name: str,
                ip_cidr: str
            ]
        ]:

            An outer dict of node names (e.g. "asn2border1") mapping to inner dicts.
            Inner dicts mapping node port names (e.g. "eth0") to interface IP/Masks in
            CIDR notation (e.g. "10.0.0.1/24")
    """

    # there's weirdness if the nodes aren't started
    gns3.start_all()

    output_dict: Dict[str, Dict[str, str]] = {}

    subnets = list(get_p2p_subnets())

    for index, link in enumerate(gns3.project.links):
        if link.nodes is None:
            continue
        # assign a /30 per link
        if index >= len(subnets):
            raise IndexError("too many links, not enough /30s in the given supernet")
        link_subnet = subnets[index]
        # get a generator we can pull successive IPs from
        subnet_ips = link_subnet.iter_hosts()

        # assign each router in this link an IP in the subnet
        for node_entry in link.nodes:
            node = gns3.project.get_node(node_id=node_entry["node_id"])
            if (
                node is None
                or node.name is None
                or node.ports is None
                or not gns3.is_router(node)
            ):
                continue
            # ensure their output entry exists
            if node.name not in output_dict.keys():
                output_dict[node.name] = {}
            # the link stores the port number of the host. Convert it to the name of
            # the port
            port_number = node_entry["adapter_number"]
            port_name = node.ports[port_number]["name"]

            # handle external addressing as a special case
            if node.name in ["asn1border1", "asn1border2"] and port_name == "eth7":
                if node.name == "asn1border1":
                    ip_cidr = ASN1BORDER1_EXTERNAL_IP
                else:
                    ip_cidr = ASN1BORDER2_EXTERNAL_IP
            else:
                # otherwise assign the next available IP in the subnet
                ip = next(subnet_ips)
                ip_cidr = f"{ip}/{link_subnet.prefixlen}"

            # record it
            output_dict[node.name][port_name] = ip_cidr

    return output_dict
