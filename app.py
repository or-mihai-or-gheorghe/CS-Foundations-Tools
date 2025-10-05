# app.py

import streamlit as st

# Configure page
st.set_page_config(
    page_title="CS Fundamentals - Bucharest University of Economic Studies",
    layout="wide"
)

# Define navigation pages
pages = [
    st.Page("pages/foundations.py", title="💻 Foundations", default=True),
    st.Page("pages/games_hub.py", title="🎮 Games Hub"),
]

# Create and run navigation
pg = st.navigation(pages)
pg.run()
