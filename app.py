# app.py

import streamlit as st
from tools import floating_point, decimal_converter, special_values

# Define the available tools in a dictionary.
TOOLS = {
    "Floating-Point Converter": floating_point,
    "Decimal Converter": decimal_converter,
    "Special Values Explorer": special_values, # --- CHANGE 2: Add the new tool here ---
}

def main():
    st.set_page_config(page_title="CS Fundamentals App", layout="wide")
    
    st.sidebar.title("Navigation")
    
    selection = st.sidebar.radio("Go to", list(TOOLS.keys()))

    tool_module = TOOLS[selection]

    if hasattr(tool_module, 'render'):
        tool_module.render()
    else:
        st.error(f"The selected tool '{selection}' is not implemented correctly.")
        
    st.sidebar.markdown("---")
    st.sidebar.info(
        "This app is designed to help CS students visualize and understand fundamental concepts. "
        "Built by a fellow educator."
    )


if __name__ == "__main__":
    main()