# app.py

import streamlit as st
from tools import floating_point

# Define the available tools in a dictionary.
# The key is the name displayed in the sidebar, and the value is the module.
TOOLS = {
    "Floating-Point Converter": floating_point,
    # Future tools will be added here
    # "Binary Operations": binary_ops,
    # "Karnaugh Map": kmap,
}

def main():
    st.set_page_config(page_title="CS Fundamentals App", layout="wide")
    
    st.sidebar.title("Navigation")
    
    # Create a radio button in the sidebar to select the tool
    selection = st.sidebar.radio("Go to", list(TOOLS.keys()))

    # Get the selected tool's module
    tool_module = TOOLS[selection]

    # All tool modules should have a 'render' function
    # This keeps the main app clean and delegates rendering to the tool module
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