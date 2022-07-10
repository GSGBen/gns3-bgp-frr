from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from gns3_bgp_frr import addressing

# load jinja2 templates from the templates folder in the base
parent_path = Path(__file__).resolve().parent
root_path = parent_path / ".."
templates_path = root_path / "templates"

env = Environment(
    loader=FileSystemLoader(templates_path), autoescape=select_autoescape()
)

# write to this folder
output_folder_path = root_path / "generated"
# ensure it exists
output_folder_path.mkdir(parents=True, exist_ok=True)


def generate_configs():
    """
    Creates FRR configs for each router, in the `<project root>/generated` folder.
    """

    # template that applies to all routers
    base_template = env.get_template("base.j2")

    for node_name, interface_ips in addressing.get_interface_ips().items():
        # save with a cisco extension to get better highlighting
        output_path = output_folder_path / f"{node_name}.ios"
        # generate separate config sections
        base_config = base_template.render({"interface_ips": interface_ips})

        # write a single combined config file
        config = base_config
        with open(output_path, "w") as output_file:
            output_file.write(config)
