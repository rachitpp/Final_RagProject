"""Bridge Streamlit Cloud secrets to the environment / GCP credentials.

Locally you authenticate with a `.env` file plus a `GOOGLE_APPLICATION_CREDENTIALS`
path pointing at a service-account JSON. On Streamlit Community Cloud there is no
`.env` and no key file on disk — only `st.secrets`. This bridges the gap:

  - simple string secrets (QDRANT_API_KEY, GOOGLE_CLOUD_PROJECT) -> env vars
  - the GCP service account -> written to a temp JSON file that
    GOOGLE_APPLICATION_CREDENTIALS then points at (so Vertex AI's ADC finds it)

It is a NO-OP when those env vars are already set (local dev with .env) or when
no secrets are configured, so it never interferes with running locally.
"""
import json
import os
import tempfile


def bootstrap_secrets() -> None:
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return  # not running under Streamlit, or no secrets -> rely on .env

    # Simple string secrets -> env vars (never clobber something already set).
    for key in ("QDRANT_API_KEY", "GOOGLE_CLOUD_PROJECT"):
        try:
            if key in secrets and not os.environ.get(key):
                os.environ[key] = str(secrets[key])
        except Exception:
            pass

    # GCP service account -> temp JSON file + Application Default Credentials.
    try:
        if "gcp_service_account" in secrets and not os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        ):
            sa = dict(secrets["gcp_service_account"])
            path = os.path.join(tempfile.gettempdir(), "gcp_service_account.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sa, f)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
    except Exception:
        pass
