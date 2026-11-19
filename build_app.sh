#!/bin/bash
# Builds dist/CreditNexus on this Mac/Linux machine (needs Python once, only here).
cd "$(dirname "$0")"
python3 -m pip install --quiet -r backend/requirements.txt pyinstaller || exit 1
python3 -m PyInstaller --noconfirm --clean packaging/credit-nexus.spec && echo "Built: $(pwd)/dist/CreditNexus"
