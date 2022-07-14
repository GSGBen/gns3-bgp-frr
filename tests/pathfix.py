# allow importing from the main gns3_bgp_frr module

from pathlib import Path
import sys

parent_path = Path(__file__).resolve().parent
root_path = parent_path / ".."
sys.path.insert(0, str(root_path.resolve()))
