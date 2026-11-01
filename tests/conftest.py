import os
import sys
import pathlib

os.environ["SECONDLOOK_MOCK"] = "1"  # tests never call the API
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
