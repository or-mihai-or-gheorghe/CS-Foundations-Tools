# pages/1_🎮_Games_Hub.py

import streamlit as st
from tools.games import binary_speed_challenge
from components.streamlit_auth import render_auth_ui, render_auth_status_badge
from components.leaderboard import render_leaderboard
from components.game_stats import render_game_stats, render_per_game_stats

# ========================= Games Registry =========================

AVAILABLE_GAMES = {
    "Binary Speed Challenge": {
        "module": binary_speed_challenge,
        "description": "Convert binary and decimal numbers as fast as you can! Choose your difficulty, build streaks for multipliers, and race against the clock.",
        "emoji": "⚡",
        "difficulty": "Easy to Expert",
        "duration": "60 seconds",
        "skills": ["Binary Conversion", "Speed", "Accuracy"]
    }
}

# ========================= State Management =========================

def init_games_hub_state():
    """Initialize games hub state"""
    if 'games_hub' not in st.session_state:
        st.session_state.games_hub = {
            'selected_game': None,
            'show_landing': True,
            'active_tab': 'games'  # 'games' or 'leaderboard'
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
            <p style="color: rgba(255,255,255,0.95); font-size: 16px; margin: 0; line-height: 1.5;">
                {game_info['description']}
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**⏱️ Duration:** {game_info['duration']}")
            st.markdown(f"**📊 Difficulty:** {game_info['difficulty']}")
            st.markdown(f"**🎯 Skills:** {', '.join(game_info['skills'])}")

        with col2:
            st.markdown("")  # Spacing
            st.markdown("")  # Spacing
            if st.button(
                "▶ Play",
                key=f"play_{game_name}",
                type="primary",
                use_container_width=True
            ):
                select_game(game_name)
                st.rerun()

def render_landing_page():
    """Render games landing page with all available games"""

    st.title("🎮 Games Hub")

    # Authentication UI at the top (compact)
    render_auth_ui()

    # Compact welcome message
    st.caption("Test your CS skills with interactive games. Compete and climb the leaderboard!")

    # Tab selection
    tab1, tab2, tab3 = st.tabs(["🎮 Games", "🏆 Leaderboard", "📊 Stats"])

    with tab1:
        st.subheader(f"🎯 Available Games ({len(AVAILABLE_GAMES)})")

        # Render each game card
        for game_name, game_info in AVAILABLE_GAMES.items():
            render_game_card(game_name, game_info)

    with tab2:
        # Render leaderboard
        render_leaderboard()

    with tab3:
        # Render stats (no redundant titles - tab name is clear)
        render_game_stats()
        st.markdown("---")
        render_per_game_stats()

def render_game_screen(game_name: str):
    """Render the selected game with a back button"""

    game_info = AVAILABLE_GAMES[game_name]
    game_module = game_info['module']

    # Add back button and auth status at the top
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Back to Games", key="back_to_games"):
            # Reset any game state when returning
            if 'binary_game' in st.session_state:
                st.session_state.binary_game['active'] = False
            return_to_landing()
            st.rerun()

    with col3:
        # Show compact auth status
        render_auth_status_badge()

    # Render the game
    if hasattr(game_module, 'render'):
        game_module.render()
    else:
        st.error(f"Game '{game_name}' is not properly configured.")

# ========================= Main Page Logic =========================

def main():
    """Main function for Games Hub page"""
    init_games_hub_state()

    hub = st.session_state.games_hub

    if hub['show_landing'] or hub['selected_game'] is None:
        render_landing_page()
    else:
        render_game_screen(hub['selected_game'])

if __name__ == "__main__":
    main()
