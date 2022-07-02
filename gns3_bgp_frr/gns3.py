import gns3fy
import os
from settings import *

# set up the connection to the project once for all functionality below
gns3_server = gns3fy.Gns3Connector(
    GNS3_SERVER_URL, GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD
)
project = gns3fy.Project(name=PROJECT_NAME, connector=gns3_server)
project.get()
if project.status != "opened":
    project.open()


def start():
    """
    Starts all nodes.
    """
    project.start_nodes()


def set_up():
    """
    Enable the required daemons on each node.
    """


def reset_all():
    """
    Resets the entire project to default.
    If you configure something in the project, add a reset_<thing>() function to undo it and call it from here.
    """
    for node in project.nodes:
        clear_node_config()
