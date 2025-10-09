# components/google_auth_button.py
"""
Google OAuth button component for Streamlit
Handles OAuth flow using Firebase Authentication popup
"""

import streamlit as st
import streamlit.components.v1 as components


def render_google_auth_button():
    """
    Render a Google Sign-In button that handles OAuth in a popup
    Returns True if authentication was successful
    """

    # Get Firebase config
    try:
        api_key = st.secrets["firebase"]["api_key"]
        auth_domain = st.secrets["firebase"]["auth_domain"]
        project_id = st.secrets["firebase"]["project_id"]
    except Exception as e:
        st.error(f"Firebase configuration missing: {e}")
        return False

    # Create a unique key for this component instance
    component_key = "google_auth_component"

    # HTML/JavaScript for Google Sign-In with Firebase
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js"></script>
        <script src="https://www.gstatic.com/firebasejs/9.22.0/firebase-auth-compat.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                padding: 10px;
            }}
            .google-btn {{
                background: white;
                border: 1px solid #dadce0;
                border-radius: 4px;
                padding: 10px 16px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 12px;
                width: 100%;
                font-size: 14px;
                font-weight: 500;
                color: #3c4043;
                transition: all 0.2s;
            }}
            .google-btn:hover {{
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border-color: #d2d3d4;
            }}
            .google-btn:active {{
                background: #f8f9fa;
            }}
            .google-btn:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
            }}
            .google-icon {{
                width: 20px;
                height: 20px;
            }}
            .status {{
                margin-top: 12px;
                padding: 10px;
                border-radius: 4px;
                font-size: 13px;
                display: none;
            }}
            .status.show {{ display: block; }}
            .status.success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .status.error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            .status.info {{ background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }}
        </style>
    </head>
    <body>
        <button id="google-signin-btn" class="google-btn">
            <svg class="google-icon" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span id="btn-text">Sign in with Google</span>
        </button>
        <div id="status" class="status"></div>

        <script>
            const firebaseConfig = {{
                apiKey: "{api_key}",
                authDomain: "{auth_domain}",
                projectId: "{project_id}"
            }};

            let app;
            let auth;

            try {{
                app = firebase.initializeApp(firebaseConfig);
                auth = firebase.auth();
            }} catch (error) {{
                console.error("Firebase initialization error:", error);
                showStatus("Configuration error: " + error.message, "error");
            }}

            const btn = document.getElementById('google-signin-btn');
            const statusDiv = document.getElementById('status');
            const btnText = document.getElementById('btn-text');

            function showStatus(message, type) {{
                statusDiv.textContent = message;
                statusDiv.className = 'status show ' + type;
            }}

            function hideStatus() {{
                statusDiv.className = 'status';
            }}

            async function signIn() {{
                try {{
                    btn.disabled = true;
                    btnText.textContent = 'Opening sign-in...';
                    hideStatus();

                    const provider = new firebase.auth.GoogleAuthProvider();
                    provider.setCustomParameters({{
                        hd: 'ase.ro',
                        prompt: 'select_account'
                    }});

                    const result = await auth.signInWithPopup(provider);
                    const user = result.user;

                    // Validate domain
                    if (!user.email.endsWith('@ase.ro')) {{
                        await auth.signOut();
                        throw new Error('Only @ase.ro email addresses are allowed');
                    }}

                    btnText.textContent = 'Signed in!';
                    showStatus('✅ Success! Refreshing page...', 'success');

                    // Get token
                    const token = await user.getIdToken();

                    // Send auth data to Streamlit using query params
                    const params = new URLSearchParams({{
                        auth_token: token,
                        auth_email: user.email,
                        auth_name: user.displayName || user.email.split('@')[0],
                        auth_photo: user.photoURL || '',
                        auth_uid: user.uid
                    }});

                    // Reload with auth params
                    window.top.location.href = window.top.location.pathname + '?' + params.toString();

                }} catch (error) {{
                    console.error('Sign-in error:', error);
                    btn.disabled = false;
                    btnText.textContent = 'Sign in with Google';

                    if (error.code === 'auth/popup-closed-by-user') {{
                        showStatus('Sign-in cancelled', 'info');
                    }} else if (error.code === 'auth/popup-blocked') {{
                        showStatus('❌ Popup blocked. Please allow popups.', 'error');
                    }} else {{
                        showStatus('❌ ' + error.message, 'error');
                    }}
                }}
            }}

            btn.addEventListener('click', signIn);

            // Check for existing auth state
            auth.onAuthStateChanged(async (user) => {{
                if (user && user.email.endsWith('@ase.ro')) {{
                    btn.disabled = true;
                    btnText.textContent = 'Signed in as ' + user.displayName;
                    showStatus('Already authenticated', 'success');

                    // Send token to Streamlit
                    const token = await user.getIdToken();
                    const params = new URLSearchParams({{
                        auth_token: token,
                        auth_email: user.email,
                        auth_name: user.displayName || user.email.split('@')[0],
                        auth_photo: user.photoURL || '',
                        auth_uid: user.uid
                    }});

                    // Only redirect if not already authenticated in Streamlit
                    if (!window.top.location.search.includes('auth_token')) {{
                        setTimeout(() => {{
                            window.top.location.href = window.top.location.pathname + '?' + params.toString();
                        }}, 1000);
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """

    # Render the component
    components.html(html_code, height=120, scrolling=False)

    # Check for auth callback in query parameters
    query_params = st.query_params

    if 'auth_token' in query_params:
        token = query_params.get('auth_token')
        email = query_params.get('auth_email')
        name = query_params.get('auth_name')
        photo = query_params.get('auth_photo')
        uid = query_params.get('auth_uid')

        # Sign in the user
        from firebase import sign_in

        user = sign_in(email, token=token, display_name=name)

        if user:
            # Clear query params
            st.query_params.clear()
            return True

    return False
