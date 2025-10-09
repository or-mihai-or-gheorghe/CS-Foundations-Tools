# components/game_stats.py
"""
Game statistics display component
Shows global game statistics (all-time and recent)
"""

import streamlit as st
from firebase import get_global_stats
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def render_game_stats():
    """
    Render global game statistics
    Shows all-time games played and last 7 days
    """
    try:
        stats = get_global_stats()

        if not stats or 'global' not in stats:
            st.info("📊 No games played yet. Be the first to play!")
            return

        global_stats = stats['global']

        # Render stats in compact format
        st.markdown("### 📊 Global Stats")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_games = global_stats.get('total_all_games', 0)
            st.metric(
                label="All-Time Games",
                value=f"{total_games:,}",
                help="Total games played (all users, all time)"
            )

        with col2:
            recent_games = global_stats.get('recent_7_days', 0)
            st.metric(
                label="Last 7 Days",
                value=f"{recent_games:,}",
                help="Games played in the last 7 days"
            )

        with col3:
            auth_games = global_stats.get('total_authenticated', 0)
            st.metric(
                label="With Account",
                value=f"{auth_games:,}",
                help="Games played by signed-in users"
            )

        with col4:
            anon_games = global_stats.get('total_anonymous', 0)
            st.metric(
                label="Anonymous",
                value=f"{anon_games:,}",
                help="Games played without signing in"
            )

    except Exception as e:
        logger.error(f"Error rendering game stats: {e}")
        st.error("Failed to load stats")


def render_game_stats_compact():
    """
    Render game stats in a more compact format (single line)
    """
    try:
        stats = get_global_stats()

        if not stats or 'global' not in stats:
            return

        global_stats = stats['global']
        total = global_stats.get('total_all_games', 0)
        recent = global_stats.get('recent_7_days', 0)

        st.caption(f"🎮 {total:,} games played all-time • {recent:,} in last 7 days")

    except Exception as e:
        logger.error(f"Error rendering compact stats: {e}")


def render_per_game_stats():
    """
    Render per-game statistics breakdown
    """
    try:
        stats = get_global_stats()

        if not stats or 'by_game' not in stats:
            return

        by_game = stats['by_game']

        if not by_game:
            return

        st.markdown("#### Per-Game Breakdown")

        for game_slug, game_stats in by_game.items():
            with st.expander(f"🎮 {game_slug.replace('_', ' ').title()}", expanded=False):
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Total", f"{game_stats.get('total_games', 0):,}")

                with col2:
                    st.metric("Last 7 Days", f"{game_stats.get('recent_7_days', 0):,}")

                with col3:
                    st.metric("Authenticated", f"{game_stats.get('authenticated_games', 0):,}")

                with col4:
                    st.metric("Anonymous", f"{game_stats.get('anonymous_games', 0):,}")

                last_played = game_stats.get('last_played', 'Never')
                if last_played != 'Never':
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(last_played.replace('Z', '+00:00'))
                        st.caption(f"Last played: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
                    except:
                        st.caption(f"Last played: {last_played}")

    except Exception as e:
        logger.error(f"Error rendering per-game stats: {e}")
