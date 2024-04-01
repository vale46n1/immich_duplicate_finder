from datetime import datetime
import streamlit as st
from datetime import datetime
from immichApi import deleteAsset
from db import getHashFromDb

def compare_and_color_data(value1, value2):
    # Parse the ISO 8601 formatted strings into datetime objects
    date1 = datetime.fromisoformat(value1.rstrip('Z'))
    date2 = datetime.fromisoformat(value2.rstrip('Z'))
    
    # Compare the datetime objects
    if date1 > date2:  # value1 is newer
        return f"<span style='color: red;'>{value1}</span>"
    elif date1 < date2:  # value1 is older
        return f"<span style='color: green;'>{value1}</span>"
    else:  # They are the same
        return f"{value1}"

def compare_and_color(value1, value2):
    if value1 > value2:
        return f"<span style='color: green;'>{value1}</span>"
    elif value1 < value2:
        return f"<span style='color: red;'>{value1}</span>"
    else:
        return f"{value1}"

def display_asset_column(col, asset1_info, asset2_info, asset_id_1, server_url, api_key):
    # Construct the details markdown string based on asset information
    details = f"""
    - **File name:** {asset1_info[1]}
    - **Photo with ID:** {asset_id_1}
    - **Size:** {compare_and_color(asset1_info[0], asset2_info[0])}
    - **Resolution:** {compare_and_color(asset1_info[2], asset2_info[2])}
    - **Lens Model:** {asset1_info[3]}
    - **Created At:** {compare_and_color_data(asset1_info[4], asset2_info[4])}
    - **Is External:** {'Yes' if asset1_info[5] else 'No'}
    - **Is Offline:** {'Yes' if asset1_info[6] else 'No'}
    - **Is Read-Only:** {'Yes' if asset1_info[7] else 'No'}
    - **Is Trashed:** {'Yes' if asset1_info[8] else 'No'}
    - **Is Favorite:** {'Yes' if asset1_info[9] else 'No'}
    """
    with col:
        st.markdown(details, unsafe_allow_html=True)
        # Generate a unique key using the current datetime, for internal use only
        current_time = datetime.now().strftime("%Y%m%d%H%M%S%f")
        delete_button_key = f"delete-{asset_id_1}-{current_time}"
        delete_button_label = f"Delete {asset_id_1}"  # The label shown to the user remains simple and clean
        if st.button(delete_button_label, key=delete_button_key):
            if deleteAsset(server_url, asset_id_1, api_key):
                st.success(f"Deleted photo {asset_id_1}")
                st.session_state[f'deleted_photo_{asset_id_1}'] = True
            else:
                st.error(f"Failed to delete photo {asset_id_1}")

def findDuplicatesHash(assets,model):
    """Find and return duplicates based on file hash, correlating specific resolutions."""
    seen_hashes = {}
    duplicates = []
    resolution_counts  = {}  # Track resolution correlations for the same hash

    for asset in assets:
        if not st.session_state.get('is_trashed', False) and asset.get('isTrashed', False):
            continue  # Skip trashed assets if include_trashed is False

        # Check resolution only if avoid_thumbnail_jpeg is True and skip specific resolutions
        #if st.session_state['avoid_thumbnail_jpeg'] and (resolution == "1600 x 1200" or resolution == "1200 x 1600"):
        #    continue  # Skip this asset and move to the next one

        resolution_height = asset.get('exifInfo', {}).get('exifImageHeight', 'Unknown')
        resolution_width = asset.get('exifInfo', {}).get('exifImageWidth', 'Unknown')
        resolution = "{} x {}".format(resolution_height, resolution_width)

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