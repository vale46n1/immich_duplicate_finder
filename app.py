import numpy as np
from streamlit_image_comparison import image_comparison
import streamlit as st

from utility import display_asset_column, findDuplicatesHash
from immichApi import getAssetInfo, getServerStatistics, deleteAsset, fetchAssets
from db import startup_db_configurations, startup_processed_assets_db, countProcessedAssets, getHashFromDb
from startup import startup_sidebar
from imageProcessing import streamAsset,calculatepHashPhotos,calculateFaissIndex
from faissCalc import init_or_load_faiss_index,find_faiss_duplicates
import os

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
###############STARTUP#####################

# Set page title and favicon
st.set_page_config(page_title="Immich duplicator finder ", page_icon="https://immich.app/img/immich-logo-stacked-dark.svg")

startup_db_configurations()
startup_processed_assets_db()
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

def show_duplicate_photos_faiss(assets,limit,threshold):
    # Load the index and metadata
    index, metadata = init_or_load_faiss_index()
    if not index or not metadata:
        st.write("FAISS index or metadata not available.")
        return
    # Assuming find_duplicates is implemented and returns a list of (asset_id, asset_id) pairs for duplicates
    duplicates = find_faiss_duplicates(index, metadata, threshold)  # Adjust threshold as needed
    
    if duplicates:
        st.write(f"Found {len(duplicates)} duplicate pairs with FAISS code:")
        progress_bar = st.progress(0)
        num_duplicates_to_show = min(len(duplicates), limit)
        
        for i, dup_pair in enumerate(duplicates[:limit]):  # Only show up to 'limit' duplicates
            
            # Update progress
            progress = (i + 1) / num_duplicates_to_show
            progress_bar.progress(progress)

            asset_id_1, asset_id_2 = dup_pair

            #######DATA#########
            image1 = streamAsset(asset_id_1,immich_server_url,'Thumbnail (fast)',api_key)
            image2 = streamAsset(asset_id_2,immich_server_url,'Thumbnail (fast)',api_key)
            asset1_info=getAssetInfo(asset_id_1,assets)
            asset2_info=getAssetInfo(asset_id_2,assets)

            if image1 is not None and image2 is not None:
                # Convert PIL images to numpy arrays if necessary
                image1_np = np.array(image1)
                image2_np = np.array(image2)
                # Proceed with image comparison
                image_comparison(
                    img1=image1_np,
                    img2=image2_np,
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

def main():   
    assets = None
    # Initialize session state variables with default values if they are not already set
    session_defaults = {
        'enable_size_filter': True,
        'size_ratio': 5,
        'deleted_photo': False,
        'filter_nr': 10,
        'show_duplicates': False,
        'calcolate_phash': False,
        ##########FAISS###############
        'calcolate_faiss': False,
        'show_faiss_duplicate': False,
        'faiss_threshold': 0.6,
        ###########################
        'avoid_thumbnail_jpeg': True,
        'is_trashed': False,
        'is_favorite': True,
        'photo_choice': 'Thumbnail (fast)'  # Initialize with default action to not show duplicates
    }
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    #################
    with st.sidebar.expander("Experimental", expanded=True):
        #FAISS INDEX
        if st.button('Generate/Update FAISS index'):
            st.session_state['calcolate_faiss'] = True

        st.session_state['faiss_threshold'] = st.number_input("Faiss threshold", min_value=0.1, value=st.session_state['faiss_threshold'], step=0.1)
        if st.button('Find photos duplicate'):
            st.session_state['show_faiss_duplicate'] = True

    with st.sidebar.expander("Filter Settings", expanded=True):
        # Direct binding of session state to UI widgets
        st.session_state['enable_size_filter'] = st.checkbox("Enable Size Difference Filter", value=st.session_state['enable_size_filter'])
        st.session_state['size_ratio'] = st.number_input("Minimum Size Difference Ratio", min_value=1, value=st.session_state['size_ratio'], step=1)
        st.session_state['filter_nr'] = st.number_input("Nr of photo to show", min_value=1, value=st.session_state['filter_nr'], step=1)

        # Adding a select box for choosing between original photo and thumbnail
        photo_options = ['Original Photo (slow)', 'Thumbnail (fast)']
        photo_choice = st.selectbox("Choose photo type to display", options=photo_options, index=photo_options.index(st.session_state['photo_choice']))
        st.session_state['photo_choice'] = photo_choice
        #st.session_state['avoid_thumbnail_jpeg'] = st.checkbox("Avoid to analyze thumbnail generated by Immich (1600x1200)", value=st.session_state['avoid_thumbnail_jpeg'])
        st.session_state['is_trashed'] = st.checkbox("Include trashed items", value=st.session_state['is_trashed'])
        #st.session_state['is_favorite'] = st.checkbox("Filter favorite elements", value=st.session_state['is_favorite'])
        # Button to trigger duplicates finding
        if st.button('Find Duplicates'):
            st.session_state['show_duplicates'] = True

    # Only proceed to show duplicates if 'show_duplicates' flag is true
    if st.session_state['show_duplicates']:
        assets = fetchAssets(immich_server_url,api_key)  # Ensure this handles errors/exceptions properly
        limit = st.session_state['filter_nr']
        if assets:
            show_duplicate_photos(assets, limit)
        else:
            st.write("No assets found or failed to fetch assets.")

    if st.session_state['calcolate_phash']:
        if assets is None: 
            assets = fetchAssets(immich_server_url,api_key) # Ensure this handles errors/exceptions properly
        if assets:
            calculatepHashPhotos(assets, immich_server_url, api_key)
        else:
            st.write("No assets found or failed to fetch assets.")

    if st.session_state['calcolate_faiss']:
        
        assets = fetchAssets(immich_server_url,api_key)  # Ensure this handles errors/exceptions properly
        if assets:
            calculateFaissIndex(assets, immich_server_url, api_key)
        else:
            st.write("No assets found or failed to fetch assets.")
    
    if st.session_state['show_faiss_duplicate']:
        
        print(st.session_state['faiss_threshold'])
        if assets is None: 
            print(f"Fetch Assets")
            assets = fetchAssets(immich_server_url,api_key)
        show_duplicate_photos_faiss(assets,50,st.session_state['faiss_threshold']) #Limit / threshold

    # Add version and other data at the bottom
    st.sidebar.markdown("---")
    program_version = "v0.0.8"  # Example version
    additional_data = "Immich duplicator finder"
    st.sidebar.markdown(f"**Version:** {program_version}\n\n{additional_data}")

if __name__ == "__main__":
    main()