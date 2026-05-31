"""Bridge Streamlit Cloud secrets to the environment / GCP credentials.

Locally you authenticate with a `.env` file plus a GOOGLE_APPLICATION_CREDENTIALS
path. On Streamlit Community Cloud there is no `.env` and no key file on disk —
only `st.secrets`. This bridges the gap, and it is a NO-OP when those env vars
are already set (local dev) or when no secrets are configured.

The GCP service account can be supplied in ANY of these forms (first wins):

  1. BEST — base64 of the whole JSON (one safe line, cannot break TOML):
         GCP_SERVICE_ACCOUNT_B64 = "eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIs..."
  2. The whole JSON as a TOML triple-quoted string:
         GCP_SERVICE_ACCOUNT_JSON = '''{ ... }'''
  3. A [gcp_service_account] TOML table (field-by-field).

GOOGLE_CLOUD_PROJECT is auto-filled from the key's project_id if not set.
"""
import base64
import json
import os
import tempfile


def _load_sa(secrets) -> dict | None:
    # 1. base64 of the JSON (safest to paste).
    try:
        if "GCP_SERVICE_ACCOUNT_B64" in secrets:
            raw = base64.b64decode(str(secrets["GCP_SERVICE_ACCOUNT_B64"]))
            return json.loads(raw.decode("utf-8-sig"))
    except Exception:
        pass
    # 2. Whole JSON as a string.
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" in secrets:
            return json.loads(str(secrets["GCP_SERVICE_ACCOUNT_JSON"]))
    except Exception:
        pass
    # 3. TOML table.
    try:
        if "gcp_service_account" in secrets:
            return dict(secrets["gcp_service_account"])
    except Exception:
        pass
    return None


def bootstrap_secrets() -> None:
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return  # not under Streamlit / no secrets -> rely on .env

    for key in ("QDRANT_API_KEY", "GOOGLE_CLOUD_PROJECT"):
        try:
            if key in secrets and not os.environ.get(key):
                os.environ[key] = str(secrets[key])
        except Exception:
            pass

    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return  # already have a key file (local dev)

    sa = _load_sa(secrets)
    if not sa:
        return

    try:
        path = os.path.join(tempfile.gettempdir(), "gcp_service_account.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sa, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        if not os.environ.get("GOOGLE_CLOUD_PROJECT") and sa.get("project_id"):
            os.environ["GOOGLE_CLOUD_PROJECT"] = sa["project_id"]
    except Exception:
        pass
