# Generate a bulletproof Streamlit secrets file: encodes the GCP key as base64
# (one safe line that cannot break TOML) and pulls QDRANT_API_KEY from .env.
# Writes .streamlit/secrets.toml (git-ignored).
#
# Run:  python to_toml.py
# Then open .streamlit/secrets.toml, copy BOTH lines, paste into the Streamlit
# Cloud dashboard -> Settings -> Secrets -> Save.
import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

raw = Path("Project_123.json").read_bytes()
b64 = base64.b64encode(raw).decode("ascii")
qdrant = os.environ.get("QDRANT_API_KEY", "")

content = (
    f"QDRANT_API_KEY = {json.dumps(qdrant)}\n"
    f'GCP_SERVICE_ACCOUNT_B64 = "{b64}"\n'
)

out = Path(".streamlit/secrets.toml")
out.parent.mkdir(exist_ok=True)
out.write_text(content, encoding="utf-8")

print("Wrote .streamlit/secrets.toml")
print("  QDRANT_API_KEY found in .env:", bool(qdrant))
print("  base64 length:", len(b64))
print("\nNext: open .streamlit/secrets.toml, copy BOTH lines, paste into the")
print("Streamlit dashboard Secrets box, and click Save.")
