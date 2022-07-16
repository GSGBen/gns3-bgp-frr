import pathfix
import urllib.request
from settings import *
import requests
from requests.auth import HTTPBasicAuth
import gns3fy

########## test the various components of loading the project


def test_server_is_reachable_and_authenticates():
    # reachability
    try:
        auth = HTTPBasicAuth(GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD)
        response = requests.get(GNS3_SERVER_URL, auth=auth)
    except requests.exceptions.ConnectionError:
        assert False, f"Couldn't connect to {GNS3_SERVER_URL}, check URL"

    assert (
        response.status_code != 404
    ), f"Couldn't connect to {GNS3_SERVER_URL}, check URL"

    # authentication
    assert (
        response.status_code != 401
    ), "Couldn't authenticate to the GNS3 server, check username and password"


def test_project_is_reachable():
    # same import code from gns3.py
    gns3_server = gns3fy.Gns3Connector(
        GNS3_SERVER_URL, GNS3_SERVER_USERNAME, GNS3_SERVER_PASSWORD
    )
    project = gns3fy.Project(name=PROJECT_NAME, connector=gns3_server)
    try:
        project.get()
    except:
        assert (
            False
        ), f"Couldn't get project {PROJECT_NAME}, check the project name is the same"

    if project.status != "opened":
        project.open()

    assert project.status == "opened"
