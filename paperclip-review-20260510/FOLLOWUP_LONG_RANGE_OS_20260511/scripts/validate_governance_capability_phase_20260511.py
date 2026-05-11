#!/usr/bin/env python3
import sys
from pathlib import Path
from paperclip_long_range_os_validation import validate_phase4

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/paperclip_long_range_os/phase4_governance_capability")
raise SystemExit(validate_phase4(root))
