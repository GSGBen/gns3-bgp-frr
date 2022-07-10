import re
from time import sleep
from typing import Dict, List
import gns3fy
import os
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
    set_daemon_state_all(False)
    clear_config_all()


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


def run_shell_command(frr_node: gns3fy.Node, command: str):
    """
    Runs a command in the outer sh shell of the frr image. Exits back to sh before each
    so use `run_shell_commands()` to e.g write configs.

    Increase `delay_seconds` if there are weird input errors.
    """
    run_shell_commands(frr_node, [command])


def run_shell_commands(frr_node: gns3fy.Node, commands: List[str]):
    """
    Runs multiple commands in the outer sh shell of the frr image.

    Increase `delay_seconds` if there are weird input errors.

    I'm was getting weird input errors. Happened intermittently before `conf t`. It
    shows up as `\\x07;5R` (so `\\x07;5Rconf t) if I read it which doesn't show up in google and
    doesn't look exactly like an ANSI code.

    x07 is the ASCII bell. Not sure what's triggering it though. Ah, I  think this is
    only happening on the node I have a GNS3 putty aux session open to.

    What didn't work:
      - delay of 0.1
      - sending `\\r\\n` instead of `\\n`
      - `command.strip()` and `escape_ansi_bytes(command_line)` before sending
      - waiting until "# " instead of "#". There was an extra space in the prompt I was
        missing. This makes me think there was still data in the buffer to be read, that
        I was somehow writing back. Maybe .read_eager() or .read_lazy() before I write
        would help.

    What did work:

    """
    telnet_port = frr_node.properties["aux"]
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
            # ensure everything is clear to avoid the junk (see docstring)
            result_eager = telnet.read_eager()
            telnet.write(command_line)
            result = telnet.read_until(prompt, timeout=TELNET_TIMEOUT)

            # debug
            print(f"{frr_node.name}: {result_eager}, <command>, {result}")
            if str(result).find("Unknown command") != -1:
                rich.print("[bold red]error above[/]")
            if result_eager:
                rich.print("[bold yellow]result_eager above has content[/]")


def escape_ansi_bytes(input: bytes):
    """
    https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python#14693789
    """
    # 7-bit and 8-bit C1 ANSI sequences
    ansi_escape_8bit = re.compile(
        rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
    )
    return ansi_escape_8bit.sub(b"", input)


def clear_config_all():
    """
    Clears the frr config on all nodes.
    """
    # they need to be started for us to run commands on them
    project.start_nodes()

    for node in project.nodes:
        if is_router(node):
            # delete all frr config files and conf.sav files
            run_shell_command(node, "rm /etc/frr/*.conf*")

    # they need to be restarted for it to apply
    project.stop_nodes()
    project.start_nodes()


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
        for node_entry in link.nodes:
            if node_entry.node_id == node.node_id:
                # the link nodes call them port_number, the node ports call them
                # adapter_number
                found_links[node_entry["adapter_number"]] = link

    return found_links
