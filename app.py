import streamlit as st
import os

from api import fetchAssets
from db import startup_db_configurations, startup_processed_assets_db, startup_processed_duplicate_faiss_db
from startup import startup_sidebar
from imageDuplicate import generate_db_duplicate,show_duplicate_photos_faiss,calculateFaissIndex


# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
###############STARTUP#####################

# Set page title and favicon
st.set_page_config(page_title="Immich duplicator finder ", page_icon="https://immich.app/img/immich-logo-stacked-dark.svg")

startup_db_configurations()
startup_processed_assets_db()
startup_processed_duplicate_faiss_db()
immich_server_url, api_key, timeout = startup_sidebar()

def setup_session_state():
    """Initialize session state with default values."""
    session_defaults = {
        'enable_size_filter': True,
        'size_ratio': 5,
        'deleted_photo': False,
        'filter_nr': 10,
        'show_duplicates': False,
        'calculate_faiss': False,
        'generate_db_duplicate': False,
        'show_faiss_duplicate': False,
        'avoid_thumbnail_jpeg': True,
        'is_trashed': False,
        'is_favorite': True,
        'stop_process' : False,
        'stop_index' : False,
        'photo_choice': 'Thumbnail (fast)'  # Initialize with default action to not show duplicates
    }
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def configure_sidebar():
    """Configure the sidebar for user inputs."""
    with st.sidebar:
        st.markdown("---")
        with st.expander("Image Duplicate Finder", expanded=True):
            # Button to generate/update the FAISS index
            if st.button('Create/Update FAISS index'):
                st.session_state['calculate_faiss'] = True

            # Button to trigger the generation of the duplicates database
            if st.button('Create/Update duplicate DB'):
                st.session_state['generate_db_duplicate'] = True

            st.markdown("---")
            # Input for setting the minimum FAISS threshold
            st.session_state['faiss_min_threshold'] = st.number_input(
                "Minimum Faiss threshold", min_value=0.0, max_value=10.0,
                value=st.session_state.get('faiss_min_threshold', 0.0), step=0.01,
                help="Set the lower limit of the FAISS similarity threshold for considering duplicates."
            )

            # Input for setting the maximum FAISS threshold
            st.session_state['faiss_max_threshold'] = st.number_input(
                "Maximum Faiss threshold", min_value=0.0, max_value=10.0,
                value=st.session_state.get('faiss_max_threshold', 0.6), step=0.01,
                help="Set the upper limit of the FAISS similarity threshold for considering duplicates."
            )

            # Input for setting the maximum FAISS threshold
            st.session_state['limit'] = st.number_input(
                "Number of Pairs to Display",
                value=st.session_state.get('limit', 10), step=1,
                help="Set the number of pairs to display for the comparison"
            )

            if st.button('Find duplicate photos'):
                st.session_state['show_faiss_duplicate'] = True

        with st.expander("Video Duplicate Finder", expanded=True):
            # Button to generate/update the FAISS index
            if st.button('Find duplicate video'):
                st.info("Coming function")

        st.markdown("---")
        # Display program version and additional data
        program_version = "v0.1.3"
        additional_data = "Immich duplicator finder"
        st.markdown(f"**Version:** {program_version}\n\n{additional_data}")

def main():
    setup_session_state()
    configure_sidebar()
    assets = None

    # Attempt to fetch assets if any asset-related operation is to be performed
    if st.session_state['calculate_faiss'] or st.session_state['generate_db_duplicate'] or st.session_state['show_faiss_duplicate']:
        assets = fetchAssets(immich_server_url, api_key,timeout)
        if not assets:
            st.error("No assets found or failed to fetch assets.")
            return  # Stop further execution since there are no assets to process


    # Calculate the FAISS index if the corresponding flag is set
    if st.session_state['calculate_faiss'] and assets:
        calculateFaissIndex(
            assets, 
            immich_server_url, 
            api_key
        )

    # Show FAISS duplicate photos if the corresponding flag is set
    if st.session_state['generate_db_duplicate']:
        generate_db_duplicate()

    # Show FAISS duplicate photos if the corresponding flag is set
    if st.session_state['show_faiss_duplicate'] and assets:
        show_duplicate_photos_faiss(
            assets, st.session_state['limit'], 
            st.session_state['faiss_min_threshold'],
            st.session_state['faiss_max_threshold'],
            immich_server_url,
            api_key
        )

if __name__ == "__main__":
    main()