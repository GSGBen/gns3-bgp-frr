from time import sleep
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from gns3_bgp_frr import addressing, gns3, logging
from netaddr import IPNetwork

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

    for node_name, interface_ips in addressing.get_interface_ips(log=log).items():
        # save with a cisco extension to get better highlighting
        file_name = f"{node_name}.ios"

        if log:
            logging.log(f"generating [cyan]{file_name}[/]", "info")

        output_path = output_folder_path / file_name
        # generate separate config sections
        base_config = base_template.render({"interface_ips": interface_ips})

        # write a single combined config file
        config = base_config
        with open(output_path, "w") as output_file:
            output_file.write(config)


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
