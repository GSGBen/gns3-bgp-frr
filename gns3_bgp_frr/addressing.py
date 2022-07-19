from typing import Generator
from typing import Dict
from netaddr import IPNetwork
from settings import *
from gns3_bgp_frr import gns3, logging
import gns3fy


def get_asn1_supernet() -> IPNetwork:
    """
    Returns the first /25 of the /24 P2P_SUPERNET for easier summarisation.
    """
    supernet = IPNetwork(P2P_SUPERNET)
    supernet_halves = supernet.subnet(25)
    first_half = next(supernet_halves)
    return first_half


def get_asn1_p2p_subnets(log=False) -> Generator[IPNetwork, None, None]:
    """
    Get the /30s available for asn1-internal links.
    Uses the first /25 of the /24 P2P_SUPERNET for easier summarisation.
    Returns an interable of IPNetwork()s.
    Wrap with list() if you need to get all at once.
    """

    first_half = get_asn1_supernet()

    if log:
        logging.log(f"carving up {first_half} into /30s for asn1 links", "info")

    # carve up the supernet into /30 subnets
    return first_half.subnet(prefixlen=30)


def get_non_asn1_p2p_subnets(log=False) -> Generator[IPNetwork, None, None]:
    """
    Get the /30s available for non-asn1-internal links.
    Uses the second /25 of the /24 P2P_SUPERNET.
    Returns an interable of IPNetwork()s.
    Wrap with list() if you need to get all at once.
    """

    # use the second half of the /24
    supernet = IPNetwork(P2P_SUPERNET)
    supernet_halves = supernet.subnet(25)
    next(supernet_halves)
    second_half = next(supernet_halves)

    if log:
        logging.log(f"carving up {second_half} into /30s for non-asn1 links", "info")

    # carve up the supernet into /30 subnets
    return second_half.subnet(prefixlen=30)


def get_interface_ips(log=False) -> Dict[str, Dict[str, str]]:
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
    if log:
        logging.log("generating interface IPs", "info")

    # there's weirdness if the nodes aren't started
    gns3.start_all(log=log)

    output_dict: Dict[str, Dict[str, str]] = {}

    asn1_subnets = list(get_asn1_p2p_subnets(log=log))
    non_asn1_subnets = list(get_non_asn1_p2p_subnets(log=log))

    if log:
        logging.log(f"assigning subnets to {len(gns3.project.links)} links", "info")

    for index, link in enumerate(gns3.project.links):
        if link.nodes is None:
            continue

        # assign a /30 per link.
        # group the asn1 internal links for route summarisation
        subnets = asn1_subnets if gns3.is_asn1_internal_link(link) else non_asn1_subnets
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
                    if log:
                        logging.log(
                            "giving [cyan]asn1border1 eth7[/] an external address",
                            "info",
                        )
                    ip_cidr = ASN1BORDER1_EXTERNAL_IP
                else:
                    if log:
                        logging.log(
                            "giving [cyan]asn1border2 eth7[/] an external address",
                            "info",
                        )
                    ip_cidr = ASN1BORDER2_EXTERNAL_IP
            else:
                # otherwise assign the next available IP in the subnet
                ip = next(subnet_ips)
                ip_cidr = f"{ip}/{link_subnet.prefixlen}"

            # record it
            output_dict[node.name][port_name] = ip_cidr

    return output_dict
