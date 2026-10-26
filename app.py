"""Streamlit app for the channel-by-channel EEG plots.

Run from this folder:  python -m streamlit run app.py --server.port 8503
"""
import streamlit as st

import views

st.set_page_config(page_title="EEG channels", page_icon=":material/waves:", layout="wide",
                   menu_items={"About": "Channel-by-channel view of EEG recorded while people listen to music."})
st.title("EEG, channel by channel")
st.sidebar.caption("What every sensor on the head recorded while 18 people listened to music, and where the activity changes.\n\n"
                   "Data: Kaggle, Music Tempo Emotional Impact EEG Dataset.")
st.navigation([
    st.Page(views.explore_page, title="Explore a recording", icon=":material/search:", url_path="explore", default=True),
    st.Page(views.group_page, title="Baseline vs music", icon=":material/compare_arrows:", url_path="group"),
    st.Page(views.quality_page, title="Channel quality", icon=":material/signal_cellular_alt:", url_path="quality"),
    st.Page(views.observations_page, title="Observations", icon=":material/article:", url_path="observations"),
    st.Page(views.about_page, title="About", icon=":material/info:", url_path="about"),
]).run()
