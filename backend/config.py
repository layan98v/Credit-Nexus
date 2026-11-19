"""
Settings — no accounts, no keys. Everything is optional environment variables:
  CN_AI=0                 turn AI commentary off
  CN_STRICT=0             allow unverified AI figures (default: strict)
  CN_POLLINATIONS_KEY     optional key from enter.pollinations.ai (lifts the 1-request-per-30s limit)
  CN_PUBLIC=1             website mode (no package installs at runtime)
  CN_CONFIG_DIR           where local files go (default ~/.credit-nexus)
"""
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CN_CONFIG_DIR", str(Path.home() / ".credit-nexus")))
PUBLIC = os.environ.get("CN_PUBLIC") == "1"
