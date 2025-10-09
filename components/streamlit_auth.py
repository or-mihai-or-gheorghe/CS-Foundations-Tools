# components/streamlit_auth.py
"""
Streamlit native authentication wrapper
Uses st.login() and st.logout() with Google OAuth
"""

import streamlit as st
from firebase import get_current_user as get_firebase_user, sign_in as firebase_sign_in, sign_out as firebase_sign_out
from firebase.environment import is_local_environment, should_use_mock_auth
import logging

logger = logging.getLogger(__name__)


def is_authenticated() -> bool:
    """
    Check if user is authenticated via Streamlit's native auth

    Returns:
        bool: True if user is logged in
    """
    return st.user.is_logged_in


def get_current_user() -> dict:
    """
    Get current authenticated user from Streamlit

    Returns:
        dict: User information or None if not logged in
    """
    if not st.user.is_logged_in:
        return None

    return {
        "uid": st.user.email.replace("@", "_").replace(".", "_"),  # Create UID from email
        "email": st.user.email,
        "display_name": st.user.name or st.user.email.split("@")[0],
        "photo_url": "",
        "is_authenticated": True,
        "is_mock": False
    }


def sync_to_firebase():
    """
    Sync Streamlit auth user to Firebase session for database operations
    """
    if st.user.is_logged_in:
        user_data = get_current_user()

        # Check if already synced
        firebase_user = get_firebase_user()
        if firebase_user and firebase_user.get('email') == user_data['email']:
            return  # Already synced

        # Sync to Firebase session
        firebase_sign_in(
            email=user_data['email'],
            token=None,  # No token needed for internal sync
            display_name=user_data['display_name']
        )

        logger.info(f"Synced Streamlit user to Firebase: {user_data['email']}")


def validate_ase_domain(email: str) -> bool:
    """
    Validate that email belongs to @ase.ro domain or any subdomain

    Args:
        email: Email address to validate

    Returns:
        bool: True if email ends with @ase.ro or subdomain (e.g., @csie.ase.ro)
    """
    email_lower = email.lower()
    # Accept @ase.ro and any subdomain like @csie.ase.ro, @stud.ase.ro, etc.
    return email_lower.endswith(".ase.ro") or email_lower.endswith("@ase.ro")


def render_auth_ui():
    """
    Render authentication UI using Streamlit's native auth
    In local environment, auth is optional (show option to play anonymously)
    Enforces @ase.ro domain restriction
    """
    is_local = is_local_environment()

    if st.user.is_logged_in:
        # ENFORCE domain validation
        user_email = getattr(st.user, 'email', None)

        if user_email and not validate_ase_domain(user_email):
            # Invalid domain - force sign out
            st.error(f"⛔ Access Denied: Only @ase.ro email addresses are allowed")
            st.error(f"You signed in with: {user_email}")
            st.warning("Please sign in with your @ase.ro or subdomain account (e.g., @csie.ase.ro)")

            if st.button("Sign Out", type="primary", use_container_width=True):
                firebase_sign_out()
                st.logout()

            st.stop()  # Prevent further execution

        # User is signed in with valid domain
        _render_user_profile()

        # Sync to Firebase for database operations
        sync_to_firebase()
    else:
        # User is not signed in
        if is_local:
            # Local: Show that auth is optional
            _render_sign_in_local()
        else:
            # Cloud: Show regular sign-in
            _render_sign_in()


def _render_user_profile():
    """Render signed-in user profile - compact (domain already validated)"""
    # Get user info safely
    user_email = getattr(st.user, 'email', None)
    user_name = getattr(st.user, 'name', None)

    if not user_email:
        st.error("Unable to retrieve user email")
        return

    col1, col2 = st.columns([4, 1])

    with col1:
        # Display user info as simple text (no HTML to avoid issues)
        display_name = user_name or user_email.split('@')[0]
        st.success(f"✅ {display_name}")
        st.caption(user_email)

    with col2:
        if st.button("Sign Out", type="secondary", key="signout_native"):
            # Sign out from Firebase too
            firebase_sign_out()
            st.logout()


def _render_sign_in():
    """Render sign-in button - compact"""
    with st.expander("🔐 Sign in to save scores", expanded=False):
        st.caption("Only @ase.ro accounts • Scores saved to leaderboard")

        if st.button("🔑 Log in with Google", on_click=st.login, type="primary", use_container_width=True):
            pass  # st.login handles the redirect


def _render_sign_in_local():
    """Render sign-in for local environment - auth is optional"""
    with st.expander("🔐 Sign in (Optional - Local Dev)", expanded=False):
        st.caption("💻 Local mode: You can play without signing in")
        st.caption("Sign in to test leaderboard features with mock data")

        if st.button("🔑 Log in (Mock Auth)", on_click=st.login, type="primary", use_container_width=True):
            pass  # st.login handles the redirect

        st.info("ℹ️ In local dev, auth is optional. Games can be played anonymously.")


def render_auth_status_badge():
    """Render compact authentication status badge"""
    if st.user.is_logged_in:
        display_name = st.user.name or st.user.email.split('@')[0]
        st.success(f"✅ Signed in as **{display_name}**")
    else:
        st.warning("⚠️ Not signed in - scores won't be saved")
