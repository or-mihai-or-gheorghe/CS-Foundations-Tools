# tools/games/games_hub.py

import streamlit as st
from . import binary_speed_challenge

# ========================= Games Registry =========================

AVAILABLE_GAMES = {
    "Binary Speed Challenge": {
        "module": binary_speed_challenge,
        "description": "Convert binary and decimal numbers as fast as you can!",
        "emoji": "⚡",
        "difficulty": "Easy to Expert",
        "duration": "60 seconds",
        "skills": ["Binary Conversion", "Speed", "Accuracy"],
        "features": [
            "4 difficulty levels (Easy to Expert)",
            "Multiple game modes (Binary↔Decimal)",
            "Direct input or multiple choice",
            "Streak multipliers and speed bonuses",
            "Real-time countdown timer"
        ]
    }
    # Future games will be added here
}

# ========================= State Management =========================

def init_games_hub_state():
    """Initialize games hub state"""
    if 'games_hub' not in st.session_state:
        st.session_state.games_hub = {
            'selected_game': None,
            'show_landing': True
        }

def select_game(game_name: str):
    """Select a game to play"""
    st.session_state.games_hub['selected_game'] = game_name
    st.session_state.games_hub['show_landing'] = False

def return_to_landing():
    """Return to games landing page"""
    st.session_state.games_hub['selected_game'] = None
    st.session_state.games_hub['show_landing'] = True

# ========================= UI Components =========================

def render_game_card(game_name: str, game_info: dict):
    """Render a game card with info and play button"""

    with st.container():
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            <h2 style="color: white; margin: 0 0 10px 0;">
                {game_info['emoji']} {game_name}
            </h2>
            <p style="color: rgba(255,255,255,0.9); font-size: 16px; margin: 0;">
                {game_info['description']}
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**⏱️ Duration:** {game_info['duration']}")
            st.markdown(f"**📊 Difficulty:** {game_info['difficulty']}")
            st.markdown(f"**🎯 Skills:** {', '.join(game_info['skills'])}")

            with st.expander("📋 Features", expanded=False):
                for feature in game_info['features']:
                    st.markdown(f"- {feature}")

        with col2:
            st.markdown("")  # Spacing
            st.markdown("")  # Spacing
            if st.button(
                f"▶️ Play {game_name}",
                key=f"play_{game_name}",
                type="primary",
                use_container_width=True
            ):
                select_game(game_name)
                st.rerun()

def render_landing_page():
    """Render games landing page with all available games"""

    st.title("🎮 Games Hub")

    st.markdown("""
    Welcome to the **CS Fundamentals Games Hub**!

    Test your skills with interactive games designed to reinforce computer science concepts.
    Challenge yourself, compete against the clock, and master binary operations through fun gameplay!
    """)

    st.markdown("---")

    st.subheader(f"🎯 Available Games ({len(AVAILABLE_GAMES)})")

    # Render each game card
    for game_name, game_info in AVAILABLE_GAMES.items():
        render_game_card(game_name, game_info)

    st.markdown("---")

    # Coming soon section
    with st.expander("🚀 Coming Soon", expanded=False):
        st.markdown("""
        ### Future Games

        - **🧠 Binary Pattern Memory** - Remember and reproduce binary sequences
        - **🔧 Bit Manipulation Puzzle** - Achieve target with AND, OR, XOR, SHIFT
        - **🏃 Gray Code Race** - Navigate Gray code sequences quickly
        - **🎲 Floating Point Challenge** - Master IEEE 754 precision
        - **🛡️ Hamming Code Debug** - Find and fix transmission errors
        - **⚡ Boolean Speedrun** - Simplify expressions with K-maps
        - **🔐 CRC Challenge** - Calculate checksums under pressure

        *Have an idea for a game? Let us know!*
        """)

def render_game_screen(game_name: str):
    """Render the selected game with a back button"""

    game_info = AVAILABLE_GAMES[game_name]
    game_module = game_info['module']

    # Add back button at the top
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if st.button("← Back to Games", key="back_to_games"):
            # Reset any game state when returning
            if 'binary_game' in st.session_state:
                st.session_state.binary_game['active'] = False
            return_to_landing()
            st.rerun()

    # Render the game
    if hasattr(game_module, 'render'):
        game_module.render()
    else:
        st.error(f"Game '{game_name}' is not properly configured.")

# ========================= Main Render Function =========================

def render():
    """Main render function for games hub"""
    init_games_hub_state()

    hub = st.session_state.games_hub

    if hub['show_landing'] or hub['selected_game'] is None:
        render_landing_page()
    else:
        render_game_screen(hub['selected_game'])
