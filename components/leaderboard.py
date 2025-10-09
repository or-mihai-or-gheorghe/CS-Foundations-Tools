# components/leaderboard.py
"""
Leaderboard UI component
Displays game rankings with filtering and sorting capabilities
"""

import streamlit as st
from firebase import get_leaderboard, get_current_user
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


# Game registry for leaderboard
AVAILABLE_GAMES = {
    "binary_speed_challenge": "Binary Speed Challenge",
    # Add more games here as they are developed
}


def render_leaderboard(game_slug: Optional[str] = None):
    """
    Render leaderboard with filters

    Args:
        game_slug: Game identifier (None for global leaderboard)
    """
    st.title("🏆 Leaderboard")

    # Render filters
    filters = _render_filters(game_slug)

    # Get current user for highlighting
    current_user = get_current_user()
    current_uid = current_user.get('uid') if current_user else None

    # Fetch leaderboard data
    try:
        leaderboard_data = get_leaderboard(
            game_slug=filters['game_slug'],
            filters={
                'difficulty': filters.get('difficulty'),
                'user_search': filters.get('user_search', '')
            },
            limit=50
        )

        if not leaderboard_data:
            st.info("📊 No scores yet. Be the first to play and set a record!")
            return

        # Display leaderboard
        _render_leaderboard_table(leaderboard_data, current_uid, filters['game_slug'])

        # Show user's rank if not in top 50
        if current_uid:
            _render_user_rank_info(leaderboard_data, current_uid)

    except Exception as e:
        logger.error(f"Error rendering leaderboard: {e}")
        st.error(f"Failed to load leaderboard: {str(e)}")


def _render_filters(default_game_slug: Optional[str] = None) -> Dict:
    """
    Render filter controls

    Args:
        default_game_slug: Default game selection

    Returns:
        Dict: Selected filter values
    """
    st.markdown("### Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Game selector
        game_options = {"all": "🌐 All Games"}
        game_options.update({slug: name for slug, name in AVAILABLE_GAMES.items()})

        selected_game = st.selectbox(
            "Game",
            options=list(game_options.keys()),
            format_func=lambda x: game_options[x],
            index=0 if not default_game_slug else list(game_options.keys()).index(default_game_slug)
        )

        game_slug = None if selected_game == "all" else selected_game

    with col2:
        # Difficulty filter (only for specific games)
        difficulty = None
        if game_slug:
            difficulty = st.selectbox(
                "Difficulty",
                options=["All", "Easy", "Medium", "Hard", "Expert"],
                index=0
            )
            difficulty = None if difficulty == "All" else difficulty

    with col3:
        # User search
        user_search = st.text_input(
            "Search User",
            placeholder="name or email",
            help="Filter by user name or email"
        )

    st.markdown("---")

    return {
        'game_slug': game_slug,
        'difficulty': difficulty,
        'user_search': user_search
    }


def _render_leaderboard_table(data: List[Dict], current_uid: Optional[str], game_slug: Optional[str]):
    """
    Render leaderboard table

    Args:
        data: Leaderboard entries
        current_uid: Current user's UID (for highlighting)
        game_slug: Game identifier (None for global)
    """
    # Determine columns based on game type
    if game_slug:
        # Game-specific leaderboard
        st.markdown("#### Top Players")

        for entry in data:
            is_current_user = (entry.get('uid') == current_uid)
            _render_leaderboard_entry(entry, is_current_user, game_specific=True)

    else:
        # Global leaderboard
        st.markdown("#### Top Players (All Games)")

        for entry in data:
            is_current_user = (entry.get('uid') == current_uid)
            _render_leaderboard_entry(entry, is_current_user, game_specific=False)


def _render_leaderboard_entry(entry: Dict, is_current_user: bool, game_specific: bool):
    """
    Render a single leaderboard entry

    Args:
        entry: Leaderboard entry data
        is_current_user: Whether this is the current user
        game_specific: Whether this is a game-specific leaderboard
    """
    rank = entry.get('rank', '?')
    display_name = entry.get('display_name', 'Unknown')
    email = entry.get('email', '')

    # Rank emoji
    rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

    # Highlight current user
    bg_color = "rgba(102, 126, 234, 0.1)" if is_current_user else "transparent"
    border = "2px solid #667eea" if is_current_user else "1px solid #e0e0e0"

    if game_specific:
        # Game-specific stats
        total_score = entry.get('total_score', 0)
        games_played = entry.get('games_played', 0)
        avg_accuracy = entry.get('avg_accuracy', 0)
        best_streak = entry.get('best_streak', 0)

        html = f"""
        <div style="
            background: {bg_color};
            border: {border};
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <div style="display: flex; align-items: center; flex: 1;">
                <div style="font-size: 24px; margin-right: 16px; min-width: 60px;">
                    {rank_emoji}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: bold; font-size: 16px;">
                        {display_name} {'<span style="color: #667eea;">(You)</span>' if is_current_user else ''}
                    </div>
                    <div style="font-size: 12px; color: #666;">
                        {email}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 24px; align-items: center;">
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 18px; color: #667eea;">
                        {total_score:,}
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Points
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 16px;">
                        {games_played}
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Games
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 16px;">
                        {avg_accuracy:.1f}%
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Accuracy
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 16px;">
                        🔥 {best_streak}
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Best Streak
                    </div>
                </div>
            </div>
        </div>
        """
    else:
        # Global stats
        total_score = entry.get('total_score_all_games', 0)
        games_played = entry.get('total_games_all_types', 0)
        games_breakdown = entry.get('games_breakdown', {})
        breakdown_text = ", ".join([f"{AVAILABLE_GAMES.get(k, k)}: {v}" for k, v in games_breakdown.items()])

        html = f"""
        <div style="
            background: {bg_color};
            border: {border};
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <div style="display: flex; align-items: center; flex: 1;">
                <div style="font-size: 24px; margin-right: 16px; min-width: 60px;">
                    {rank_emoji}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: bold; font-size: 16px;">
                        {display_name} {'<span style="color: #667eea;">(You)</span>' if is_current_user else ''}
                    </div>
                    <div style="font-size: 12px; color: #666;">
                        {email}
                    </div>
                    <div style="font-size: 11px; color: #888; margin-top: 4px;">
                        {breakdown_text}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 32px; align-items: center;">
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 18px; color: #667eea;">
                        {total_score:,}
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Total Points
                    </div>
                </div>
                <div style="text-align: center;">
                    <div style="font-weight: bold; font-size: 16px;">
                        {games_played}
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        Total Games
                    </div>
                </div>
            </div>
        </div>
        """

    st.markdown(html, unsafe_allow_html=True)


def _render_user_rank_info(leaderboard_data: List[Dict], current_uid: str):
    """
    Show current user's rank if not in top 50

    Args:
        leaderboard_data: Leaderboard entries
        current_uid: Current user's UID
    """
    # Check if user is in displayed data
    user_in_top = any(entry.get('uid') == current_uid for entry in leaderboard_data)

    if not user_in_top:
        st.info("💡 Keep playing to break into the top 50!")


def render_leaderboard_compact(game_slug: str, limit: int = 5):
    """
    Render a compact leaderboard (useful for game result screen)

    Args:
        game_slug: Game identifier
        limit: Number of entries to show
    """
    st.markdown("### 🏆 Top Players")

    try:
        leaderboard_data = get_leaderboard(game_slug=game_slug, limit=limit)

        if not leaderboard_data:
            st.info("No scores yet. Be the first!")
            return

        # Simple table view
        for entry in leaderboard_data:
            rank = entry.get('rank', '?')
            rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

            display_name = entry.get('display_name', 'Unknown')
            total_score = entry.get('total_score', 0)

            st.markdown(f"{rank_emoji} **{display_name}** - {total_score:,} points")

        st.caption("View full leaderboard in Games Hub")

    except Exception as e:
        logger.error(f"Error rendering compact leaderboard: {e}")
        st.error("Failed to load leaderboard")
