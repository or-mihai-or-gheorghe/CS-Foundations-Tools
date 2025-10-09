# firebase/auth.py
"""
Firebase authentication module
Handles user sign-in, sign-out, and session management
Supports both real Firebase Auth and mock auth for local development
"""

import streamlit as st
from typing import Optional, Dict
import logging
from .config import is_mock_mode, get_firebase_config
from .mock_auth import (
    mock_sign_in,
    mock_sign_out,
    get_mock_user_from_session,
    validate_ase_email as mock_validate_ase_email
)

logger = logging.getLogger(__name__)


def validate_ase_email(email: str) -> bool:
    """
    Validate that email belongs to @ase.ro domain

    Args:
        email: Email address to validate

    Returns:
        bool: True if email ends with @ase.ro
    """
    return mock_validate_ase_email(email)


def get_current_user() -> Optional[Dict]:
    """
    Get the currently authenticated user from session state

    Returns:
        Dict: User object if authenticated, None otherwise
    """
    if 'user' not in st.session_state:
        return None

    user = st.session_state.user
    if user and user.get('is_authenticated'):
        return user

    return None


def sign_in(email: str, token: Optional[str] = None, display_name: Optional[str] = None) -> Optional[Dict]:
    """
    Sign in a user with Firebase Authentication or mock auth

    Args:
        email: User email address
        token: Firebase ID token (production only)
        display_name: User display name (optional, used in mock mode)

    Returns:
        Dict: User object if successful, None if failed
    """
    # Validate email domain first
    if not validate_ase_email(email):
        logger.warning(f"Sign-in failed: email {email} is not @ase.ro domain")
        st.error("⚠️ Only @ase.ro email addresses are allowed")
        return None

    # Use mock authentication in development
    if is_mock_mode():
        logger.info(f"Using mock authentication for {email}")
        user = mock_sign_in(email, display_name)

        if user:
            st.session_state.user = user
            logger.info(f"Mock sign-in successful: {email}")
            return user
        else:
            st.error("❌ Sign-in failed. Check if your email is in the allowed test list.")
            return None

    # Production Firebase Authentication
    try:
        # Import pyrebase here to avoid issues in mock mode
        import pyrebase

        config = get_firebase_config()
        firebase = pyrebase.initialize_app(config)
        auth = firebase.auth()

        if token:
            # Verify existing token
            try:
                account_info = auth.get_account_info(token)
                user_data = account_info['users'][0]

                email_verified = user_data.get('emailVerified', False)
                user_email = user_data.get('email', '')

                # Double-check domain restriction
                if not validate_ase_email(user_email):
                    logger.warning(f"Sign-in blocked: {user_email} is not @ase.ro")
                    st.error("⚠️ Only @ase.ro email addresses are allowed")
                    return None

                # Create user object
                user = {
                    "uid": user_data['localId'],
                    "email": user_email,
                    "display_name": user_data.get('displayName', user_email.split('@')[0]),
                    "photo_url": user_data.get('photoUrl', ''),
                    "email_verified": email_verified,
                    "is_authenticated": True,
                    "is_mock": False,
                    "token": token
                }

                st.session_state.user = user
                logger.info(f"Firebase sign-in successful: {user_email}")
                return user

            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                st.error("❌ Authentication token is invalid or expired")
                return None

        else:
            logger.warning("No token provided for Firebase authentication")
            st.error("❌ Authentication failed: no token provided")
            return None

    except Exception as e:
        logger.error(f"Firebase authentication error: {e}")
        st.error(f"❌ Authentication error: {str(e)}")
        return None


def sign_out() -> bool:
    """
    Sign out the current user

    Returns:
        bool: True if successful
    """
    if is_mock_mode():
        mock_sign_out()

    # Clear user from session state
    if 'user' in st.session_state:
        email = st.session_state.user.get('email', 'unknown')
        del st.session_state.user
        logger.info(f"User signed out: {email}")

    return True


def is_authenticated() -> bool:
    """
    Check if a user is currently authenticated

    Returns:
        bool: True if user is signed in
    """
    user = get_current_user()
    return user is not None and user.get('is_authenticated', False)


def get_user_uid() -> Optional[str]:
    """
    Get the current user's UID

    Returns:
        str: User UID if authenticated, None otherwise
    """
    user = get_current_user()
    return user.get('uid') if user else None


def get_user_email() -> Optional[str]:
    """
    Get the current user's email

    Returns:
        str: User email if authenticated, None otherwise
    """
    user = get_current_user()
    return user.get('email') if user else None


def get_user_display_name() -> Optional[str]:
    """
    Get the current user's display name

    Returns:
        str: User display name if authenticated, None otherwise
    """
    user = get_current_user()
    if user:
        return user.get('display_name', user.get('email', '').split('@')[0])
    return None
