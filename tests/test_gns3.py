import pathfix
from gns3_bgp_frr import gns3


def test_project_is_reachable():
    # the actual test will happen with the import above
    assert gns3.project.status == "opened"
