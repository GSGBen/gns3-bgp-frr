# the same details the gns3 application uses
GNS3_SERVER_URL = "http://example:3080"
GNS3_SERVER_HOST = "192.168.1.1"
GNS3_SERVER_USERNAME = "exampleuser"
GNS3_SERVER_PASSWORD = "examplepassword"
PROJECT_NAME = "frr-bgp"
# a free subnet, at least a /25, in CIDR format, that's routable within your network
P2P_SUPERNET = "10.0.0.0/24"
# an IP and mask, in  CIDR notation, for each of the external routers, in the network
# your GNS3 VM is connected to. This is considered 'external' to the GNS3 lab but it
# might be your LAN or dev network.
ASN1BORDER1_EXTERNAL_IP = "192.168.1.251/24"
ASN1BORDER2_EXTERNAL_IP = "192.168.1.252/24"
