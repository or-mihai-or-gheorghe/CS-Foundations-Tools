# firebase/mock_auth.py
"""
Mock authentication for local development
Simulates Firebase authentication without requiring OAuth callbacks
"""

import streamlit as st
import hashlib
import time
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def validate_ase_email(email: str) -> bool:
    """
    Validate that email belongs to @ase.ro domain

    Args:
        email: Email address to validate

    Returns:
        bool: True if email ends with @ase.ro, False otherwise
    """
    if not email:
        return False
    return email.lower().endswith("@ase.ro")


def is_email_allowed(email: str) -> bool:
    """
    Check if email is in the allowed test emails list (mock mode only)

    Args:
        email: Email address to check

    Returns:
        bool: True if email is allowed for testing
    """
    try:
        allowed_emails = st.secrets.get("firebase", {}).get("allowed_test_emails", [])
        return email.lower() in [e.lower() for e in allowed_emails]
    except Exception:
        return False


def generate_mock_uid(email: str) -> str:
    """
    Generate a consistent mock user ID from email

    Args:
        email: User email

    Returns:
        str: Mock UID (hash of email)
    """
    return hashlib.md5(email.lower().encode()).hexdigest()[:20]


def create_mock_user(email: str, display_name: Optional[str] = None) -> Dict:
    """
    Create a mock user object

    Args:
        email: User email
        display_name: Optional display name

    Returns:
        Dict: Mock user object
    """
    if not display_name:
        # Extract name from email (e.g., john.doe@ase.ro -> John Doe)
        name_part = email.split("@")[0]
        display_name = name_part.replace(".", " ").title()

    return {
        "uid": generate_mock_uid(email),
        "email": email,
        "display_name": display_name,
        "photo_url": f"https://ui-avatars.com/api/?name={display_name.replace(' ', '+')}&background=667eea&color=fff",
        "is_authenticated": True,
        "is_mock": True,
        "auth_time": time.time()
    }


def mock_sign_in(email: str, display_name: Optional[str] = None) -> Optional[Dict]:
    """
    Perform mock sign-in (local development only)

    Args:
        email: User email
        display_name: Optional display name

    Returns:
        Dict: User object if successful, None if validation fails
    """
    # Validate email domain - in mock mode, any @ase.ro email is allowed
    if not validate_ase_email(email):
        logger.warning(f"Mock sign-in failed: email {email} is not @ase.ro domain")
        return None

    # Optional: Check if email is in allowed list for extra security
    # Disabled by default to allow any @ase.ro email in development
    # Uncomment the following lines to restrict to specific test emails:
    # if not is_email_allowed(email):
    #     logger.warning(f"Mock sign-in failed: email {email} is not in allowed test emails")
    #     return None

    # Create mock user
    user = create_mock_user(email, display_name)
    logger.info(f"Mock sign-in successful for {email} (UID: {user['uid']})")

    return user


def mock_sign_out() -> bool:
    """
    Perform mock sign-out

    Returns:
        bool: Always True
    """
    logger.info("Mock sign-out successful")
    return True


def get_mock_user_from_session() -> Optional[Dict]:
    """
    Get the currently signed-in mock user from session state

    Returns:
        Dict: User object if signed in, None otherwise
    """
    if 'user' not in st.session_state:
        return None

    user = st.session_state.user
    if user and user.get('is_mock') and user.get('is_authenticated'):
        return user

    return None


# Mock database for local development
_mock_database = {
    "users": {},
    "games": {},
    "leaderboard": {
        "binary_speed_challenge": {
            "all_time": {},
            "by_difficulty": {
                "Easy": {},
                "Medium": {},
                "Hard": {},
                "Expert": {}
            },
            "monthly": {}
        },
        "global": {
            "all_time": {}
        }
    }
}


def get_mock_database() -> Dict:
    """
    Get the mock database (for local development)

    Returns:
        Dict: Mock database
    """
    return _mock_database


def save_to_mock_database(path: str, data: Dict) -> bool:
    """
    Save data to mock database (local development)

    Args:
        path: Database path (e.g., "users/abc123")
        data: Data to save

    Returns:
        bool: True if successful
    """
    try:
        parts = path.strip("/").split("/")
        current = _mock_database

        # Navigate to the parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value
        current[parts[-1]] = data

        logger.info(f"Mock database: saved to {path}")
        return True

    except Exception as e:
        logger.error(f"Mock database save failed: {e}")
        return False


def get_from_mock_database(path: str) -> Optional[Dict]:
    """
    Get data from mock database (local development)

    Args:
        path: Database path

    Returns:
        Dict: Data if found, None otherwise
    """
    try:
        parts = path.strip("/").split("/")
        current = _mock_database

        for part in parts:
            if part not in current:
                return None
            current = current[part]

        return current

    except Exception as e:
        logger.error(f"Mock database get failed: {e}")
        return None
