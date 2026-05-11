#!/usr/bin/env python3
import sys
from pathlib import Path
from paperclip_long_range_os_validation import validate_phase5

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/paperclip_long_range_os/phase5_memory_substrate")
raise SystemExit(validate_phase5(root))
