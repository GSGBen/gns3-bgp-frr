import gns3fy
import os
from settings import *
from telnetlib import Telnet

# connection and command write timeout
TELNET_TIMEOUT = 5

# set up the connection to the project once for all functionality below
gns3_server = gns3fy.Gns3Connector(
    GNS3_SERVER_URL, GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD
)
project = gns3fy.Project(name=PROJECT_NAME, connector=gns3_server)
project.get()
if project.status != "opened":
    project.open()


def start_all():
    """
    Starts all nodes.
    """
    project.start_nodes()


def stop_all():
    """
    Starts all nodes.
    """
    project.stop_nodes()


def reset_all():
    """
    Resets the entire project to default. If you configure something in the project, add
    a reset_<thing>() function to undo it and call it from here.
    """
    set_daemon_state(False)


def set_daemon_state(enabled: bool = True):
    """
    Enable the required daemons on each node.
    """
    # they need to be started for us to run commands on them
    project.start_nodes()

    for node in project.nodes:
        if is_router(node):
            run_shell_command(node, "sed -i 's/bgpd=no/bgpd=yes/g' /etc/frr/daemons")
            run_shell_command(node, "sed -i 's/ospfd=no/ospfd=yes/g' /etc/frr/daemons")

    # they need to be restarted for it to apply
    project.stop_nodes()
    project.start_nodes()


def is_router(node: gns3fy.Node) -> bool:
    return (
        node.properties is not None
        and "image" in node.properties
        and node.properties["image"].startswith("frrouting")
    )


def run_shell_command(frr_node: gns3fy.Node, command: str):
    """
    Runs a command in the outer sh shell of the frr image.
    """
    telnet_port = frr_node.properties["aux"]
    with Telnet(GNS3_SERVER_HOST, telnet_port, timeout=TELNET_TIMEOUT) as telnet:
        # clear the active line
        telnet.write(b"\x03")
        telnet.read_until(b"#", timeout=TELNET_TIMEOUT)
        # exit to the shell in case we're in vtysh, potentially in config mode
        telnet.write(b"end\n")
        # stops it running
        telnet.read_until(b"#", timeout=TELNET_TIMEOUT)
        telnet.write(b"exit\n")
        # these are required, mainly the last one. closing the connection too early
        telnet.read_until(b"#", timeout=TELNET_TIMEOUT)

        telnet.write(command.encode() + b"\n")
        telnet.read_until(b"#", timeout=TELNET_TIMEOUT)
