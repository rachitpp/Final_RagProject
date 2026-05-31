# Generate a COMPLETE, valid Streamlit secrets file from your existing creds.
# Reads Project_123.json (GCP key) + .env (QDRANT_API_KEY, GOOGLE_CLOUD_PROJECT)
# and writes .streamlit/secrets.toml (git-ignored).
#
# Run:  python to_toml.py
# Then open .streamlit/secrets.toml, copy ALL of it, and paste into the
# Streamlit Cloud dashboard -> Settings -> Secrets -> Save.
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

with open("Project_123.json", encoding="utf-8") as f:
    sa = json.load(f)

qdrant = os.environ.get("QDRANT_API_KEY", "")
project = os.environ.get("GOOGLE_CLOUD_PROJECT") or sa.get("project_id", "")

lines = [
    f"QDRANT_API_KEY = {json.dumps(qdrant)}",
    f"GOOGLE_CLOUD_PROJECT = {json.dumps(project)}",
    "",
    "[gcp_service_account]",
]
for key, value in sa.items():
    lines.append(f"{key} = {json.dumps(value)}")  # json.dumps -> valid TOML string
content = "\n".join(lines) + "\n"

out = Path(".streamlit/secrets.toml")
out.parent.mkdir(exist_ok=True)
out.write_text(content, encoding="utf-8")

print(f"Wrote {out}")
print("  QDRANT_API_KEY found in .env :", bool(qdrant))
print("  GOOGLE_CLOUD_PROJECT         :", project)
print("  gcp_service_account fields   :", len(sa))
print("\nNext: open .streamlit/secrets.toml, copy EVERYTHING, paste into the")
print("Streamlit dashboard Secrets box, and click Save.")
