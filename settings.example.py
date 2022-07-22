# the same details the gns3 application uses
GNS3_SERVER_URL = "http://example:3080"
GNS3_SERVER_HOST = "192.168.1.1"
GNS3_SERVER_USERNAME = "exampleuser"
GNS3_SERVER_PASSWORD = "examplepassword"
PROJECT_NAME = "frr-bgp"
# a free subnet, at least a /24, in CIDR format, that's routable within your network
P2P_SUPERNET = "10.0.0.0/24"
# an IP and mask, in  CIDR notation, for each of the external routers, in the network
# your GNS3 VM is connected to. This is your lan or dev network, probably the network
# your GNS3 VM is one. This is considered 'external' to the GNS3 lab.
ASN1BORDER1_EXTERNAL_IP = "192.168.1.251/24"
ASN1BORDER2_EXTERNAL_IP = "192.168.1.252/24"
# the IP of the (real, outside GNS3) gateway on the same subnet as
# ASN1BORDER1_EXTERNAL_IP and ASN2BORDER1_EXTERNAL_IP. Either for BGP or default route.
# See the description of the next setting too.
EXTERNAL_GATEWAY = "192.168.1.254"
# If you have a router that can run BGP:
# - specify True here. asn1border1 and 2 will then try to peer with it via BGP. You'll
# also need to set up peering from your side (see README).
#
# If you don't:
# - set this to False and asn1border1 and 2 will originate a default route, then set
# their default route to EXTERNAL_GATEWAY. On your EXTERNAL_GATEWAY device you'll need
# to add a route to P2P_SUPERNET via ASN1BORDER1_EXTERNAL_IP and
# ASN1BORDER2_EXTERNAL_IP.
ENABLE_EXTERNAL_GATEWAY_BGP = True
# if ENABLE_EXTERNAL_GATEWAY_BGP is True, set this to the AS number of EXTERNAL_GATEWAY
EXTERNAL_GATEWAY_ASN = 64512
