from netaddr import IPNetwork
from settings import *
from gns3_bgp_frr import gns3


def get_p2p_subnets():
    """
    Get the /30s available for GNS3 device networking.
    Returns an interable of IPNetwork()s.
    Wrap with list() if you need to get all at once.
    """
    supernet = IPNetwork(P2P_SUPERNET)
    return supernet.subnet(prefixlen=30)
