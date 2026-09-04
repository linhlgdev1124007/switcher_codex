import os
import sys
from pathlib import Path


if hasattr(sys, "_MEIPASS"):
    bundle_dir = Path(sys._MEIPASS)
    os.environ["TCL_LIBRARY"] = str(bundle_dir / "tcl" / "tcl8.6")
    os.environ["TK_LIBRARY"] = str(bundle_dir / "tcl" / "tk8.6")
