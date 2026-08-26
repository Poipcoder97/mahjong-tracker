import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import gzip
import base64
from io import BytesIO
from mahjong_table import display_mahjong_table as render_mahjong_table
from datetime import datetime

CHARACTERS = ["東", "南", "西", "北"]
DIRECTIONS = ["east", "south", "west", "north"]
COMMON_BONUSES_CHINESE = [
    "中洞",  # zhōng dòng
    "邊張",  # biān zhāng
    "單吊",  # dān diào
    "門清"   # mén qīng
]
COMMON_BONUSES_PINYIN = [
    "zhōng dòng", 
    "biān zhāng", 
    "dān diào", 
    "mén qīng"
]
MORE_BONUSES_VALUE = [1, 1, 1, 1, 4, 8, 2, 5, 8, 4, 8, 16, 4, 8, 8, 16, 4, 8, 16, 24]
MORE_BONUSES_COLOR = ["blue", "yellow", "green", "red", "red", "orange", "violet", "blue", "red", "yellow", "orange", "red", "green", "red", "blue", "violet", "orange", "orange", "red", "red"]
MORE_BONSUES_ICON = ["hive", "phishing", "screenshot_frame", "mobile_theft", "width_normal", "filter_8", "looks_3", "looks_4", "looks_5", "star_half", "star", "star_shine", "gesture", "thread_unread", "draw_abstract", "draw_collage", "travel_explore", "planet", "globe_location_pin", "social_leaderboard"]
MORE_BONUSES_CHINESE = [
    "槓上自摸",    #0 gàng shàng zì mō
    "海底撈月",    #1 hǎidǐ lāoyuè
    "全求人",      #2 quán qiú rén
    "搶槓",        #3 qiāng gàng
    "碰碰胡",      #4 pèng pèng hú
    "niko niko",  #5 niko niko
    "三暗刻",      #6 sān àn kè
    "四暗刻",      #7 sì àn kè
    "五暗刻",      #8 wǔ àn kè
    "混一色",      #9 hùn yī sè
    "清一色",      #10 qīng yī sè
    "字一色",      #11 zì yī sè
    "小三元",      #12 xiǎo sān yuán
    "大三元",      #13 dà sān yuán
    "小四喜",      #14 xiǎo sì xǐ
    "大四喜",      #15 dà sì xǐ
    "地聽",        #16 dì tīng
    "天聽",        #17 tiān tīng
    "地胡",        #18 dì hú
    "天胡"         #19 tiān hú
]
MORE_BONUSES_PINYIN = [
    "gàng shàng zì mō",
    "hǎidǐ lāoyuè",
    "quán qiú rén",
    "qiāng gàng",
    "pèng pèng hú",
    "niko niko",
    "sān àn kè",
    "sì àn kè",
    "wǔ àn kè",
    "hùn yī sè",
    "qīng yī sè",
    "zì yī sè",
    "xiǎo sān yuán",
    "dà sān yuán",
    "xiǎo sì xǐ",
    "dà sì xǐ",
    "dì tīng",
    "tiān tīng",
    "dì hú",
    "tiān hú"
]

def num_to_chinese(num):
    chinese_numbers = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九",
        10: "十"
    }
    return chinese_numbers.get(num, str(num))

def calculate_score(round_data):
    if round_data["draw"] or round_data["winner"] is None or round_data["loser"] is None or round_data["east_seat"] is None:
        return [0,0,0,0], [0,0,0,0]
    base_points = st.session_state.game["settings"]["base_points"]
    bonus_points = st.session_state.game["settings"]["bonus_points"]
    bonus_data = round_data["bonuses"].copy()
    winner = round_data["winner"]
    loser = round_data["loser"]
    dice_roller = round_data["round"] - 1
    streak = round_data["streak"]
    bonus_count = 0
    bonus_count += 1 if winner == loser else 0
    for i in range(2):
        bonus_count += 1 if bonus_data["flowers"][i] else 0
        bonus_count += 1 if bonus_data["winds"][i] else 0
    for dragon in bonus_data["dragons"]:
        bonus_count += 1 if dragon else 0
    bonus_count += 1 if any(bonus_data["common"][0:3]) else 0
    bonus_count += 1 if bonus_data["common"][3] and winner != loser else 2 if bonus_data["common"][3] and winner == loser else 0
    for i in range(20):
        bonus_count += MORE_BONUSES_VALUE[i] if bonus_data["more"][i] else 0
    if (winner == dice_roller) != (loser == dice_roller):
        bonus_count += 1 + 2*streak
    if winner == loser:
        if winner == dice_roller:
            bonus_count += 1 + 2*streak
            bonuses = [bonus_count if i == winner else 0-bonus_count for i in range(4)]
            points = [3*(base_points + bonus_points*bonus_count) if i == winner else 0-base_points-bonus_points*bonus_count for i in range(4)]
        else:
            bonuses = [bonus_count if i == winner else 0-bonus_count for i in range(4)]
            points = [3*(base_points + bonus_points*bonus_count) if i == winner else 0-base_points-bonus_points*bonus_count for i in range(4)]
            points[winner] += bonus_points * (1 + 2*streak)
            points[dice_roller] -= bonus_points * (1 + 2*streak)
            bonuses[winner] += 1 + 2*streak
            bonuses[dice_roller] -= 1 + 2*streak
    else:
        points, bonuses = [0,0,0,0], [0,0,0,0]
        points[winner] = base_points + bonus_count*bonus_points
        points[loser] = 0-points[winner]
        bonuses[winner] = bonus_count
        bonuses[loser] = 0-bonus_count
    return points, bonuses

def generate_scoresheets():
    scores = {"Round": []}
    for player in st.session_state.players:
        scores[player] = []
    for round_data in st.session_state.game["rounds"]:
        if round_data["draw"] or round_data["winner"] is not None and round_data["loser"] is not None and round_data["east_seat"] is not None:
            name = f"{CHARACTERS[round_data['current_cycle']]}{num_to_chinese(round_data['round'])}"
            if round_data["streak"] > 0:
                name += f" (連{num_to_chinese(round_data['streak'])})"
            scores["Round"].append(name)
            points = calculate_score(round_data)[0]
            for idx, player in enumerate(st.session_state.players):
                scores[player].append(points[idx])
    scores_df = pd.DataFrame(scores)
    if scores_df.empty:
        scores_df = pd.DataFrame([["東一", 0, 0, 0, 0]], columns=(["Round"]+st.session_state.players))
    st.session_state.scores_df = scores_df
    st.session_state.cumulative_scores_df = pd.concat([pd.DataFrame([[0, 0, 0, 0]], columns=st.session_state.players), pd.DataFrame({player: scores_df[player].cumsum() for player in st.session_state.players})], ignore_index=True)
    rankings = sorted(list(set(st.session_state.cumulative_scores_df.iloc[-1])), reverse=True)
    player_rankings = []
    for player in st.session_state.players:
        player_rankings.append(rankings.index(st.session_state.cumulative_scores_df[player].iloc[-1]))
    st.session_state.player_rankings = player_rankings

def get_badges(round_data, bonus_seat):
    badges = ""
    if round_data["draw"] or bonus_seat == -1:
        return badges
    common_bonuses_labels = COMMON_BONUSES_PINYIN if st.session_state.use_pinyin else COMMON_BONUSES_CHINESE
    more_bonuses_labels = MORE_BONUSES_PINYIN if st.session_state.use_pinyin else MORE_BONUSES_CHINESE
    bonus_data = round_data["bonuses"]
    if round_data["round"]-1 in (round_data["winner"], round_data["loser"]) or round_data["winner"] == round_data["loser"]:
        badges += ":yellow-badge[:material/military_tech: zhuāng jiā (1)] " if st.session_state.use_pinyin else ":yellow-badge[:material/military_tech: 莊家 (1)] "
        if round_data["streak"] > 0:
            badges += f':green-badge[:material/motion_blur: lián {round_data["streak"]} ({round_data["streak"]*2})] ' if st.session_state.use_pinyin else f':green-badge[:material/motion_blur: 連 {num_to_chinese(round_data["streak"])} ({round_data["streak"]*2})] '
    badges += (":blue-badge[:material/mobile_theft: 自摸 (1)]" if not st.session_state.use_pinyin else ":blue-badge[:material/mobile_theft: zì mō (1)]") if round_data["winner"] == round_data["loser"] and not bonus_data["common"][3] and not any(bonus_data["more"][0:2]) else ""
    badges += (":blue-badge[:material/sweep: 門清一摸三 (3)]" if not st.session_state.use_pinyin else ":blue-badge[:material/sweep: mén qīng yī mō sān (3)]") if round_data["winner"] == round_data["loser"] and bonus_data["common"][3] else ""
    badges += (f":green-badge[:material/deceased: {num_to_chinese(bonus_seat+1)}花 (1)]" if not st.session_state.use_pinyin else f":green-badge[:material/deceased: {bonus_seat+1} huā (1)]") if bonus_data["flowers"][0] else ""
    badges += (f":yellow-badge[:material/local_florist: {num_to_chinese(bonus_seat+1)}花 (1)]" if not st.session_state.use_pinyin else f":yellow-badge[:material/local_florist: {bonus_seat+1} huā (1)]") if bonus_data["flowers"][1] else ""
    badges += f":orange-badge[:material/air: {CHARACTERS[bonus_seat]} (1)]" if bonus_data["winds"][0] else ""
    badges += f":violet-badge[:material/nest_eco_leaf: {CHARACTERS[round_data['current_cycle']]} (1)]" if bonus_data["winds"][1] else ""
    badges += (":red-badge[:material/route: 紅中 (1)]" if not st.session_state.use_pinyin else ":red-badge[:material/route: hóng zhōng (1)]") if bonus_data["dragons"][0] else ""
    badges += (":green-badge[:material/poker_chip: 青發 (1)]" if not st.session_state.use_pinyin else ":green-badge[:material/poker_chip: qīng fā (1)]") if bonus_data["dragons"][1] else ""
    badges += (":gray-badge[:material/fullscreen_portrait: 白皮 (1)]" if not st.session_state.use_pinyin else ":gray-badge[:material/fullscreen_portrait: bái pí (1)]") if bonus_data["dragons"][2] else ""
    for i in range(3):
        if bonus_data["common"][i]:
            badges += f":orange-badge[:material/repeat_one: {common_bonuses_labels[i]} (1)]"
    badges += f":green-badge[:material/cleaning_services: {common_bonuses_labels[3]} (1)]" if bonus_data["common"][3] and round_data["winner"] != round_data["loser"] else ""
    for i in range(20):
        if bonus_data["more"][i]:
            if i in (0, 1):
                badges += f":{MORE_BONUSES_COLOR[i]}-badge[:material/{MORE_BONSUES_ICON[i]}: {more_bonuses_labels[i]} ({MORE_BONUSES_VALUE[i]+1})] "
            else:
                badges += f":{MORE_BONUSES_COLOR[i]}-badge[:material/{MORE_BONSUES_ICON[i]}: {more_bonuses_labels[i]} ({MORE_BONUSES_VALUE[i]})] "
    return badges

def get_direction(rotation):
    directions = ["東 (East)", "南 (South)", "西 (West)", "北 (North)"]
    index = int((rotation / 90) % 4)
    return directions[index]

def get_direction_character(rotation):
    index = int((rotation / 90) % 4)
    return CHARACTERS[index]

# URL query param compression
PERSIST_KEYS = ["game", "game_start_time", "dice_roll", "game_finish", "min_bonus", "use_pinyin", "editing_round"]
QUERY_PARAM_KEY = "s"

def _json_default(obj):
    if isinstance(obj, datetime):
        return {"__datetime__": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def _json_object_hook(d):
    if "__datetime__" in d:
        return datetime.fromisoformat(d["__datetime__"])
    return d

def encode_game_state():
    payload = {k: st.session_state[k] for k in PERSIST_KEYS if k in st.session_state}
    raw = json.dumps(payload, default=_json_default, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")

def decode_game_state(encoded):
    try:
        compressed = base64.urlsafe_b64decode(encoded.encode("ascii"))
        raw = gzip.decompress(compressed)
        return json.loads(raw.decode("utf-8"), object_hook=_json_object_hook)
    except Exception:
        return None

def save_state_to_query_params():
    st.query_params[QUERY_PARAM_KEY] = encode_game_state()

def clear_query_params():
    if QUERY_PARAM_KEY in st.query_params:
        del st.query_params[QUERY_PARAM_KEY]

def reset_game():
    for key in PERSIST_KEYS + ["ui", "selected_player", "winner", "loser", "east_seat", "current_cycle", "table_rotation", "players"]:
        if key in st.session_state:
            del st.session_state[key]
    clear_query_params()
    st.rerun()

def initialize_game_state():
    if "game" not in st.session_state and QUERY_PARAM_KEY in st.query_params:
        restored = decode_game_state(st.query_params[QUERY_PARAM_KEY])
        if restored:
            for key, value in restored.items():
                st.session_state[key] = value
    if "game" not in st.session_state:
        st.session_state.game = {
            "players": {},
            "seating": {"east": None, "south": None, "west": None, "north": None},
            "rounds": [{
                "current_cycle": 0,
                "round": 1,
                "streak": 0,
                "winner": None,
                "loser": None, # If winner == loser, then zi mo
                "east_seat": None,
                "draw": False,
                "bonuses": {
                    "flowers": [False, False], # [Flower #1, Flower #2]
                    "winds": [False, False], # [Seat Wind, Cycle Wind]
                    "dragons": [False, False, False], # [zhōng, fā, bái]
                    "common": [False, False, False, False], # [zhōng dòng, biān zhāng, dān diào, mén qīng]
                    "more": [False for _ in range(20)] # [gàng shàng, hǎidǐ lāo, quán qiú rén, qiāng gàng, pèng pèng hú, niko niko, sān àn kè, sì àn kè, wǔ àn kè, hùn yī sè, qīng yī sè, zì yī sè, xiǎo sān yuán, dà sān yuán, xiǎo sì xǐ, dà sì xǐ, dì tīng, tiān tīng, dì hú, tiān hú]
                },
                "timestamp": None,
                "duration": None
            }],
            "settings": {"base_points": 5, "bonus_points": 2},
        }
    if "ui" not in st.session_state:
        st.session_state.ui = {"selected_player": None}
    if "dice_roll" not in st.session_state:
        st.session_state.dice_roll = ["east", 0]
    if "winner" not in st.session_state:
        st.session_state.winner = None
    if "loser" not in st.session_state:
        st.session_state.loser = None
    if "east_seat" not in st.session_state:
        st.session_state.east_seat = None
    if "current_cycle" not in st.session_state:
        st.session_state.current_cycle = 0
    if "game_start_time" not in st.session_state:
        st.session_state.game_start_time = None
    if "min_bonus" not in st.session_state:
        st.session_state.min_bonus = 0
    if "game_finish" not in st.session_state:
        st.session_state.game_finish = False
    if "players" not in st.session_state:
        st.session_state.players = []
    if "use_pinyin" not in st.session_state:
        st.session_state.use_pinyin = False
    

class Modules:
    def startup():
        st.set_page_config(page_title="Mahjong Tracker", page_icon="🀄", layout="centered")
        st.title("Mahjong Score Tracker")

    @staticmethod
    def display_mahjong_table(k="mahjong_table_component"):
        render_mahjong_table(key=k)
        st.session_state.selected_player = None

    @staticmethod
    def display_player_setup_tap():
        if "selected_player" not in st.session_state.ui:
            st.session_state.ui["selected_player"] = None
        st.markdown("#### 1. Enter Player Names")
        st.caption("Enter player names, then tap to assign seats")
        cols = st.columns(4)
        player_ids = list(st.session_state.game["players"].keys())
        if len(player_ids) < 4:
            for i in range(len(player_ids), 4):
                new_id = f"p{i+1}"
                st.session_state.game["players"][new_id] = {"name": "", "seat": None}
        player_ids = list(st.session_state.game["players"].keys())[:4]
        name_changed = False
        for i in range(4):
            with cols[i]:
                current_name = st.session_state.game["players"][player_ids[i]]["name"]
                new_name = st.text_input(f"Player {i+1}", value=current_name, key=f"name_input_{player_ids[i]}", placeholder=f"Player {i+1}", label_visibility="collapsed", disabled=st.session_state.game_start_time is not None)
                if new_name != current_name:
                    st.session_state.game["players"][player_ids[i]]["name"] = new_name
                    name_changed = True
        if name_changed:
            for direction in ["east", "south", "west", "north"]:
                pid = st.session_state.game["seating"][direction]
                if pid and pid not in st.session_state.game["players"]:
                    st.session_state.game["seating"][direction] = None
            st.rerun()
        st.divider()
        player_ids = list(st.session_state.game["players"].keys())[:4]
        filled_players = [pid for pid in player_ids if st.session_state.game["players"][pid]["name"].strip()]
        if len(filled_players) < 4:
            st.warning(f"Please enter all 4 player names ({len(filled_players)}/4 filled)")
            return
        st.markdown("#### 2. Assign Seats")
        st.caption("Tap a player name, then tap a seat slot to assign or swap")
        col_left, col_right = st.columns([1, 1])
        with col_right:
            st.markdown("**Players**")
            unassigned_players = []
            for pid in player_ids:
                is_seated = any(st.session_state.game["seating"][direction] == pid for direction in ["east", "south", "west", "north"])
                if not is_seated:
                    unassigned_players.append(pid)
            if unassigned_players:
                st.session_state.players = []
                for pid in unassigned_players:
                    player_name = st.session_state.game["players"][pid]["name"]
                    is_selected = (st.session_state.ui["selected_player"] == pid)
                    if st.button(player_name, key=f"card_{pid}", use_container_width=True, type="primary" if is_selected else "secondary", disabled=st.session_state.game_start_time is not None):
                        if st.session_state.ui["selected_player"] == pid:
                            st.session_state.ui["selected_player"] = None
                        else:
                            st.session_state.ui["selected_player"] = pid
                        st.rerun()
            else:
                st.info("All players assigned to a seat!")
                st.session_state.players = []
                for seat in ["east", "south", "west", "north"]:
                    pid = st.session_state.game["seating"][seat]
                    st.session_state.game["players"][pid]["seat"] = seat
                    st.session_state.players.append(st.session_state.game["players"][pid]["name"])
        with col_left:
            st.markdown("**Seats**")
            seat_order = [("east", "East (東)"), ("south", "South (南)"), ("west", "West (西)"), ("north", "North (北)")]
            for direction, display_name in seat_order:
                current_pid = st.session_state.game["seating"][direction]
                seat_cols = st.columns([1, 1])
                with seat_cols[0]:
                    st.markdown(f"**{display_name}**")
                with seat_cols[1]:
                    if current_pid:
                        current_player_name = st.session_state.game["players"][current_pid]["name"]
                        is_selected = (st.session_state.ui["selected_player"] == current_pid)
                        if st.button(current_player_name, key=f"slot_{direction}", use_container_width=True, type="primary" if is_selected else "secondary", disabled=st.session_state.game_start_time is not None):
                            selected = st.session_state.ui["selected_player"]
                            if selected is None:
                                st.session_state.ui["selected_player"] = current_pid
                                st.rerun()
                            elif selected == current_pid:
                                st.session_state.ui["selected_player"] = None
                                st.rerun()
                            else:
                                selected_seat = None
                                for d in ["east", "south", "west", "north"]:
                                    if st.session_state.game["seating"][d] == selected:
                                        selected_seat = d
                                        break
                                if selected_seat:
                                    st.session_state.game["seating"][selected_seat] = current_pid
                                    st.session_state.game["seating"][direction] = selected
                                else:
                                    st.session_state.game["seating"][direction] = selected
                                st.session_state.ui["selected_player"] = None
                                st.rerun()
                    else:
                        if st.button("(Empty)", key=f"slot_{direction}", use_container_width=True, type="secondary"):
                            selected = st.session_state.ui["selected_player"]
                            if selected:
                                current_seat = None
                                for d in ["east", "south", "west", "north"]:
                                    if st.session_state.game["seating"][d] == selected:
                                        current_seat = d
                                        break
                                if current_seat:
                                    st.session_state.game["seating"][current_seat] = None
                                st.session_state.game["seating"][direction] = selected
                                st.session_state.ui["selected_player"] = None
                                st.rerun()
        if st.button("Reset All Seats", use_container_width=True, disabled=st.session_state.game_start_time is not None):
            st.session_state.game["seating"] = {"east": None, "south": None, "west": None, "north": None}
            st.session_state.ui["selected_player"] = None
            st.rerun()
        st.divider()

    def configure_game():
        st.markdown("#### 3. Configure Game Settings")
        st.caption("Choose Scoring Metric")
        with st.container(border=False, horizontal=True):
            st.write("Base Points:")
            base_points = st.number_input("Base Points", min_value=1, max_value=None, value=5, step=1, label_visibility="collapsed")
        with st.container(border=False, horizontal=True):
            st.write("Bonus Points:")
            bonus_points = st.number_input("Bonus Points", min_value=1, max_value=None, value=2, step=1, label_visibility="collapsed")
        st.caption("Extra Settings")
        with st.container(border=False, horizontal=True):
            enable_min_bonus = st.checkbox("Minimum Bonus:")
            min_bonus = st.number_input("Minimum Bonus", min_value=1, max_value=None, value=3, step=1, label_visibility="collapsed", disabled=(not enable_min_bonus))
        if st.button("Start Game", type="primary", width="stretch"):
            st.session_state.game_start_time = datetime.now()
            st.session_state.game["settings"]["base_points"] = base_points
            st.session_state.game["settings"]["bonus_points"] = bonus_points
            st.session_state.min_bonus = min_bonus if enable_min_bonus else 0
            st.rerun()

    @st.dialog("Select Winner")
    def select_winner(round_data):
        st.session_state.selected_player = None
        render_mahjong_table(key="mahjong_table_component_select_winner")
        if st.session_state.selected_player:
            round_data["winner"] = st.session_state.players.index(st.session_state.selected_player)
            st.rerun()

    @st.dialog("Select Loser (Choose Winner for 自摸)")
    def select_loser(round_data):
        st.session_state.selected_player = None
        render_mahjong_table(key="mahjong_table_component_select_loser")
        if st.session_state.selected_player:
            round_data["loser"] = st.session_state.players.index(st.session_state.selected_player)
            st.rerun()

    @st.dialog("Select 東/1 Seat")
    def select_east_seat(round_data):
        st.session_state.selected_player = None
        render_mahjong_table(key="mahjong_table_component_select_east")
        if st.session_state.selected_player:
            round_data["east_seat"] = st.session_state.players.index(st.session_state.selected_player)
            round_data["bonuses"]["flowers"] = [False, False]
            round_data["bonuses"]["winds"] = [False, False]
            st.rerun()

    @st.dialog("Reset Game?")
    def confirm_reset_game():
        st.caption("This will erase all players, seating, and rounds. This can not be undone.")
        with st.container(border=False, horizontal=True):
            if st.button("Cancel", type="secondary"):
                st.rerun()
            if st.button("Confirm", type="primary"):
                reset_game()

    @st.dialog("Share Game")
    def share_game():
        full_url = st.context.url
        if st.query_params:
            full_url += "/?s=" + st.query_params["s"]
        st.caption("Copy URL to share game stats.")
        st.code(full_url, language="text", wrap_lines=True, height=450)
        if st.button("Done", icon=":material/check:", type="primary", width="stretch"):
            st.rerun()

    @st.dialog(f"Delete Round?")
    def delete_round(round_data):
        st.caption("This can not be undone")
        with st.container(border=False, horizontal=True):
            if st.button("Cancel", type="secondary"):
                st.rerun()
            if st.button("Confirm", type="primary"):
                st.session_state.game["rounds"].remove(round_data)
                st.rerun()

    @st.dialog("Draw?")
    def enter_draw(round_data):
        st.caption("No winner for this round")
        with st.container(border=False, horizontal=True):
            if st.button("Cancel", type="secondary"):
                st.rerun()
            if st.button("Confirm", type="primary"):
                round_data["draw"] = True
                round_data["winner"] = None
                round_data["loser"] = None
                round_data["east_seat"] = None
                st.rerun()

    @st.dialog("Enter Bonuses")
    def more_bonuses(round_data):
        st.markdown("<style>.stCheckbox label span { overflow: visible !important; white-space: nowrap !important; text-overflow: clip !important; max-width: none !important; width: auto !important; display: inline-block !important; } .stCheckbox label .stBadge { overflow: visible !important; white-space: nowrap !important; text-overflow: clip !important; max-width: none !important; display: inline-block !important; } .stCheckbox label span[data-testid='stMarkdownContainer'] { overflow: visible !important; white-space: nowrap !important; display: inline-block !important; }</style>", unsafe_allow_html=True)
        bonuses = (round_data["bonuses"]["more"]).copy()
        with st.container(border=False, horizontal=True):
            cancel_button = st.button("Cancel", type="secondary")
            confirm_button = st.button("Confirm", type="primary")
        with st.container(border=False, horizontal=False):
            for i in range(20):
                value = MORE_BONUSES_VALUE[i]
                value += 1 if i in (0,1) else 0
                bonuses[i] =  st.checkbox(f":{MORE_BONUSES_COLOR[i]}-badge[:material/{MORE_BONSUES_ICON[i]}: {MORE_BONUSES_CHINESE[i]}/{MORE_BONUSES_PINYIN[i]} ({value})] ", key=f"more_bonus_1_{i}", value=bonuses[i])
        if confirm_button:
            round_data["bonuses"]["more"] = bonuses
            if bonuses[12] or bonuses[13]:
                round_data["bonuses"]["dragons"] = [False, False, False]
            if bonuses[14] or bonuses[15]:
                round_data["bonuses"]["winds"] = [False, False]
            st.rerun()
        if cancel_button:
            st.rerun()

    @st.dialog("Finish Game?")
    def finish_game(round_data):
        with st.container(border=False, horizontal=True):
            if st.button("Finish", type="primary"):
                st.session_state.game_finish = True
                round_data["timestamp"] = datetime.now()
                start_time = st.session_state.game["rounds"][-2]["timestamp"]
                round_data["duration"] = (round_data["timestamp"] - start_time).total_seconds()
                st.rerun()
            if st.button("Cancel", type="secondary"):
                st.rerun()

    def display_scorecards(target=-1):
        common_bonuses_labels = COMMON_BONUSES_PINYIN if st.session_state.use_pinyin else COMMON_BONUSES_CHINESE
        if "editing_round" not in st.session_state:
            st.session_state.editing_round = None
        for round_index, round_data in enumerate(reversed(st.session_state.game["rounds"])):
            if target != -1 and len(st.session_state.game["rounds"]) - 1 - round_index != target:
                continue
            should_gray_out = (round_index != 0 or st.session_state.game_finish or target != -1) and round_index != st.session_state.editing_round
            with st.container(border=True):
                name = f"{CHARACTERS[round_data['current_cycle']]}{num_to_chinese(round_data['round'])}"
                if round_data["streak"] > 0:
                    name += f" (連{num_to_chinese(round_data['streak'])})"
                cols = st.columns(2)
                with cols[0]:
                    with st.container(border=False, horizontal=True):
                        st.write(f"### {name}")
                with cols[1]:
                    with st.container(border=False, horizontal=True):
                        if should_gray_out:
                            if st.button("Edit Round" if not round_data["draw"] else "(Draw)", icon=(":material/edit_off:" if round_data["draw"] else ":material/edit:"), type="secondary", key=f"edit_button_{round_index}", disabled=round_data["draw"]):
                                st.session_state.editing_round = round_index
                                st.rerun()
                        elif round_index != 0 or st.session_state.game_finish or target != -1:
                            if st.button("Confirm", icon=":material/check:", type="primary", key=f"done_editing_{round_index}"):
                                st.session_state.editing_round = None
                                st.rerun()
                        else:
                            st.space("stretch")
                            if st.button("", icon=":material/swords:", type=("primary" if round_data["draw"] else "secondary"), key=f"draw_{round_index}", disabled=should_gray_out):
                                if round_data["draw"]:
                                    round_data["draw"] = False
                                    st.rerun()
                                else:
                                    Modules.enter_draw(round_data)
                            if st.button("", icon=":material/delete:", type="primary", key=f"delete_{round_index}"):
                                Modules.delete_round(round_data)
                cols = st.columns(3)
                with cols[0]:
                    if st.button("Select Winner" if round_data["winner"] is None else f"{st.session_state.players[round_data['winner']]}", icon=":material/crown:", key=f"select_winner_{round_index}", width="stretch", disabled=(round_data["draw"] or round_index != 0 or st.session_state.game_finish)):
                        Modules.select_winner(round_data)
                with cols[1]:
                    if st.button("Select Loser" if round_data["loser"] is None else ("自摸" if not st.session_state.use_pinyin else "zì mō") if round_data["winner"] == round_data["loser"] else f"{st.session_state.players[round_data['loser']]}", icon=":material/close:", key=f"select_loser_{round_index}", width="stretch", disabled=(should_gray_out or round_data["draw"])):
                        Modules.select_loser(round_data)
                with cols[2]:
                    if st.button("Dice Roll" if round_data["east_seat"] is None else f"{st.session_state.players[round_data['east_seat']]}", icon=":material/casino:", key=f"east_seat_{round_index}", width="stretch", disabled=(should_gray_out or round_data["draw"])):
                        Modules.select_east_seat(round_data)
                with st.container(border=False, horizontal=True):
                    bonus_data = round_data["bonuses"]
                    bonus_seat = -1
                    if round_data["winner"] is not None and round_data["east_seat"] is not None and round_data["loser"] is not None:
                        bonus_seat = (round_data["winner"] - round_data["east_seat"]) % 4
                    if bonus_seat == round_data["current_cycle"]:
                        bonus_data["winds"][1] = bonus_data["winds"][0]
                    if st.button(f"{bonus_seat+1}", icon=":material/deceased:", key=f"flower_1_{round_index}", type=("primary" if bonus_data["flowers"][0] else "secondary"), disabled=(should_gray_out and not bonus_data["flowers"][0] or round_data["draw"] or bonus_seat==-1)):
                        if not should_gray_out:
                            bonus_data["flowers"][0] = not bonus_data["flowers"][0]
                            st.rerun()
                    if st.button(f"{bonus_seat+1}", icon=":material/local_florist:", key=f"flower_2_{round_index}", type=("primary" if bonus_data["flowers"][1] else "secondary"), disabled=(should_gray_out and not bonus_data["flowers"][1] or round_data["draw"] or bonus_seat==-1)):
                        if not should_gray_out:
                            bonus_data["flowers"][1] = not bonus_data["flowers"][1]
                            st.rerun()
                    if st.button(CHARACTERS[bonus_seat], key=f"wind_1_{round_index}", type=("primary" if bonus_data["winds"][0] else "secondary"), disabled=(should_gray_out and not bonus_data["winds"][0] or round_data["draw"] or bonus_seat==-1 or bonus_data["more"][14] or bonus_data["more"][15])):
                        if not should_gray_out:
                            bonus_data["winds"][0] = not bonus_data["winds"][0]
                            if bonus_seat == round_data["current_cycle"]:
                                bonus_data["winds"][1] = bonus_data["winds"][0]
                            st.rerun()
                    if st.button(CHARACTERS[round_data['current_cycle']], key=f"wind_2_{round_index}", type=("primary" if bonus_data["winds"][1] else "secondary"), disabled=(should_gray_out and not bonus_data["winds"][1] or round_data["draw"] or bonus_seat==-1 or bonus_seat==round_data["current_cycle"] or bonus_data["more"][14] or bonus_data["more"][15])):
                        if not should_gray_out:
                            bonus_data["winds"][1] = not bonus_data["winds"][1]
                            st.rerun()
                    if st.button("中", key=f"zhong_{round_index}", type=("primary" if bonus_data["dragons"][0] else "secondary"), disabled=(should_gray_out and not bonus_data["dragons"][0] or round_data["draw"] or bonus_seat==-1 or bonus_data["more"][12] or bonus_data["more"][13])):
                        if not should_gray_out:
                            bonus_data["dragons"][0] = not bonus_data["dragons"][0]
                            if all(bonus_data["dragons"]):
                                bonus_data["dragons"] = [False, False, False]
                                bonus_data["more"][13] = True
                            st.rerun()
                    if st.button("發", key=f"fa_{round_index}", type=("primary" if bonus_data["dragons"][1] else "secondary"), disabled=(should_gray_out and not bonus_data["dragons"][1] or round_data["draw"] or bonus_seat==-1 or bonus_data["more"][12] or bonus_data["more"][13])):
                        if not should_gray_out:
                            bonus_data["dragons"][1] = not bonus_data["dragons"][1]
                            if all(bonus_data["dragons"]):
                                bonus_data["dragons"] = [False, False, False]
                                bonus_data["more"][13] = True
                            st.rerun()
                    if st.button(":material/fullscreen_portrait:", key=f"bai_{round_index}", type=("primary" if bonus_data["dragons"][2] else "secondary"), disabled=(should_gray_out and not bonus_data["dragons"][2] or round_data["draw"] or bonus_seat==-1 or bonus_data["more"][12] or bonus_data["more"][13])):
                        if not should_gray_out:
                            bonus_data["dragons"][2] = not bonus_data["dragons"][2]
                            if all(bonus_data["dragons"]):
                                bonus_data["dragons"] = [False, False, False]
                                bonus_data["more"][13] = True
                            st.rerun()
                with st.container(border=False, horizontal=True):
                    if st.button(f":material/fullscreen_portrait::material/web_stories::material/fullscreen_portrait:\n{common_bonuses_labels[0]}", key=f"center_hole_{round_index}", type=("primary" if bonus_data["common"][0] else "secondary"), disabled=(should_gray_out and not bonus_data["common"][0] or round_data["draw"] or bonus_seat==-1 or any(bonus_data["common"][0:3]) and not bonus_data["common"][0])):
                        if not should_gray_out:
                            bonus_data["common"][0] = not bonus_data["common"][0]
                            st.rerun()
                    if st.button(f":material/fullscreen_portrait::material/fullscreen_portrait::material/web_stories:\n{common_bonuses_labels[1]}", key=f"edge_hole_{round_index}", type=("primary" if bonus_data["common"][1] else "secondary"), disabled=(should_gray_out and not bonus_data["common"][1] or round_data["draw"] or bonus_seat==-1 or any(bonus_data["common"][0:3]) and not bonus_data["common"][1])):
                        if not should_gray_out:
                            bonus_data["common"][1] = not bonus_data["common"][1]
                            st.rerun()
                    if st.button(f":material/fullscreen_portrait::material/web_stories:\n{common_bonuses_labels[2]}", key=f"pair_wait_{round_index}", type=("primary" if bonus_data["common"][2] else "secondary"), disabled=(should_gray_out and not bonus_data["common"][2] or round_data["draw"] or bonus_seat==-1 or any(bonus_data["common"][0:3]) and not bonus_data["common"][2])):
                        if not should_gray_out:
                            bonus_data["common"][2] = not bonus_data["common"][2]
                            st.rerun()
                    if st.button(f":material/cleaning_services::material/clear_all:\n{common_bonuses_labels[3]}", key=f"clean_gate_{round_index}", type=("primary" if bonus_data["common"][3] else "secondary"), disabled=(should_gray_out and not bonus_data["common"][3] or round_data["draw"] or bonus_seat==-1)):
                        if not should_gray_out:
                            bonus_data["common"][3] = not bonus_data["common"][3]
                            st.rerun()
                points, bonuses = calculate_score(round_data)
                bonus_count = 0-max([bonuses[i] for i in range(4) if i != round_data["winner"] and i != round_data["round"]-1]) if round_data["winner"] == round_data["loser"] else max(bonuses)
                cols = st.columns(2)
                with cols[0]:
                    if st.button("More Bonuses", icon=":material/star:", key=f"more_bonuses_{round_index}", disabled=(should_gray_out or round_data["draw"] or bonus_seat==-1)):
                        Modules.more_bonuses(round_data)
                    st.markdown(get_badges(round_data, bonus_seat))
                with cols[1]:
                    if not round_data["draw"] and bonus_seat > -1:
                        st.metric(st.session_state.players[round_data['winner']], f"+ {max(points)}", f"{bonus_count} 台" if not st.session_state.use_pinyin else f"{bonus_count} tái", icon=":material/crown:", border=True)
                if round_data["duration"]:
                    minutes = int(round_data["duration"] // 60)
                    seconds = int(round_data["duration"] % 60)
                    st.caption(f":material/timer: {minutes}m {seconds}s")
                if round_index == 0 and not st.session_state.game_finish:
                    if st.session_state.dice_roll != [DIRECTIONS[round_data["round"]-1], round_data["streak"]]:
                        st.session_state.dice_roll = [DIRECTIONS[round_data["round"]-1], round_data["streak"]]
                        st.rerun()
                    text = "Finish Game" if not round_data["draw"] and round_data["winner"] != 3 and round_data["round"] == 4 and round_data["current_cycle"] == 3 else "Next Round"
                    if st.button(text, icon=":material/check:", type="primary", disabled=((bonus_seat==-1 or bonus_count<st.session_state.min_bonus) and not round_data["draw"]), width="stretch"):
                        if text == "Next Round":
                            if round_data["draw"]:
                                round = round_data["round"]
                                current_cycle = round_data["current_cycle"]
                                streak = round_data["streak"] + 1
                            elif round_data["winner"] == DIRECTIONS.index(st.session_state.dice_roll[0]):
                                round = round_data["round"]
                                current_cycle = round_data["current_cycle"]
                                streak = round_data["streak"] + 1
                            else:
                                round = round_data["round"] % 4 + 1
                                current_cycle = round_data["current_cycle"] if round != 1 else round_data["current_cycle"] + 1
                                streak = 0
                            st.session_state.dice_roll = [DIRECTIONS[round-1], streak]
                            round_data["timestamp"] = datetime.now()
                            start_time = st.session_state.game_start_time if st.session_state.game["rounds"].index(round_data) == 0 else st.session_state.game["rounds"][st.session_state.game["rounds"].index(round_data)-1]["timestamp"]
                            round_data["duration"] = (round_data["timestamp"] - start_time).total_seconds()
                            st.session_state.game["rounds"].append({
                                "current_cycle": current_cycle,
                                "round": round,
                                "streak": streak,
                                "winner": None,
                                "loser": None,
                                "east_seat": None,
                                "draw": False,
                                "bonuses": {
                                    "flowers": [False, False],
                                    "winds": [False, False],
                                    "dragons": [False, False, False],
                                    "common": [False, False, False, False],
                                    "more": [False for _ in range(20)]
                                },
                                "timestamp": None,
                                "duration": None
                            })
                            st.rerun()
                        else:
                            Modules.finish_game(round_data)
                    if not round_data["draw"] and bonus_seat > -1:
                        if bonus_count < st.session_state.min_bonus:
                            st.badge(f"Minimum bonus not fulfilled: ({bonus_count}/{st.session_state.min_bonus})", icon=":material/close:", color="red")

    def display_total_scores():
        with st.container(border=False, horizontal=True):
            for player in st.session_state.players:
                delta = "±" if st.session_state.scores_df[player].iloc[-1] == 0 else "+" if st.session_state.scores_df[player].iloc[-1] > 0 else ""
                delta_color = "gray" if delta == "±" else "normal"
                delta_arrow = "off" if delta == "±" else "auto"
                st.metric(player, st.session_state.cumulative_scores_df[player].iloc[-1], delta=f"{delta}{st.session_state.scores_df[player].iloc[-1]}", delta_color=delta_color, delta_arrow=delta_arrow, border=True)

    def display_scoresheet():
        with st.container(border=False, horizontal=True):
            deltas = ["1st", "2nd", "3rd", "4th"]
            delta_colors = ["green", "yellow", "orange", "red"]
            for rank, player in zip(st.session_state.player_rankings, st.session_state.players):
                st.metric(player, st.session_state.cumulative_scores_df[player].iloc[-1], delta=deltas[rank], delta_color=delta_colors[rank], delta_arrow="off", border=True)
        plt.style.use("dark_background")
        scores_df = st.session_state.cumulative_scores_df
        graph_colors = ["limegreen", "yellow", "darkorange", "red"]
        fig, ax = plt.subplots()
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.axhline(y=0, color='white', linestyle='-', linewidth=1, alpha=1)
        for rank, player in zip(st.session_state.player_rankings, st.session_state.players):
            ax.plot(scores_df.index, scores_df[player], marker="", color=graph_colors[rank], linewidth=2, label=player)
            final_score = scores_df[player].iloc[-1]
            ax.plot(scores_df.index[-1], final_score, marker="o", markersize=8, color=graph_colors[rank])
        ax.grid(True, alpha=0.3)
        ax.set_xticks(range(1, len(scores_df)))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        st.markdown("#### Total Scores")
        st.pyplot(fig)
        plt.close(fig)
        total_scores_row = {"Round": ["TOTAL"]}
        for player in st.session_state.players:
            total_scores_row[player] = [st.session_state.cumulative_scores_df[player].iloc[-1]]
        def highlight_max(row):
            colors = ["#65F065", "#FFFF52", "#FFA63A", "#FF3C3C"]
            if row.name == len(st.session_state.scores_df):
                return ['background-color: rgba(128, 128, 128, 0.1)' for _ in row]
            player_cols = st.session_state.players
            player_values = row[player_cols]
            round_str = row['Round']
            second_char = round_str[1] if len(round_str) > 1 else ''
            highlight_idx = {"一": 1, "二": 2, "三": 3, "四": 4}.get(second_char, -1)
            if (player_values == 0).all():
                styles = []
                for idx, col in enumerate(row.index):
                    if col == 'Round':
                        styles.append('background-color: rgba(128, 128, 128, 0.05)')
                    elif idx == highlight_idx:
                        styles.append(f'font-weight: bold; color: {colors[st.session_state.player_rankings[st.session_state.players.index(col)]]}')
                    else:
                        styles.append('')
                return styles
            is_max = player_values == player_values.max()
            styles = []
            for idx, col in enumerate(row.index):
                if col == 'Round':
                    styles.append('background-color: rgba(128, 128, 128, 0.05)')
                elif col in player_cols and is_max[col]:
                    if idx == highlight_idx:
                        styles.append(f'background-color: rgba(13, 110, 253, 0.15); font-weight: bold; color: {colors[st.session_state.player_rankings[st.session_state.players.index(col)]]}')
                    else:
                        styles.append('background-color: rgba(13, 110, 253, 0.15)')
                elif idx == highlight_idx:
                    styles.append(f'font-weight: bold; color: {colors[st.session_state.player_rankings[st.session_state.players.index(col)]]}')
                else:
                    styles.append('')
            return styles
        styled_df = pd.concat([st.session_state.scores_df, pd.DataFrame(total_scores_row)], ignore_index=True).style.apply(highlight_max, axis=1)
        st.dataframe(styled_df, width="stretch", hide_index=True, height="content", selection_mode=None)
        Modules.display_miscellaneous_stats()

    def display_miscellaneous_stats():
        tai_char = "Tái" if st.session_state.use_pinyin else "台"
        zi_mo_char = "Zì Mō" if st.session_state.use_pinyin else "自摸"
        st.markdown("#### Miscellaneous Stats")
        win_amount, bonus_amount = ([[] for _ in range(4)], [[] for _ in range(4)])
        winners = []
        dice_roll_streak = [[] for _ in range(4)]
        zi_mo_count = [0 for _ in range(4)]
        durations = []
        for round_data in st.session_state.game["rounds"]:
            if round_data["draw"] or round_data["winner"] is not None and round_data["loser"] is not None and round_data["east_seat"] is not None:
                points, bonuses = calculate_score(round_data)
                if round_data["draw"]:
                    winners.append(None)
                else:
                    winners.append(points.index(max(points)))
                    bonus_amount[points.index(max(points))].append(max(bonuses))
                    win_amount[points.index(max(points))].append(max(points))
                    if round_data["winner"] == round_data["loser"]:
                        zi_mo_count[round_data["winner"]] += 1
                dice_roll_streak[round_data["round"]-1].append(round_data["streak"])
                if round_data["duration"] is not None:
                    durations.append(round_data["duration"])
        win_count = [winners.count(i) for i in range(4)]
        max_winstreak = [0, 0, 0, 0]
        current = [0, 0, 0, 0]
        for w in winners:
            current = [current[i] + 1 if i == w else 0 for i in range(4)]
            max_winstreak = [max(max_winstreak[i], current[i]) for i in range(4)]
        max_dice_roll_streak = [0, 0, 0, 0]
        for idx, roll in enumerate(dice_roll_streak):
            if roll != []:
                max_dice_roll_streak[idx] = max(roll)
        st.markdown("###### :material/crown: Win Count")
        with st.container(border=False, horizontal=True):
            for idx, player in enumerate(st.session_state.players):
                st.metric(player, win_count[idx], "Wins", border=True, delta_color="blue", delta_arrow="off")
        st.markdown("###### :material/keyboard_double_arrow_up: Average Points Per Win")
        with st.container(border=False, horizontal=True):
            for idx, player in enumerate(st.session_state.players):
                st.metric(player, round(sum(win_amount[idx])/max(len(win_amount[idx]),1), 1), f"{round(sum(bonus_amount[idx])/max(len(bonus_amount[idx]),1), 2)} {tai_char}", border=True, delta_color="violet", delta_arrow="off")
        st.markdown("###### :material/moving: Biggest Win")
        with st.container(border=False, horizontal=True):
            for idx, player in enumerate(st.session_state.players):
                if win_amount[idx]:
                    st.metric(player, f"+{max(win_amount[idx])}", f"{bonus_amount[idx][win_amount[idx].index(max(win_amount[idx]))]} {tai_char}", border=True, delta_color="orange", delta_arrow="off")
                else:
                    st.metric(player, "+0", f"0 {tai_char}", border=True, delta_color="orange", delta_arrow="off")
        st.markdown(f"###### :material/mobile_theft: {zi_mo_char} Count")
        with st.container(border=False, horizontal=True):
            for idx, player in enumerate(st.session_state.players):
                st.metric(player, zi_mo_count[idx], zi_mo_char, border=True, delta_color="yellow", delta_arrow="off")
        if durations:
            st.markdown("###### :material/alarm_on: Round Duration")
            with st.container(border=False, horizontal=True):
                st.metric("Total Duration", f"{int((sum(durations))//3600)}h {int((sum(durations)%3600)//60)}m {int((sum(durations)%3600)%60)}s", border=True, width="stretch", icon=":material/timer_play:")
                st.metric("Average Duration", f"{int((sum(durations)/len(durations))//60)}m {int((sum(durations)/len(durations))%60)}s", border=True, width="stretch", icon=":material/avg_time:")
            with st.container(border=False, horizontal=True):
                st.metric("Fastest Round", f"{int(min(durations)//60)}m {int(min(durations)%60)}s", st.session_state.scores_df["Round"].iloc[durations.index(min(durations))], delta_arrow="off", delta_color="green", border=True, icon=":material/acute:")
                st.metric("Longest Round", f"{int(max(durations)//60)}m {int(max(durations)%60)}s", st.session_state.scores_df["Round"].iloc[durations.index(max(durations))], delta_arrow="off", delta_color="red", border=True, icon=":material/avg_pace:")
        else:
            st.markdown("###### :material/alarm_on: Round Duration")
            with st.container(border=False, horizontal=True):
                st.metric("Fastest Round", "0m 00s", "---", delta_arrow="off", delta_color="green", border=True, icon=":material/acute:")
                st.metric("Longest Round", "0m 00s", "---", delta_arrow="off", delta_color="red", border=True, icon=":material/avg_pace:")
            st.metric("Average Duration", "0m 00s", border=True, width="stretch", icon=":material/avg_time:")
        st.markdown("###### :material/motion_blur: Longest Streaks")
        with st.container(border=False, horizontal=True):
            if max_winstreak != [0,0,0,0]:
                st.metric("Win Streak", max(max_winstreak), st.session_state.players[max_winstreak.index(max(max_winstreak))], delta_arrow="off", delta_color="blue", border=True, icon=":material/fire_check:")
            else:
                st.metric("Win Streak", 0, "---", delta_arrow="off", delta_color="blue", border=True, icon=":material/fire_check:")
            if max_dice_roll_streak != [0,0,0,0]:
                st.metric("Dice Roll Streak", max(max_dice_roll_streak), st.session_state.players[max_dice_roll_streak.index(max(max_dice_roll_streak))], delta_arrow="off", delta_color="violet", border=True, icon=":material/casino:")
            else:
                st.metric("Dice Roll Streak", 0, "---", delta_arrow="off", delta_color="violet", border=True, icon=":material/casino:")


def main():
    st.markdown("<style>div[data-testid='stHorizontalBlock'] { flex-wrap: nowrap !important; } div[data-testid='stHorizontalBlock'] > div { min-width: 0 !important; flex: 1 1 0 !important; }</style>", unsafe_allow_html=True) # Force horizontal columns on Mobile
    st.markdown("<style>.stButton button { white-space: pre-line !important; height: auto !important; padding: 10px !important; }</style>", unsafe_allow_html=True) # Allow \n char
    st.markdown("<style>.stButton button { white-space: pre !important; }</style>", unsafe_allow_html=True) # Allow consecutive whitespace
    st.markdown("<style>[data-testid='stMetricValue'] { font-size: 18px !important; font-weight: 600 !important; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; } [data-testid='stMetricLabel'] { font-size: 13px !important; } [data-testid='stMetricDelta'] { font-size: 13px !important; } [data-testid='stMetricValue'] > div { font-size: 30px !important; font-weight: 500 !important; white-space: normal !important; overflow: visible !important; }</style>", unsafe_allow_html=True) # Change font size of st.metric
    initialize_game_state()
    Modules.startup()
    Modules.display_player_setup_tap()
    if st.session_state.players:
        Modules.display_mahjong_table("mahjong_table_component_config")
        st.divider()
        if st.session_state.game_start_time is None:
            Modules.configure_game()
        else:
            generate_scoresheets()
            enter_scores, scoresheet = st.tabs(["Enter Scores", "Scoresheet"], key="tabs")
            with enter_scores:
                Modules.display_total_scores()
                Modules.display_scorecards()
            with scoresheet:
                Modules.display_scoresheet()
    save_state_to_query_params()
    st.divider()
    if st.button("Share Game", icon=":material/share:", type="primary", width="stretch"):
        Modules.share_game()
    if st.button("Reset Game", icon=":material/restart_alt:", type="secondary", width="stretch"):
        Modules.confirm_reset_game()
    toggle_state = st.toggle("Use Pīnyīn", value=st.session_state.get("use_pinyin", False))
    if toggle_state != st.session_state.use_pinyin:
        st.session_state.use_pinyin = toggle_state
        st.rerun()


if __name__ == "__main__":
    main()