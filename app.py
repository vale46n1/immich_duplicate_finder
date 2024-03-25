import requests
import os
import json
import numpy as np
from PIL import Image, UnidentifiedImageError
import sqlite3
import io
from io import BytesIO
from streamlit_image_comparison import image_comparison
import streamlit as st
import pandas as pd

def load_settings_from_db():
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM settings LIMIT 1")
    settings = c.fetchone()
    conn.close()
    return settings if settings else (None, None, None, 10)

def save_settings_to_db(immich_server_url, api_key, images_folder, timeout):
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    # This simple logic assumes one row of settings; adjust according to your needs
    c.execute("DELETE FROM settings")  # Clear existing settings
    c.execute("INSERT INTO settings VALUES (?, ?, ?, ?)", (immich_server_url, api_key, images_folder, timeout))
    conn.commit()
    conn.close()

def startup_sidebar():
    logo_path = "https://immich.app/img/immich-logo-stacked-dark.svg"

    st.sidebar.image(logo_path, width=150)
    st.sidebar.markdown("---")

    immich_server_url, api_key, images_folder, timeout = load_settings_from_db()

    with st.sidebar.expander("Login Settings", expanded=False):
        immich_server_url = st.text_input('IMMICH Server URL', immich_server_url).rstrip('/')
        api_key = st.text_input('API Key', api_key)
        timeout = st.number_input('Request timeout', timeout)
        if st.button('Save Settings'):
            save_settings_to_db(immich_server_url, api_key, images_folder, timeout)
            st.success('Settings saved!')
    return immich_server_url, api_key, timeout

def startup_configurations():
    st.set_page_config(page_title="Immich duplicator finder", page_icon="https://avatars.githubusercontent.com/u/109746326?s=48&v=4")
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (immich_server_url text, api_key text, images_folder text, timeout number)''')
    conn.commit()
    conn.close()

startup_configurations()
immich_server_url, api_key, timeout = startup_sidebar()

def convert_heic_to_jpeg(heic_path):
    heic_image = Image.open(heic_path)
    jpeg_path = heic_path.rsplit('.', 1)[0] + '.jpg'
    heic_image.save(jpeg_path, format='JPEG')
    return jpeg_path
  
def bytes_to_megabytes(bytes_size):
    """Convert bytes to megabytes (MB) and format to 3 decimal places."""
    if bytes_size is None:
        return "0.001 MB"  # Assuming you want to return this default value for None input
    megabytes = bytes_size / (1024 * 1024)
    return f"{megabytes:.3f} MB"

def validate_image(image_content):
    try:
        # Attempt to open the image to verify it's valid
        Image.open(BytesIO(image_content)).verify()
        return True
    except (IOError, ValueError):
        # The image is invalid or corrupted
        return False

@st.cache_data(show_spinner=True)
def stream_asset(asset_id, immich_server_url):   
    # Determine whether to fetch the original or thumbnail based on user selection
    photo_choice = st.session_state['photo_choice']
    if photo_choice == 'Thumbnail (fast)':
        response = requests.request("GET", f"{immich_server_url}/api/asset/thumbnail/{asset_id}?format=JPEG", headers={'Accept': 'application/octet-stream','x-api-key': api_key}, data={}, timeout=timeout)
    else:
        asset_download_url = f"{immich_server_url}/api/download/asset/{asset_id}"
        response = requests.post(asset_download_url, headers={'Accept': 'application/octet-stream', 'x-api-key': api_key}, stream=True, timeout=timeout)
        
    if response.status_code == 200 and 'image/' in response.headers.get('Content-Type', ''):
        image_bytes = BytesIO(response.content)
        try:
            image = Image.open(image_bytes)
            image.load()  # Force loading the image data while the file is open
            image_bytes.close()  # Now we can safely close the stream
            return image
        except UnidentifiedImageError:
            print(f"Failed to identify image for asset_id {asset_id}. Content-Type: {response.headers.get('Content-Type')}")
            image_bytes.close()  # Ensure the stream is closed even if an error occurs
            return None
    else:
        print(f"Skipping non-image asset_id {asset_id} with Content-Type: {response.headers.get('Content-Type')}")
        return None

def get_asset_info(asset_id, assets):
    # Search for the asset in the provided list of assets.
    asset_info = next((asset for asset in assets if asset['id'] == asset_id), None)

    if asset_info:
        # Extract all required info.
        try:
            formatted_file_size = bytes_to_megabytes(asset_info['exifInfo']['fileSizeInByte'])
        except KeyError:
            formatted_file_size = "Unknown"
        
        original_file_name = asset_info.get('originalFileName', 'Unknown')
        resolution = "{} x {}".format(
            asset_info.get('exifInfo', {}).get('exifImageHeight', 'Unknown'), 
            asset_info.get('exifInfo', {}).get('exifImageWidth', 'Unknown')
        )
        lens_model = asset_info.get('exifInfo', {}).get('lensModel', 'Unknown')
        creation_date = asset_info.get('fileCreatedAt', 'Unknown')
        is_external = asset_info.get('isExternal', False)
        is_offline = asset_info.get('isOffline', False)
        is_read_only = asset_info.get('isReadOnly', False)
        
        # Add more fields as needed and return them
        return formatted_file_size, original_file_name, resolution, lens_model, creation_date, is_external, is_offline, is_read_only
    else:
        return None

@st.cache_data(show_spinner=True) 
def fetch_assets():
    # Remove trailing slash from immich_server_url if present
    base_url = immich_server_url
    asset_info_url = f"{base_url}/api/asset/"
    
    try:
        with st.spinner('Fetching assets...'):
            # Make the HTTP GET request
            response = requests.get(asset_info_url, headers={'Accept': 'application/json', 'x-api-key': api_key}, verify=False, timeout=timeout)

            # Check for HTTP errors
            response.raise_for_status()

            # Check the Content-Type of the response
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                # Attempt to decode the JSON response
                try:
                    if response.text:
                        assets = response.json()
                        assets = [asset for asset in assets if asset.get("type") == "IMAGE"]
                        st.success('Assets fetched successfully!')
                        return assets
                    else:
                        st.error('Received an empty response.')
                        return None
                except requests.exceptions.JSONDecodeError as e:
                    st.error('Failed to decode JSON from the response.')
                    st.error(f'Response content: {response.text}')
                    return None
            else:
                st.error(f'Unexpected Content-Type: {content_type}')
                st.error(f'Response content: {response.text}')
                return None

    except requests.exceptions.ConnectTimeout:
        # Handle connection timeout specifically
        st.error('Failed to connect to the server. Please check your network connection and try again.')

    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors
        st.error(f'HTTP error occurred: {e}')

    except requests.exceptions.RequestException as e:
        # Handle other requests-related errors
        st.error(f'Error fetching assets: {e}')

    return None

def find_duplicates_hash(assets):
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


def delete_asset(asset_id):
    url = f"{immich_server_url}/api/asset"
    payload = json.dumps({
        "force": True,
        "ids": [asset_id]
    })
    response = requests.request("DELETE", url, headers={'Content-Type': 'application/json','x-api-key': api_key}, data=payload, timeout=timeout)
    print(response)
    if response.status_code == 204:
        st.success(f"Successfully deleted asset with ID: {asset_id}")
        return True
    else:
        st.error(f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}")
        return False

def show_duplicate_photos(assets,limit):
     # Assuming this fetches asset information
    duplicates, resolution_counts = find_duplicates_hash(assets)

    if duplicates:
        st.write(f"Total duplicates found {len(duplicates)} on total asset of {len(assets)} -> Currently shown: {limit}")
        progress_bar = st.progress(0)
        filtered_duplicates = []
        for original, duplicate in duplicates:
            original_size_info = get_asset_info(original['id'],assets)
            duplicate_size_info = get_asset_info(duplicate['id'],assets)

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
            
            original_size=get_asset_info(original['id'],assets)
            duplicate_size=get_asset_info(duplicate['id'],assets)

            st.write(f"Duplicate Pair {i}")
            
            #ORIGINAL SIZE
            original_image = stream_asset(original['id'], immich_server_url)
            duplicate_image = stream_asset(duplicate['id'], immich_server_url)

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
                - **Size:** {original_size[0]}
                - **Resolution:** {original_size[2]}
                - **Lens Model:** {original_size[3]}
                - **Created At:** {original_size[4]}
                - **Is External:** {'Yes' if original_size[5] else 'No'}
                - **Is Offline:** {'Yes' if original_size[6] else 'No'}
                - **Is Read-Only:** {'Yes' if original_size[7] else 'No'}
                """
                st.markdown(details_img1)
               
                if st.button(f"Delete original {i}", key=f"delete-org-{i}"):
                    if delete_asset(original['id']):
                        st.success(f"Deleted photo {i}")
                        st.session_state['deleted_photo'] = True
                    else:
                        st.error(f"Failed to delete photo {i}")
                                        
            with col2:
                details_img2 = f"""
                - **File name:** {duplicate_size[1]}
                - **Photo with ID:** {duplicate['id']}
                - **Size:** {duplicate_size[0]}
                - **Resolution:** {duplicate_size[2]}
                - **Lens Model:** {duplicate_size[3]}
                - **Created At:** {duplicate_size[4]}
                - **Is External:** {'Yes' if duplicate_size[5] else 'No'}
                - **Is Offline:** {'Yes' if duplicate_size[6] else 'No'}
                - **Is Read-Only:** {'Yes' if duplicate_size[7] else 'No'}
                """
                st.markdown(details_img2, unsafe_allow_html=True)

                if st.button(f"Delete duplicate {i}", key=f"delete-dup-{i}"):
                    if delete_asset(duplicate['id']):
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
        'avoid_thumbnail_jpeg': True,
        'photo_choice': 'Thumbnail (fast)'  # Initialize with default action to not show duplicates
    }
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    #################

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
        assets = fetch_assets()  # Ensure this handles errors/exceptions properly
        limit = st.session_state['filter_nr']
        if assets:
            show_duplicate_photos(assets, limit)
        else:
            st.write("No assets found or failed to fetch assets.")

    # Add version and other data at the bottom
    st.sidebar.markdown("---")
    program_version = "v0.0.6"  # Example version
    additional_data = "Immich duplicator finder"
    st.sidebar.markdown(f"**Version:** {program_version}\n\n{additional_data}")

if __name__ == "__main__":
    main()
