#!/usr/bin/env python3
import sys
from pathlib import Path
from paperclip_long_range_os_validation import validate_phase6

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/paperclip_long_range_os/phase6_learning_local_llm")
raise SystemExit(validate_phase6(root))
