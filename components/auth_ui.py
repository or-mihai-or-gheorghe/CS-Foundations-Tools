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
    Render user profile section (when signed in)

    Args:
        user: User object from session state
    """
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        # Display avatar
        photo_url = user.get('photo_url', '')
        if photo_url:
            st.image(photo_url, width=60)
        else:
            # Default avatar
            display_name = user.get('display_name', '?')
            st.markdown(f"""
            <div style="
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                font-weight: bold;
            ">{display_name[0].upper()}</div>
            """, unsafe_allow_html=True)

    with col2:
        # Display user info
        st.markdown(f"**{user.get('display_name', 'User')}**")
        st.caption(user.get('email', ''))

        if user.get('is_mock'):
            st.caption("🧪 *Mock Auth Mode (Local Dev)*")

    with col3:
        # Sign out button
        if st.button("Sign Out", type="secondary", use_container_width=True):
            sign_out()
            st.rerun()

    st.markdown("---")


def _render_sign_in_form():
    """
    Render sign-in form
    Shows different UI for mock mode vs production
    """
    st.markdown("---")

    if is_mock_mode():
        # Mock authentication (local development)
        _render_mock_sign_in()
    else:
        # Production Firebase authentication
        _render_firebase_sign_in()

    st.markdown("---")


def _render_mock_sign_in():
    """
    Render mock sign-in form (local development)
    """
    st.info("🧪 **Mock Authentication Mode** (Local Development)")
    st.caption("Sign in with any @ase.ro email from the allowed test list")

    with st.form("mock_signin_form"):
        email = st.text_input(
            "Email Address",
            placeholder="student@ase.ro",
            help="Enter an @ase.ro email address"
        )

        display_name = st.text_input(
            "Display Name (optional)",
            placeholder="John Doe",
            help="Your name as it will appear on the leaderboard"
        )

        submitted = st.form_submit_button("🔐 Sign In (Mock)", type="primary", use_container_width=True)

        if submitted:
            if not email:
                st.error("Please enter an email address")
            elif not validate_ase_email(email):
                st.error("⚠️ Only @ase.ro email addresses are allowed")
            else:
                # Attempt mock sign-in
                user = sign_in(email, display_name=display_name or None)
                if user:
                    st.success(f"✅ Signed in as {email}")
                    st.rerun()


def _render_firebase_sign_in():
    """
    Render Firebase sign-in (production)
    Uses Firebase UI Web for Google Sign-In
    """
    st.info("🔐 **Sign In**")
    st.caption("Sign in with your @ase.ro Google account to save your scores")

    # Note about domain restriction
    st.warning("⚠️ **Only @ase.ro email addresses are allowed**")

    # Firebase UI Web integration
    st.markdown("""
    <div id="firebaseui-auth-container"></div>
    """, unsafe_allow_html=True)

    # Firebase UI Web configuration
    firebase_ui_config = """
    <script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-auth-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/ui/6.0.1/firebase-ui-auth.js"></script>
    <link type="text/css" rel="stylesheet" href="https://www.gstatic.com/firebasejs/ui/6.0.1/firebase-ui-auth.css" />

    <script>
        // Firebase configuration (loaded from Streamlit secrets)
        const firebaseConfig = {
            apiKey: "YOUR_API_KEY",
            authDomain: "YOUR_AUTH_DOMAIN",
            projectId: "YOUR_PROJECT_ID"
        };

        // Initialize Firebase
        firebase.initializeApp(firebaseConfig);

        // Initialize Firebase UI
        const ui = new firebaseui.auth.AuthUI(firebase.auth());

        ui.start('#firebaseui-auth-container', {
            signInOptions: [
                {
                    provider: firebase.auth.GoogleAuthProvider.PROVIDER_ID,
                    customParameters: {
                        // Force account selection
                        prompt: 'select_account'
                    }
                }
            ],
            callbacks: {
                signInSuccessWithAuthResult: function(authResult, redirectUrl) {
                    // Get the user's email
                    const email = authResult.user.email;

                    // Validate @ase.ro domain
                    if (!email.endsWith('@ase.ro')) {
                        firebase.auth().signOut();
                        alert('Only @ase.ro email addresses are allowed');
                        return false;
                    }

                    // Get ID token and send to Streamlit
                    authResult.user.getIdToken().then(function(idToken) {
                        // Store token in localStorage for Streamlit to retrieve
                        localStorage.setItem('firebase_token', idToken);
                        localStorage.setItem('firebase_email', email);

                        // Trigger page reload to update Streamlit session
                        window.parent.location.reload();
                    });

                    return false;
                },
                signInFailure: function(error) {
                    console.error('Sign-in error:', error);
                }
            },
            signInFlow: 'popup',
            privacyPolicyUrl: function() {
                window.open('https://cs-fundamentals.streamlit.app/', '_blank');
            },
            tosUrl: function() {
                window.open('https://cs-fundamentals.streamlit.app/', '_blank');
            }
        });
    </script>
    """

    st.components.v1.html(firebase_ui_config, height=200)

    # Alternative: Manual Google Sign-In button (simpler approach)
    st.markdown("### Alternative: Manual Sign-In")

    st.info("""
    **For Production:**
    1. Click the button below to sign in with Google
    2. Make sure you're using your @ase.ro account
    3. Authorize the app to access your basic profile
    """)

    if st.button("🔐 Sign in with Google", type="primary", use_container_width=True):
        st.warning("""
        **Firebase Auth Setup Required:**

        To enable Google Sign-In, you need to:
        1. Configure Google OAuth in Firebase Console
        2. Add authorized domain: `cs-fundamentals.streamlit.app`
        3. Deploy to production (OAuth callbacks require production URL)

        For now, use local development with mock authentication.
        """)


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
