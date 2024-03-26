import requests
import os
import json
import numpy as np
from streamlit_image_comparison import image_comparison
import streamlit as st

from immichApi import getAssetInfo, getServerStatistics, deleteAsset, fetchAssets
from db import startup_db_configurations, startup_processed_assets_db, countProcessedAssets, getHashFromDb
from startup import startup_sidebar
from imageProcessing import streamAsset,calculatepHashPhotos

###############STARTUP#####################

startup_db_configurations()
startup_processed_assets_db()
immich_server_url, api_key, timeout = startup_sidebar()

def findDuplicatesHash(assets,model):
    """Find and return duplicates based on file hash, correlating specific resolutions."""
    seen_hashes = {}
    duplicates = []
    resolution_counts  = {}  # Track resolution correlations for the same hash

    for asset in assets:
        resolution_height = asset.get('exifInfo', {}).get('exifImageHeight', 'Unknown')
        resolution_width = asset.get('exifInfo', {}).get('exifImageWidth', 'Unknown')
        resolution = "{} x {}".format(resolution_height, resolution_width)

        # Check resolution only if avoid_thumbnail_jpeg is True and skip specific resolutions
        if st.session_state['avoid_thumbnail_jpeg'] and (resolution == "1600 x 1200" or resolution == "1200 x 1600"):
            continue  # Skip this asset and move to the next one

        if model=='thumbhash':
            file_hash = asset.get('thumbhash')
        if model=='dbhash':
            file_hash = getHashFromDb(asset.get('id'))
        else:
            file_hash = asset.get('thumbhash')
        
        if file_hash in seen_hashes:
            # Add the current asset as a duplicate
            duplicates.append((seen_hashes[file_hash], asset))

            # Increment count for this resolution among duplicates
            resolution_counts[resolution] = resolution_counts.get(resolution, 0) + 1

            # Also update for the resolution of the asset previously seen with this hash
            prev_asset = seen_hashes[file_hash]
            prev_resolution_height = prev_asset.get('exifInfo', {}).get('exifImageHeight', 'Unknown')
            prev_resolution_width = prev_asset.get('exifInfo', {}).get('exifImageWidth', 'Unknown')
            prev_resolution = "{} x {}".format(prev_resolution_height, prev_resolution_width)
            resolution_counts[prev_resolution] = resolution_counts.get(prev_resolution, 0) + 1
        else:
            seen_hashes[file_hash] = asset

    return duplicates, resolution_counts

def compare_and_color(value1, value2):
    if value1 > value2:
        return f"<span style='color: green;'>{value1}</span>"
    elif value1 < value2:
        return f"<span style='color: red;'>{value1}</span>"
    else:
        return f"{value1}"

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
        for i, (original, duplicate, original_size_info, duplicate_size_info) in enumerate(limited_duplicates, start=1):  # Limit to the first 10 for testing
            # Update the progress bar based on the current iteration relative to the total
            progress_bar.progress(i / len(duplicates))
            
            original_size=getAssetInfo(original['id'],assets)
            duplicate_size=getAssetInfo(duplicate['id'],assets)

            st.write(f"Duplicate Pair {i}")
            
            photo_choice = st.session_state['photo_choice']
            #ORIGINAL SIZE
            original_image = streamAsset(original['id'], immich_server_url, photo_choice,api_key)
            duplicate_image = streamAsset(duplicate['id'], immich_server_url, photo_choice, api_key)

            if original_image is not None and duplicate_image is not None:
                # Convert PIL images to numpy arrays if necessary
                image1 = np.array(original_image)
                image2 = np.array(duplicate_image)
                # Proceed with image comparison
                image_comparison(
                    img1=image1,
                    img2=image2,
                    label1=f"Name: {original_size[1]}",
                    label2=f"Name: {duplicate_size[1]}",
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
                details_img1 = f"""
                - **File name:** {original_size[1]}
                - **Photo with ID:** {original['id']}
                - **Size:** {compare_and_color(original_size[0], duplicate_size[0])}
                - **Resolution:** {compare_and_color(original_size[2], duplicate_size[2])}
                - **Lens Model:** {original_size[3]}
                - **Created At:** {compare_and_color(original_size[4], duplicate_size[4])}
                - **Is External:** {'Yes' if original_size[5] else 'No'}
                - **Is Offline:** {'Yes' if original_size[6] else 'No'}
                - **Is Read-Only:** {'Yes' if original_size[7] else 'No'}
                """
                st.markdown(details_img1, unsafe_allow_html=True)
               
                if st.button(f"Delete original {i}", key=f"delete-org-{i}"):
                    if deleteAsset(immich_server_url, original['id'], api_key):
                        st.success(f"Deleted photo {i}")
                        st.session_state['deleted_photo'] = True
                    else:
                        st.error(f"Failed to delete photo {i}")
                                        
            with col2:
                # For the duplicate, invert the comparison to highlight the duplicate's stats accordingly
                details_img2 = f"""
                - **File name:** {duplicate_size[1]}
                - **Photo with ID:** {duplicate['id']}
                - **Size:** {compare_and_color(duplicate_size[0], original_size[0])}
                - **Resolution:** {compare_and_color(duplicate_size[2], original_size[2])}
                - **Lens Model:** {duplicate_size[3]}
                - **Created At:** {compare_and_color(duplicate_size[4], original_size[4])}
                - **Is External:** {'Yes' if duplicate_size[5] else 'No'}
                - **Is Offline:** {'Yes' if duplicate_size[6] else 'No'}
                - **Is Read-Only:** {'Yes' if duplicate_size[7] else 'No'}
                """
                st.markdown(details_img2, unsafe_allow_html=True)

                if st.button(f"Delete duplicate {i}", key=f"delete-dup-{i}"):
                    if deleteAsset(immich_server_url,duplicate['id'],api_key):
                        st.success(f"Deleted photo {i}")
                    else:
                        st.error(f"Failed to delete photo {i}")

            st.markdown("---")
        progress_bar.progress(100)

    else:
        st.write("No duplicates found.")

def main():   
    # Initialize session state variables with default values if they are not already set
    session_defaults = {
        'enable_size_filter': True,
        'size_ratio': 5,
        'deleted_photo': False,
        'filter_nr': 10,
        'show_duplicates': False,
        'calcolate_phash': False,
        'avoid_thumbnail_jpeg': True,
        'photo_choice': 'Thumbnail (fast)'  # Initialize with default action to not show duplicates
    }
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    #################

    with st.sidebar.expander("Utility", expanded=True):
        stats = getServerStatistics(immich_server_url, api_key)
        if stats is not None:
            total_photos = stats['photos']  # Replace 'totalPhotos' with the actual key from the response
        else:
            total_photos = 0
        processed_assets = countProcessedAssets()
        #st.write(f"Assets Processed: {processed_assets} / {total_photos}")
        # Button to trigger duplicates finding
        #if st.button('Calcolate pHash for all photos'):
        #    st.session_state['calcolate_phash'] = True

    with st.sidebar.expander("Filter Settings", expanded=True):
        # Direct binding of session state to UI widgets
        st.session_state['enable_size_filter'] = st.checkbox("Enable Size Difference Filter", value=st.session_state['enable_size_filter'])
        st.session_state['size_ratio'] = st.number_input("Minimum Size Difference Ratio", min_value=1, value=st.session_state['size_ratio'], step=1)
        st.session_state['filter_nr'] = st.number_input("Nr of photo to show", min_value=1, value=st.session_state['filter_nr'], step=1)

        # Adding a select box for choosing between original photo and thumbnail
        photo_options = ['Original Photo (slow)', 'Thumbnail (fast)']
        photo_choice = st.selectbox("Choose photo type to display", options=photo_options, index=photo_options.index(st.session_state['photo_choice']))
        st.session_state['photo_choice'] = photo_choice
        st.session_state['avoid_thumbnail_jpeg'] = st.checkbox("Avoid to analyze thumbnail generated by Immich (1600x1200)", value=st.session_state['avoid_thumbnail_jpeg'])

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
        assets = fetchAssets(immich_server_url,api_key)  # Ensure this handles errors/exceptions properly
        if assets:
            calculatepHashPhotos(assets, immich_server_url, api_key)
        else:
            st.write("No assets found or failed to fetch assets.")

    # Add version and other data at the bottom
    st.sidebar.markdown("---")
    program_version = "v0.0.7"  # Example version
    additional_data = "Immich duplicator finder"
    st.sidebar.markdown(f"**Version:** {program_version}\n\n{additional_data}")

if __name__ == "__main__":
    main()