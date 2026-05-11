#!/usr/bin/env python3
import sys
from pathlib import Path
from paperclip_long_range_os_validation import validate_phase1

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/paperclip_long_range_os/phase1_operating_kernel")
raise SystemExit(validate_phase1(root))
