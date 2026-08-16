import os
import streamlit as st
import streamlit.components.v1 as components

# --- One-time component registration ---
# Point this at the folder containing index.html (adjust the path to wherever
# you put the "mahjong_frontend" folder relative to this file).
_component_dir = os.path.join(os.path.dirname(__file__), "mahjong_frontend")
_mahjong_component = components.declare_component("mahjong_table", path=_component_dir)


def display_mahjong_table(key="mahjong_table_component"):
    rotation = st.session_state.get("table_rotation", 0)
    seating = st.session_state.game["seating"]

    east_player = st.session_state.game["players"][seating["east"]]["name"] if seating["east"] else "Empty"
    south_player = st.session_state.game["players"][seating["south"]]["name"] if seating["south"] else "Empty"
    west_player = st.session_state.game["players"][seating["west"]]["name"] if seating["west"] else "Empty"
    north_player = st.session_state.game["players"][seating["north"]]["name"] if seating["north"] else "Empty"

    result = _mahjong_component(
        rotation=rotation,
        east=east_player,
        south=south_player,
        west=west_player,
        north=north_player,
        dice_roll=st.session_state.get("dice_roll", ["east", 0]),
        key=key,
        default=None,
    )

    if result:
        if result.get("type") == "player_click":
            st.session_state.selected_player = result["value"]
        elif result.get("type") == "rotation":
            st.session_state.table_rotation = result["value"]