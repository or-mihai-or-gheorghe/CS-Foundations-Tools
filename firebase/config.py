# firebase/config.py
"""
Firebase configuration module
Loads configuration from Streamlit secrets and initializes Firebase
"""

import streamlit as st
from typing import Dict, Optional
import firebase_admin
from firebase_admin import credentials, db
import logging

logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None
_firebase_config: Optional[Dict] = None


def is_mock_mode() -> bool:
    """
    Check if we're running in mock authentication mode (local development)

    Returns:
        bool: True if mock mode is enabled, False for production
    """
    try:
        return st.secrets.get("firebase", {}).get("use_mock_auth", False)
    except Exception as e:
        logger.warning(f"Could not read secrets, defaulting to mock mode: {e}")
        return True


def get_firebase_config() -> Dict:
    """
    Get Firebase configuration from Streamlit secrets

    Returns:
        Dict: Firebase configuration object

    Raises:
        ValueError: If Firebase configuration is missing or invalid
    """
    global _firebase_config

    if _firebase_config is not None:
        return _firebase_config

    try:
        firebase_secrets = st.secrets["firebase"]

        _firebase_config = {
            "apiKey": firebase_secrets["api_key"],
            "authDomain": firebase_secrets["auth_domain"],
            "databaseURL": firebase_secrets["database_url"],
            "projectId": firebase_secrets["project_id"],
            "storageBucket": firebase_secrets["storage_bucket"],
            "messagingSenderId": firebase_secrets["messaging_sender_id"],
            "appId": firebase_secrets["app_id"]
        }

        logger.info(f"Firebase config loaded for project: {_firebase_config['projectId']}")
        return _firebase_config

    except KeyError as e:
        raise ValueError(f"Missing Firebase configuration in secrets: {e}")
    except Exception as e:
        raise ValueError(f"Error loading Firebase configuration: {e}")


def initialize_firebase_admin() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK

    Returns:
        firebase_admin.App: Initialized Firebase app instance

    Raises:
        ValueError: If initialization fails
    """
    global _firebase_app

    # Return existing app if already initialized
    if _firebase_app is not None:
        return _firebase_app

    # Don't initialize Firebase Admin in mock mode
    if is_mock_mode():
        logger.info("Running in mock mode - Firebase Admin SDK not initialized")
        return None

    try:
        config = get_firebase_config()

        # Check if default app already exists
        try:
            _firebase_app = firebase_admin.get_app()
            logger.info("Firebase Admin SDK already initialized")
            return _firebase_app
        except ValueError:
            # App doesn't exist, create it
            pass

        # Initialize with service account credentials
        # In production, use a certificate
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": config["projectId"],
            "private_key_id": st.secrets["firebase"].get("private_key_id"),
            "private_key": st.secrets["firebase"].get("private_key", "").replace("\\n", "\n"),
            "client_email": st.secrets["firebase"].get("client_email"),
            "client_id": st.secrets["firebase"].get("client_id"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["firebase"].get("client_x509_cert_url")
        })

        _firebase_app = firebase_admin.initialize_app(cred, {
            'databaseURL': config['databaseURL']
        })

        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app

    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise ValueError(f"Firebase initialization failed: {e}")


def get_database_reference(path: str = "/"):
    """
    Get a reference to the Firebase Realtime Database

    Args:
        path: Database path (default: root)

    Returns:
        firebase_admin.db.Reference: Database reference

    Raises:
        ValueError: If Firebase is not initialized or in mock mode
    """
    if is_mock_mode():
        raise ValueError("Cannot access real database in mock mode")

    initialize_firebase_admin()

    try:
        return db.reference(path)
    except Exception as e:
        logger.error(f"Failed to get database reference for path '{path}': {e}")
        raise ValueError(f"Database reference error: {e}")


def get_environment_info() -> Dict:
    """
    Get information about the current environment

    Returns:
        Dict: Environment information
    """
    return {
        "is_mock_mode": is_mock_mode(),
        "has_firebase_config": _firebase_config is not None,
        "firebase_initialized": _firebase_app is not None,
        "project_id": _firebase_config.get("projectId") if _firebase_config else None
    }
