# firebase/environment.py
"""
Environment detection utilities
Detect if running locally vs Streamlit Cloud
"""

import streamlit as st
import os


def is_local_environment() -> bool:
    """
    Detect if running in local development environment

    Returns:
        bool: True if local, False if Streamlit Cloud
    """
    # Check if we're on Streamlit Cloud
    try:
        # Streamlit Cloud sets specific headers
        headers = st.context.headers
        host = headers.get("host", "")

        # If host contains streamlit.app, we're on cloud
        if "streamlit.app" in host:
            return False

        # Check for localhost indicators
        if "localhost" in host or "127.0.0.1" in host or not host:
            return True

    except:
        pass

    # Fallback: check environment variables
    # Streamlit Cloud sets HOSTNAME to a specific pattern
    hostname = os.environ.get("HOSTNAME", "")
    if "streamlit" in hostname.lower():
        return False

    # Check if running on default local port
    if os.environ.get("STREAMLIT_SERVER_PORT") == "8501":
        return True

    # Default to local if uncertain
    return True


def should_use_mock_auth() -> bool:
    """
    Determine if mock auth should be used based on environment

    Returns:
        bool: True if mock auth should be enabled
    """
    # Check secrets config first
    try:
        use_mock = st.secrets.get("firebase", {}).get("use_mock_auth", None)
        if use_mock is not None:
            return use_mock
    except:
        pass

    # Auto-detect: use mock in local, real auth in cloud
    return is_local_environment()


def get_environment_name() -> str:
    """
    Get human-readable environment name

    Returns:
        str: "Local Development" or "Streamlit Cloud"
    """
    return "Local Development" if is_local_environment() else "Streamlit Cloud"
