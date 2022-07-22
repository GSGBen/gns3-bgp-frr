from dataclasses import dataclass
import re
from time import sleep
from typing import Dict, List, Literal, Optional
import gns3fy
from gns3_bgp_frr import configs, logging, addressing
from settings import *
from telnetlib import Telnet
from netaddr import IPAddress

# connection and command write timeout
TELNET_TIMEOUT = 5

# set up the connection to the project once for all functionality below (and anyone that
# imports us)
try:
    gns3_server = gns3fy.Gns3Connector(
        GNS3_SERVER_URL, GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD
    )
    project = gns3fy.Project(name=PROJECT_NAME, connector=gns3_server)
    project.get()
    if project.status != "opened":
        project.open()
except:
    message = f"Couldn't connect to GNS3 project with the following settings.\n \
                Please make sure they're correct in settings.py.\n \
                \n \
                GNS3_SERVER_URL: {GNS3_SERVER_URL}\n \
                GNS3_SERVER_USERNAME: {GNS3_SERVER_USERNAME}\n \
                GNS3_SERVER_PASSWORD: <not printed>\n \
                PROJECT_NAME: {PROJECT_NAME}\n \
                \n \
                run [cyan]pytest --no-header --tb=line[/] for a more detailed test.\n"
    logging.log(message, "error")
    exit(1)
# print("ran gns3.py startup code")


def start_all(log=False):
    """
    Starts all nodes.
    """
    if log:
        logging.log("Starting all nodes ", "info")

    # save time - only run if required. There's a wait from start_nodes() even if
    # they're already started
    already_started = all([node.status == "started" for node in project.nodes])
    if not already_started:
        project.start_nodes()


def stop_all(log=False):
    """
    Stops all nodes.
    """
    if log:
        logging.log("Stopping all nodes ", "info")

    # save time - only run if required. There's a wait from stop_nodes() even if
    # they're already stopped
    already_stopped = all([node.status == "stopped" for node in project.nodes])
    if not already_stopped:
        project.stop_nodes()


def reset_all(log=False):
    """
    Resets the entire project to default. If you configure something in the project, add
    a reset_<thing>() function to undo it and call it from here.
    """
    set_daemon_state_all(False, log=log)
    configs.clear_frr_configs(log=log)


def set_daemon_state_all(enabled: bool = True, log=False):
    """
    Enable the required daemons on each node.
    """

    # they need to be started for us to run commands on them
    start_all(log=log)

    if log:
        verb = "enabling" if enabled else "disabling"
        logging.log(f"{verb} bgp and ospf daemons", "info")

    for node in project.nodes:
        if is_router(node):

            if log:
                logging.log(f"    [cyan]{node.name}[/]", "info")

            running = "yes" if enabled else "no"
            for daemon in ["bgpd", "ospfd", "bfdd"]:
                run_shell_command(
                    node,
                    f"sed -i 's/^{daemon}=.*/{daemon}={running}/g' /etc/frr/daemons",
                )

    # they need to be restarted for it to apply
    if log:
        logging.log("restarting nodes to apply:", "info")

    stop_all(log=log)
    start_all(log=log)


def is_router(node: gns3fy.Node) -> bool:
    return (
        node.properties is not None
        and "image" in node.properties
        and node.properties["image"].startswith("frrouting")
    )


def run_shell_command(
    node: gns3fy.Node,
    command: str,
    aux_port: bool = True,
):
    """
    Runs a command in the outer sh shell of the frr image. Exits back to sh before each
    so use `run_shell_commands()` to e.g write configs.

    If aux_port is true it sends the command to the aux port which is what FRR requires.
    If false it sends it to the console port. I'm having issues with alpine - not sure
    whether it wants the console or aux port.
    """
    run_shell_commands(node, [command], aux_port)


def run_shell_commands(
    node: gns3fy.Node,
    commands: List[str],
    aux_port: bool = True,
):
    """
    Runs multiple commands in the outer sh shell of the gns3 node.

    If aux_port is true it sends the command to the aux port which is what FRR requires.
    If false it sends it to the console port. I'm having issues with alpine - not sure
    whether it wants the console or aux port.

    I was getting weird input errors. Happened intermittently before `conf t`. It shows
    up as `\\x07;5R` (so `\\x07;5Rconf t) if I read it which doesn't show up in google
    and doesn't look exactly like an ANSI code.

    x07 is the ASCII bell. This is only happening on the node I have a GNS3 putty aux
    session open to. probably that putty session interfering. As a hacky workaround I
    could clear the line (ctrl-c) or backspace a bunch of times (\\b\\b\\b).

    Pretty much confirmed: it follows the one I have open and I can't reproduce it when
    it's closed.

    What didn't work:
      - delay of 0.1
      - sending `\\r\\n` instead of `\\n`
      - `command.strip()` and `escape_ansi_bytes(command_line)` before sending
      - waiting until "# " instead of "#". There was an extra space in the prompt I was
        missing.
    - .read_eager()

    What did work:
      - clearing the line before writing with ctrl-c

    """
    if node is None or node.properties is None or node.console is None:
        return
    telnet_port: int = node.properties["aux"] if aux_port else node.console
    # print(aux_port, telnet_port)
    prompt = b"# "
    with Telnet(GNS3_SERVER_HOST, telnet_port, timeout=TELNET_TIMEOUT) as telnet:
        # clear the active line (ctrl-c)
        telnet.write(b"\x03")
        # these are required, mainly the last one. closing the connection too early
        telnet.read_until(prompt, timeout=TELNET_TIMEOUT)
        # exit to the shell in case we're in vtysh, potentially in config mode.
        telnet.write(b"end\n")
        # stops it running
        telnet.read_until(prompt, timeout=TELNET_TIMEOUT)
        telnet.write(b"exit\n")
        telnet.read_until(prompt, timeout=TELNET_TIMEOUT)

        for command in commands:
            command_line = command.strip().encode() + b"\n"
            # send ctrl-c to clear the line to avoid the junk if a putty session is open
            # to the same port (see docstring)
            telnet.write(b"\x03")
            result = telnet.read_until(prompt, timeout=TELNET_TIMEOUT)

            telnet.write(command_line)
            result = telnet.read_until(prompt, timeout=TELNET_TIMEOUT)

            # # debug
            # print(f"{node.name}: {str(result)}")
            # if str(result).find("Unknown command") != -1:
            #    rich.print("[bold red]error above[/]")

            # try to fix the alpine node not always getting the last command
            sleep(0.1)


def escape_ansi_bytes(input: bytes):
    """
    https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python#14693789
    """
    # 7-bit and 8-bit C1 ANSI sequences
    ansi_escape_8bit = re.compile(
        rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
    )
    return ansi_escape_8bit.sub(b"", input)


def is_asn1_internal_link(link: gns3fy.Link) -> bool:
    """
    Returns True if both nodes connected to the link are asn1 nodes.
    """

    if link and link.nodes and link.nodes[0] and link.nodes[1]:
        node0 = project.get_node(node_id=link.nodes[0]["node_id"])
        node1 = project.get_node(node_id=link.nodes[1]["node_id"])
        if (
            node0
            and node1
            and node0.name
            and node1.name
            and node0.name.startswith("asn1")
            and node1.name.startswith("asn1")
        ):
            return True

    # else
    return False


def get_asn(node_name: str) -> Optional[int]:
    """
    Returns the AS number of the device via name if it has one, otherwise None.
    """
    match = re.match(r"asn(\d+)", node_name)
    if match and match.group(1):
        return int(match.group(1))

    # else
    return None


@dataclass
class NeighboringBorderRouterInfo:
    """
    Data representing a border router directly connected to a node, it's AS number and
    the IP of the interface facing the node.

    Used as a return of get_neighboring_border_routers() for better structure.
    """

    # asn of the neighboring router.
    asn: int
    # name of the neighboring router
    name: str
    # IP of the interface facing the target node. No prefix length.
    ip: str


def get_neighboring_border_routers_info(
    node: gns3fy.Node,
    interface_ips: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[NeighboringBorderRouterInfo]:
    """
    Returns details of the border and CPE routers directly connected to the given node, and
    their links facing the given node.

    Args:
        node (gns3fy.Node): The node to get neighboring border routers of.

        interface_ips (Dict[str, Dict[str, str]]): The output of
        `addressing.get_interface_ips()`. If given we don't have to generate it each
        call.

    Returns:
        List[NeighboringBorderRouterInfo]: Info on the neighboring border routers.
    """
    # retrieve if not given
    if interface_ips is None:
        interface_ips = addressing.get_interface_ips()

    # get neighboring device names and the name of their link facing us
    neighboring_nodes: Dict[str, str] = {}
    # populate
    node.get_links()
    # connected links
    for node_link in node.links:
        if node_link.nodes is None:
            continue
        # nodes on those links including us
        for link_node_info in node_link.nodes:
            # not us
            if link_node_info["node_id"] != node.node_id:
                neighboring_node = project.get_node(node_id=link_node_info["node_id"])
                if (
                    neighboring_node is not None
                    and neighboring_node.ports is not None
                    and neighboring_node.name is not None
                ):
                    port_number = link_node_info["adapter_number"]
                    port_name = neighboring_node.ports[port_number]["name"]
                    neighboring_nodes[neighboring_node.name] = port_name

    # retrieve the info of border devices
    return_list: List[NeighboringBorderRouterInfo] = []
    for neighboring_node_name, interface_name in neighboring_nodes.items():
        # if they're a border router
        if neighboring_node_name and (
            neighboring_node_name.find("border") != -1
            or neighboring_node_name.find("cpe") != -1
        ):
            asn = get_asn(neighboring_node_name)

            ip_cidr = interface_ips[neighboring_node_name][interface_name]
            ip = ip_cidr.split("/")[0]

            if asn is not None and ip is not None:
                info = NeighboringBorderRouterInfo(
                    asn=asn, name=neighboring_node_name, ip=ip
                )
                return_list.append(info)

    return return_list


def show_interface_ips(log=False):
    """
    Updates the label of the ends of each link to show the interface name and the IP
    assigned.
    """

    if log:
        logging.log("updating interface labels", "info")

    interface_ips = addressing.get_interface_ips()

    for link in project.links:
        if link.nodes is None:
            continue

        for link_node in link.nodes:
            node = project.get_node(node_id=link_node["node_id"])
            if node is None or node.name is None or node.ports is None:
                continue

            interface_name = node.ports[link_node["adapter_number"]]["name"]
            if (
                node.name not in interface_ips
                or interface_name not in interface_ips[node.name]
            ):
                continue
            interface_ip_cidr = interface_ips[node.name][interface_name]
            interface_ip = interface_ip_cidr.split("/")[0]

            new_label_text = f"{interface_name}\n{interface_ip}"
            new_label_style = "'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #444444;fill-opacity: 1.0;'"

            link_node["label"]["text"] = new_label_text
            link_node["label"]["style"] = new_label_style

        link.update(nodes=link.nodes)


def reset_interface_ip_labels(log=False):
    """
    Reverts the effects of `show_interface_ips()`.
    """

    if log:
        logging.log("resetting interface labels", "info")

    for link in project.links:
        if link.nodes is None:
            continue

        for link_node in link.nodes:
            node = project.get_node(node_id=link_node["node_id"])
            if node is None or node.name is None or node.ports is None:
                continue

            interface_name = node.ports[link_node["adapter_number"]]["name"]

            new_label_text = f"{interface_name}"
            new_label_style = "'font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;'"

            link_node["label"]["text"] = new_label_text
            link_node["label"]["style"] = new_label_style

        link.update(nodes=link.nodes)
