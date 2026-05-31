"""Bridge Streamlit Cloud secrets to the environment / GCP credentials.

Locally you authenticate with a `.env` file plus a GOOGLE_APPLICATION_CREDENTIALS
path. On Streamlit Community Cloud there is no `.env` and no key file on disk —
only `st.secrets`. This bridges the gap, and it is a NO-OP when those env vars
are already set (local dev) or when no secrets are configured.

The GCP service account can be supplied in EITHER form:

  1. Easiest — paste the whole JSON as one TOML triple-quoted string:
         GCP_SERVICE_ACCOUNT_JSON = '''
         { ... entire Project_123.json ... }
         '''
  2. Or as a [gcp_service_account] TOML table (field-by-field).

GOOGLE_CLOUD_PROJECT is auto-filled from the key's project_id if not set.
"""
import json
import os
import tempfile


def bootstrap_secrets() -> None:
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return  # not under Streamlit / no secrets -> rely on .env

    # Simple string secrets -> env vars (never clobber something already set).
    for key in ("QDRANT_API_KEY", "GOOGLE_CLOUD_PROJECT"):
        try:
            if key in secrets and not os.environ.get(key):
                os.environ[key] = str(secrets[key])
        except Exception:
            pass

    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return  # already have a key file (local dev)

    # Resolve the service account from whichever form is provided.
    sa = None
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" in secrets:           # form 1: raw JSON string
            sa = json.loads(str(secrets["GCP_SERVICE_ACCOUNT_JSON"]))
    except Exception:
        sa = None
    if sa is None:
        try:
            if "gcp_service_account" in secrets:            # form 2: TOML table
                sa = dict(secrets["gcp_service_account"])
        except Exception:
            sa = None

    if not sa:
        return

    try:
        path = os.path.join(tempfile.gettempdir(), "gcp_service_account.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sa, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        # Backfill project from the key itself if not set explicitly.
        if not os.environ.get("GOOGLE_CLOUD_PROJECT") and sa.get("project_id"):
            os.environ["GOOGLE_CLOUD_PROJECT"] = sa["project_id"]
    except Exception:
        pass
