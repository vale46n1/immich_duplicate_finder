import streamlit as st
import sqlite3
from db import load_settings_from_db, save_settings_to_db,load_settings_from_db

def startup_sidebar():
    logo_path = "https://immich.app/img/immich-logo-stacked-dark.svg"
    st.sidebar.image(logo_path, width=150)
    st.sidebar.markdown("---")

    immich_server_url, api_key, images_folder, timeout = load_settings_from_db()

    with st.sidebar.expander("Login Settings", expanded=False):
        try:
            immich_server_url = st.text_input('IMMICH Server URL', immich_server_url).rstrip('/')
        except:
            immich_server_url=''

        api_key = st.text_input('API Key', api_key)
        timeout = st.number_input('Request timeout (ms)', timeout)

        # Check if the timeout is less than 200 ms and show a warning
        if timeout < 200:
            st.sidebar.warning('Warning: Timeout is set too low. It may cause request failures.')

        if st.button('Save Settings'):
            save_settings_to_db(immich_server_url, api_key, images_folder, timeout)
            st.sidebar.success('Settings saved!')

    return immich_server_url, api_key, timeout

