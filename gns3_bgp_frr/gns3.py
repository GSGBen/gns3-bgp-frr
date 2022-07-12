import re
from time import sleep
from typing import Dict, List, Literal
import gns3fy
import os
from gns3_bgp_frr import configs
from settings import *
from telnetlib import Telnet
import rich

# connection and command write timeout
TELNET_TIMEOUT = 5

# set up the connection to the project once for all functionality below (and anyone that
# imports us)
gns3_server = gns3fy.Gns3Connector(
    GNS3_SERVER_URL, GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD
)
project = gns3fy.Project(name=PROJECT_NAME, connector=gns3_server)
project.get()
if project.status != "opened":
    project.open()
# print("ran gns3.py startup code")


def start_all():
    """
    Starts all nodes.
    """
    project.start_nodes()


def start_node(node: gns3fy.Node):
    """
    Starts a node and blocks until it's available.
    This might not be needed, <node>.start() might already do it.
    """
    node.start()
    max_wait_seconds = 5.0
    waited_seconds = 0.0
    while node.status != "started":
        if waited_seconds >= max_wait_seconds:
            raise Exception(f"'{node.name}' didn't start within {max_wait_seconds}")
        sleep(0.5)
        waited_seconds += 0.5


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
    set_daemon_state_all(False)
    configs.clear_frr_configs()


def set_daemon_state_all(enabled: bool = True):
    """
    Enable the required daemons on each node.
    """
    # they need to be started for us to run commands on them
    project.start_nodes()

    for node in project.nodes:
        if is_router(node):
            # change =no to =yes for the bgpd and ospfd lines
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


def escape_ansi_bytes(input: bytes):
    """
    https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python#14693789
    """
    # 7-bit and 8-bit C1 ANSI sequences
    ansi_escape_8bit = re.compile(
        rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
    )
    return ansi_escape_8bit.sub(b"", input)


def get_node_links(node: gns3fy.Node) -> Dict[int, gns3fy.Link]:
    """
    `node.links` doesn't seem to be populated so we need to search through
    `project.links`.

    Returns a dict mapping the node's interface adapter numbers to the link objects
    they're attached to. E.g.
    `{0: <gns3fy.Link object>, 7: <other gns3fy.Link object>}`
    """
    found_links = {}

    # find links referencing the given node
    for link in project.links:
        if link.nodes is None:
            continue
        for node_entry in link.nodes:
            if node_entry.node_id == node.node_id:
                # the link nodes call them port_number, the node ports call them
                # adapter_number
                found_links[node_entry["adapter_number"]] = link

    return found_links
