import numpy as np
from streamlit_image_comparison import image_comparison
import streamlit as st

from utility import display_asset_column, findDuplicatesHash
from immichApi import getAssetInfo, fetchAssets
from db import startup_db_configurations, startup_processed_assets_db, load_duplicate_pairs, is_db_populated, startup_processed_duplicate_faiss_db,save_duplicate_pair
from startup import startup_sidebar
from imageProcessing import streamAsset,calculatepHashPhotos,calculateFaissIndex
from faissCalc import init_or_load_faiss_index
import os

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
###############STARTUP#####################

# Set page title and favicon
st.set_page_config(page_title="Immich duplicator finder ", page_icon="https://immich.app/img/immich-logo-stacked-dark.svg")

startup_db_configurations()
startup_processed_assets_db()
startup_processed_duplicate_faiss_db()
immich_server_url, api_key, timeout = startup_sidebar()

def show_duplicate_photos(assets,limit):
     # Assuming this fetches asset information
    duplicates, resolution_counts = findDuplicatesHash(assets,'thumbhash') #thumbhash or dbhash

    if duplicates:
        st.write(f"Total duplicates found {len(duplicates)} on total asset of {len(assets)} -> Currently shown: {limit}")
        progress_bar = st.progress(0)
        filtered_duplicates = []
        for original, duplicate in duplicates:
            original_size_info = getAssetInfo(original['id'],assets)
            duplicate_size_info = getAssetInfo(duplicate['id'],assets)

            # Check if the size is known before attempting to convert to float
            if original_size_info[0] != 'Unknown' and duplicate_size_info[0] != 'Unknown':
                original_size_mb = float(original_size_info[0].split()[0])
                duplicate_size_mb = float(duplicate_size_info[0].split()[0])

                # Apply size difference filter
                if st.session_state.enable_size_filter:
                    if original_size_mb == 0 or duplicate_size_mb == 0:
                        continue  # Example: skipping this pair
                    try:
                        size_diff_ratio = max(original_size_mb, duplicate_size_mb) / min(original_size_mb, duplicate_size_mb)
                    except ZeroDivisionError:
                        continue

                    if size_diff_ratio < st.session_state.size_ratio:
                        continue  # Skip this pair due to insufficient size difference

                filtered_duplicates.append((original, duplicate, original_size_info, duplicate_size_info))
        limited_duplicates = filtered_duplicates[:limit]

        # DUPLICATE FINDER
        for i, (original, duplicate, original_size_info, duplicate_size_info) in enumerate(limited_duplicates, start=1):  # Limit to the first 10 for testing
            # Update the progress bar based on the current iteration relative to the total
            progress_bar.progress(i / len(duplicates))
            st.write(f"Duplicate Pair {i}")
            photo_choice = st.session_state['photo_choice']

            asset_id_1=original['id']
            asset_id_2=duplicate['id']
            #ORIGINAL SIZE
            image1 = streamAsset(asset_id_1, immich_server_url, photo_choice,api_key)
            image2 = streamAsset(asset_id_2, immich_server_url, photo_choice, api_key)
            asset1_info=getAssetInfo(asset_id_1,assets)
            asset2_info=getAssetInfo(asset_id_2,assets)
            
            if image1 is not None and image2 is not None:
                # Convert PIL images to numpy arrays if necessary
                image1 = np.array(image1)
                image2 = np.array(image2)
                # Proceed with image comparison
                image_comparison(
                    img1=image1,
                    img2=image2,
                    label1=f"Name: {asset_id_1}",
                    label2=f"Name: {asset_id_2}",
                    width=700,
                    starting_position=50,
                    show_labels=True,
                    make_responsive=True,
                    in_memory=True,
                    # Your existing parameters here
                )
            else:
                st.write("One or both of the assets are not images and cannot be compared.")

            col1, col2 = st.columns(2)

            with col1:
                display_asset_column(
                    col1, 
                    asset1_info, 
                    asset2_info, 
                    asset_id_1, 
                    immich_server_url, 
                    api_key
                )
                                        
            with col2:
                display_asset_column(
                    col2, 
                    asset2_info, 
                    asset1_info,
                    asset_id_2, 
                    immich_server_url, 
                    api_key
                )

            st.markdown("---")
        progress_bar.progress(100)

    else:
        st.write("No duplicates found.")

def generate_db_duplicate():
    st.write("Database initialization")
    index, metadata = init_or_load_faiss_index()
    if not index or not metadata:
        st.write("FAISS index or metadata not available.")
        return

    # Check and update the stop mechanism in session state
    if 'stop_requested' not in st.session_state:
        st.session_state['stop_requested'] = False

    # Button to request stopping
    if st.button('Stop Finding Duplicates'):
        st.session_state['stop_requested'] = True
        st.session_state['generate_db_duplicate'] = False

    num_vectors = index.ntotal
    message_placeholder = st.empty()
    progress_bar = st.progress(0)

    for i in range(num_vectors):
        # Check if stop has been requested
        if st.session_state['stop_requested']:
            message_placeholder.text("Processing was stopped by the user.")
            progress_bar.empty()
            # Optionally, reset the stop flag here if you want the process to be restartable without refreshing the page
            st.session_state['stop_requested'] = False
            return None

        progress = (i + 1) / num_vectors
        message_placeholder.text(f"Finding duplicates: processing vector {i+1} of {num_vectors}")
        progress_bar.progress(progress)

        query_vector = np.array([index.reconstruct(i)])
        distances, indices = index.search(query_vector, 2)

        for j in range(1, indices.shape[1]):
            #if distances[0][j] < threshold:
            idx1, idx2 = i, indices[0][j]
            if idx1 != idx2:
                sorted_pair = (min(idx1, idx2), max(idx1, idx2))
                save_duplicate_pair(metadata[sorted_pair[0]], metadata[sorted_pair[1]], distances[0][j])

    message_placeholder.text(f"Finished processing {num_vectors} vectors.")
    progress_bar.empty()

def show_duplicate_photos_faiss(assets, limit, min_threshold, max_threshold):
    # First check if the database is populated
    if not is_db_populated():
        st.write("The database does not contain any duplicate entries. Please generate/update the database.")
        return  # Exit the function early if the database is not populated
    
    # Load duplicates from database
    duplicates = load_duplicate_pairs(min_threshold, max_threshold)

    if duplicates:
        st.write(f"Found {len(duplicates)} duplicate pairs with FAISS code within threshold {min_threshold} < x < {max_threshold}:")
        progress_bar = st.progress(0)
        num_duplicates_to_show = min(len(duplicates), limit)

        for i, dup_pair in enumerate(duplicates[:num_duplicates_to_show]):
            # Check if stop was requested
            if st.session_state.get('stop_requested', False):
                st.write("Processing was stopped by the user.")
                st.session_state['stop_requested'] = False  # Reset the flag for future operations
                st.session_state['generate_db_duplicate'] = False
                break  # Exit the loop

            progress = (i + 1) / num_duplicates_to_show
            progress_bar.progress(progress)

            asset_id_1, asset_id_2 = dup_pair
            # Assuming `streamAsset` and `getAssetInfo` are defined elsewhere in your code
            image1 = streamAsset(asset_id_1, immich_server_url, 'Thumbnail (fast)', api_key)
            image2 = streamAsset(asset_id_2, immich_server_url, 'Thumbnail (fast)', api_key)
            asset1_info = getAssetInfo(asset_id_1, assets)
            asset2_info = getAssetInfo(asset_id_2, assets)

            if image1 and image2:
                col1, col2 = st.columns(2)
                with col1:
                    st.image(image1, caption=f"Name: {asset_id_1}")
                with col2:
                    st.image(image2, caption=f"Name: {asset_id_2}")
                
                display_asset_column(col1, asset1_info, asset2_info, asset_id_1, immich_server_url, api_key)
                display_asset_column(col2, asset2_info, asset1_info, asset_id_2, immich_server_url, api_key)
            else:
                st.write(f"Missing information for one or both assets: {asset_id_1}, {asset_id_2}")

            st.markdown("---")
        progress_bar.progress(100)
    else:
        st.write("No duplicates found.")

def setup_session_state():
    """Initialize session state with default values."""
    session_defaults = {
        'enable_size_filter': True,
        'size_ratio': 5,
        'deleted_photo': False,
        'filter_nr': 10,
        'show_duplicates': False,
        'calculate_phash': False,
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
        with st.expander("Experimental", expanded=True):
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
                value=st.session_state.get('faiss_min_threshold', 0.5), step=0.01,
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
                value=st.session_state.get('limit', 50), step=1,
                help="Set the number of pairs to display for the comparison"
            )

            if st.button('Find photos duplicate'):
                    st.session_state['show_faiss_duplicate'] = True

        with st.expander("Filter Settings", expanded=True):
            # Checkbox for enabling size filter
            st.session_state['enable_size_filter'] = st.checkbox(
                "Enable Size Difference Filter", 
                value=st.session_state['enable_size_filter']
            )

            # Input for setting the minimum size difference ratio
            st.session_state['size_ratio'] = st.number_input(
                "Minimum Size Difference Ratio", min_value=1, 
                value=st.session_state['size_ratio'], step=1
            )

            # Input for number of photos to show
            st.session_state['filter_nr'] = st.number_input(
                "Nr of photo to show", min_value=1, 
                value=st.session_state['filter_nr'], step=1
            )

            # Selection for photo display type
            photo_options = ['Original Photo (slow)', 'Thumbnail (fast)']
            st.session_state['photo_choice'] = st.selectbox(
                "Choose photo type to display", options=photo_options, 
                index=photo_options.index(st.session_state['photo_choice'])
            )

            # Checkbox for including trashed items in the search
            st.session_state['is_trashed'] = st.checkbox(
                "Include trashed items", value=st.session_state['is_trashed']
            )

        # Display program version and additional data
        program_version = "v0.0.8"
        additional_data = "Immich duplicator finder"
        st.markdown(f"**Version:** {program_version}\n\n{additional_data}")

def main():
    setup_session_state()
    configure_sidebar()
    assets = None

    # Attempt to fetch assets if any asset-related operation is to be performed
    if st.session_state['show_duplicates'] or st.session_state['calculate_phash'] or st.session_state['show_faiss_duplicate'] or st.session_state['calculate_faiss']:
        assets = fetchAssets(immich_server_url, api_key)
        if not assets:
            st.error("No assets found or failed to fetch assets.")
            return  # Stop further execution since there are no assets to process

    # Show duplicate photos if the corresponding flag is set
    if st.session_state['show_duplicates'] and assets:
        show_duplicate_photos(assets, st.session_state['filter_nr'])

    # Calculate perceptual hash if the corresponding flag is set
    if st.session_state['calculate_phash'] and assets:
        calculatepHashPhotos(assets, immich_server_url, api_key)

    # Calculate the FAISS index if the corresponding flag is set
    if st.session_state['calculate_faiss'] and assets:
        calculateFaissIndex(assets, immich_server_url, api_key)

    # Show FAISS duplicate photos if the corresponding flag is set
    if st.session_state['generate_db_duplicate']:
        generate_db_duplicate()

    # Show FAISS duplicate photos if the corresponding flag is set
    if st.session_state['show_faiss_duplicate'] and assets:
        show_duplicate_photos_faiss(assets, st.session_state['limit'], st.session_state['faiss_min_threshold'],st.session_state['faiss_max_threshold'])

if __name__ == "__main__":
    main()