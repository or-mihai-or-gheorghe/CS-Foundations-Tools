# app.py

import streamlit as st
from tools import floating_point, decimal_converter, special_values, fp_arithmetic
from tools import hamming_encode, hamming_decode, crc_encode

# --- Data Structure for Tool Groups ---
TOOL_GROUPS = {
    "Floating Point Operations": {
        "Floating-Point Converter": floating_point,
        "Decimal Converter": decimal_converter,
        "Special Values Explorer": special_values,
        "FP Arithmetic (+/-)": fp_arithmetic
    },
    "Error Detecting & Correcting Codes": {
        "Hamming Encode": hamming_encode,
        "Hamming Decode & Correct": hamming_decode,
        "CRC Encode": crc_encode,
        "CRC Decode": None
    }
}

# Create a flattened dictionary for easy lookup of tool modules by name
ALL_TOOLS = {
    tool_name: module
    for group in TOOL_GROUPS.values()
    for tool_name, module in group.items()
}


def main():
    st.set_page_config(page_title="CS Fundamentals App", layout="wide")
    
    st.sidebar.title("CS Foundation Tools")

    # --- State Management for Unified Selection ---
    # We need to ensure that only one radio button is selected across all groups.
    # We use st.session_state to store the single, globally selected tool.

    # Initialize the selection with the first available tool if it's not already set
    if 'selection' not in st.session_state:
        st.session_state.selection = list(ALL_TOOLS.keys())[0]

    # Callback function to update the global selection when any radio button is changed
    def update_selection(key):
        st.session_state.selection = st.session_state[key]
    
    # --- Display Logic for Grouped Radio Buttons ---
    for group_name, tools in TOOL_GROUPS.items():
        st.sidebar.markdown(f"#### {group_name}")
        
        # Prepare tool names for display, adding "(not implemented)" where needed
        def format_tool_name(name):
            return f"{name} (not implemented)" if tools[name] is None else name

        tool_names_in_group = list(tools.keys())
        formatted_tool_names = [format_tool_name(name) for name in tool_names_in_group]

        # The key to making this work:
        # Determine the index of the currently selected tool within this group's list.
        # If the selected tool is not in this group, the index will be None, showing no selection.
        try:
            # Find the original name from the formatted name stored in session_state
            original_selection_name = st.session_state.selection.replace(" (not implemented)", "")
            current_selection_index = tool_names_in_group.index(original_selection_name)
        except ValueError:
            current_selection_index = None # The selected tool is not in this group

        # Each radio group needs a unique key
        radio_key = f"{group_name}_radio"

        # Display the radio button group for the current category
        st.sidebar.radio(
            label=f"Tools for {group_name}",
            options=formatted_tool_names,
            index=current_selection_index,
            key=radio_key,
            on_change=update_selection,
            args=(radio_key,), # Pass the widget's own key to the callback
            label_visibility="collapsed"
        )
        st.sidebar.markdown('<hr style="margin-top: 0; margin-bottom: 1rem;">', unsafe_allow_html=True)


    # --- Tool Rendering Logic ---
    selected_tool_formatted_name = st.session_state.selection
    
    # Find the original tool name and its module from our flattened dictionary
    original_tool_name = selected_tool_formatted_name.replace(" (not implemented)", "")
    tool_module = ALL_TOOLS.get(original_tool_name)

    if tool_module and hasattr(tool_module, 'render'):
        # If the tool is implemented, call its render function
        tool_module.render()
    elif tool_module is None:
        # If the tool is marked as not implemented, show a message
        st.header(original_tool_name)
        st.info("This tool is not yet implemented. Please check back later!")
    else:
        # Fallback for any other error
        st.error(f"The selected tool '{original_tool_name}' is not configured correctly.")
        
    st.sidebar.info(
        "This app is designed to help CS students visualize and understand fundamental concepts."
    )


if __name__ == "__main__":
    main()