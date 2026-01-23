# app.py

import streamlit as st

# Configure page
st.set_page_config(
    page_title="CS Fundamentals - Bucharest University of Economic Studies",
    layout="wide"
)

# ============================================================
# EXAM MODE - Good Luck Message
# Uncomment the section below and comment out this section to restore normal functionality
# ============================================================

st.markdown("""
<style>
    .main {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 80vh;
    }
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .good-luck-container {
        text-align: center;
        padding: 60px;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 25px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        max-width: 700px;
        margin: auto;
    }
    .good-luck-emoji {
        font-size: 80px;
        margin-bottom: 20px;
    }
    .good-luck-title {
        font-size: 48px;
        font-weight: bold;
        color: #2d3748;
        margin-bottom: 20px;
    }
    .good-luck-subtitle {
        font-size: 24px;
        color: #4a5568;
        margin-bottom: 30px;
    }
    .good-luck-message {
        font-size: 18px;
        color: #718096;
        line-height: 1.8;
        margin-bottom: 30px;
    }
    .university-name {
        font-size: 14px;
        color: #a0aec0;
        margin-top: 30px;
    }
</style>

<div class="good-luck-container">
    <div class="good-luck-emoji">🍀📚✨</div>
    <div class="good-luck-title">Good Luck!</div>
    <div class="good-luck-subtitle">CS Foundations Exam Day</div>
    <div class="good-luck-message">
        You've prepared well. Trust your knowledge.<br>
        Take a deep breath, stay calm, and do your best!<br><br>
        <strong>Remember:</strong> Read each question carefully,<br>
        manage your time wisely, and believe in yourself.
    </div>
    <div style="font-size: 40px;">💪🎯🏆</div>
    <div class="university-name">
        Bucharest University of Economic Studies<br>
        Faculty of Economic Cybernetics, Statistics and Informatics
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# NORMAL MODE - Uncomment below to restore functionality
# ============================================================
# # Define navigation pages
# pages = [
#     st.Page("pages/foundations.py", title="💻 Foundations", default=True),
#     st.Page("pages/games_hub.py", title="🎮 Games Hub"),
# ]
#
# # Create and run navigation
# pg = st.navigation(pages)
# pg.run()
