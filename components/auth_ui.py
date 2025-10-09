# components/auth_ui.py
"""
Authentication UI component
Renders sign-in/sign-out interface for Firebase authentication
"""

import streamlit as st
from firebase import (
    is_mock_mode,
    sign_in,
    sign_out,
    get_current_user,
    validate_ase_email
)
import logging

logger = logging.getLogger(__name__)


def render_auth_ui():
    """
    Render authentication UI
    Shows sign-in form if not authenticated, user profile if authenticated
    """
    user = get_current_user()

    if user and user.get('is_authenticated'):
        # User is signed in - show profile
        _render_user_profile(user)
    else:
        # User is not signed in - show sign-in form
        _render_sign_in_form()


def _render_user_profile(user: dict):
    """
    Render user profile section (when signed in) - Compact version

    Args:
        user: User object from session state
    """
    col1, col2 = st.columns([4, 1])

    with col1:
        # Compact user info
        display_name = user.get('display_name', 'User')
        email = user.get('email', '')

        st.markdown(f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 0;
        ">
            <span style="font-size: 18px;">✅</span>
            <div>
                <div style="font-weight: 500; font-size: 14px;">{display_name}</div>
                <div style="font-size: 12px; color: #666;">{email}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # Sign out button
        if st.button("Sign Out", type="secondary", key="signout_btn"):
            sign_out()
            st.rerun()


def _render_sign_in_form():
    """
    Render sign-in form - Compact version
    Shows different UI for mock mode vs production
    """
    # Compact expander for sign-in
    with st.expander("🔐 Sign in to save scores", expanded=False):
        if is_mock_mode():
            # Mock authentication (local development)
            _render_mock_sign_in()
        else:
            # Production Firebase authentication
            _render_firebase_sign_in()


def _render_mock_sign_in():
    """
    Render mock sign-in form (local development) - Compact version
    """
    st.caption("🧪 Mock mode - any @ase.ro email")

    with st.form("mock_signin_form"):
        email = st.text_input(
            "Email",
            placeholder="student@ase.ro",
            label_visibility="collapsed"
        )

        display_name = st.text_input(
            "Name (optional)",
            placeholder="Your name",
            label_visibility="collapsed"
        )

        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

        if submitted:
            if not email:
                st.error("Please enter an email")
            elif not validate_ase_email(email):
                st.error("Only @ase.ro emails allowed")
            else:
                user = sign_in(email, display_name=display_name or None)
                if user:
                    st.success(f"✅ Signed in as {email}")
                    st.rerun()


def _render_firebase_sign_in():
    """
    Render Firebase sign-in (production) - Compact version
    Uses Google OAuth with Firebase Authentication
    """
    st.caption("Only @ase.ro accounts • Scores saved to leaderboard")

    # Use the dedicated Google auth button component
    from .google_auth_button import render_google_auth_button

    authenticated = render_google_auth_button()

    if authenticated:
        st.success("✅ Authenticated!")
        st.rerun()


def render_auth_status_badge():
    """
    Render a compact authentication status badge
    Useful for showing auth status in a sidebar or header
    """
    user = get_current_user()

    if user and user.get('is_authenticated'):
        display_name = user.get('display_name', 'User')
        st.success(f"✅ Signed in as **{display_name}**")
    else:
        st.warning("⚠️ Not signed in - scores won't be saved")
