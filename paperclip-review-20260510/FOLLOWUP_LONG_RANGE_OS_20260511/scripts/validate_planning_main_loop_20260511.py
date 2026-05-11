#!/usr/bin/env python3
import sys
from pathlib import Path
from paperclip_long_range_os_validation import validate_phase3

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/paperclip_long_range_os/phase3_planning_main_loop")
raise SystemExit(validate_phase3(root))
