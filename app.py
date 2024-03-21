import requests
import os
import json
import numpy as np
from PIL import Image
import sqlite3
import io
from streamlit_image_comparison import image_comparison
import streamlit as st

def load_settings_from_db():
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM settings LIMIT 1")
    settings = c.fetchone()
    conn.close()
    return settings if settings else (None, None, None)

def startup_sidebar():
    logo_path = "https://immich.app/img/immich-logo-stacked-dark.svg"

    st.sidebar.image(logo_path, width=150)
    st.sidebar.markdown("---")

    immich_server_url, api_key, images_folder = load_settings_from_db()

    with st.sidebar.expander("Login Settings", expanded=False):
        immich_server_url = st.text_input('IMMICH Server URL', immich_server_url)
        api_key = st.text_input('API Key', api_key)
        if st.button('Save Settings'):
            save_settings_to_db(immich_server_url, api_key, images_folder)
            st.success('Settings saved!')
    return immich_server_url, api_key

def startup_configurations():
    st.set_page_config(page_title="Immich duplicator finder", page_icon="https://avatars.githubusercontent.com/u/109746326?s=48&v=4")
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (immich_server_url text, api_key text, images_folder text)''')
    conn.commit()
    conn.close()

startup_configurations()
immich_server_url, api_key = startup_sidebar()

def save_settings_to_db(immich_server_url, api_key, images_folder):
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    # This simple logic assumes one row of settings; adjust according to your needs
    c.execute("DELETE FROM settings")  # Clear existing settings
    c.execute("INSERT INTO settings VALUES (?, ?, ?)", (immich_server_url, api_key, images_folder))
    conn.commit()
    conn.close()

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
def get_asset_thumbnail(asset_id):
    thumbnail = requests.request("GET", f"{immich_server_url}/api/asset/thumbnail/{asset_id}", headers={'Accept': 'application/octet-stream','x-api-key': api_key}, data={})
    return thumbnail

@st.cache_data(show_spinner=True)
def stream_asset(asset_id, immich_server_url):
    # Construct the download URL for the asset
    asset_download_url = f"{immich_server_url}/api/download/asset/{asset_id}"
    # Stream the asset
    response = requests.post(asset_download_url, headers={'Accept': 'application/octet-stream','x-api-key': api_key}, stream=True)
    if response.status_code == 200:
        image_bytes = io.BytesIO(response.content)
        image = Image.open(image_bytes)
        return image  # Return the PIL Image object
    return None

def get_asset_info(asset_id, assets, asset_info_required):
    # Search for the asset in the provided list of assets.
    asset_info = next((asset for asset in assets if asset['id'] == asset_id), None)

    if asset_info:
        # Extract all required info.
        try:
            formatted_file_size = bytes_to_megabytes(asset_info['exifInfo']['fileSizeInByte'])
        except KeyError:
            formatted_file_size = "Unknown"
        original_file_name = asset_info.get('originalFileName', 'Unknown')
        resolution = "{} x {}".format(asset_info.get('exifInfo', {}).get('exifImageHeight', 'Unknown'), asset_info.get('exifInfo', {}).get('exifImageWidth', 'Unknown'))
        lens_model = asset_info.get('exifInfo', {}).get('lensModel', 'Unknown')
        creation_date = asset_info.get('fileCreatedAt', 'Unknown')

        # Add more fields as needed

        return formatted_file_size, original_file_name, resolution, lens_model, creation_date
    else:
        return None
 
def fetch_assets():
    asset_info_url = f"{immich_server_url}/api/asset/"
    with st.spinner('Fetching assets...'):
        response = requests.get(asset_info_url, headers={'Accept': 'application/json','x-api-key': api_key})
        response.raise_for_status()
        assets = response.json()
    st.success('Assets fetched successfully!')
    return assets

def find_duplicates_hash(assets):
    """Find and return duplicates based on file hash."""
    seen_hashes = {}
    duplicates = []
    for asset in assets:
        file_hash = asset.get('thumbhash')
        if file_hash in seen_hashes:
            duplicates.append((seen_hashes[file_hash], asset))
        else:
            seen_hashes[file_hash] = asset
    return duplicates

def delete_asset(asset_id):
    url = f"{immich_server_url}/api/asset"
    payload = json.dumps({
        "force": True,
        "ids": [asset_id]
    })
    response = requests.request("DELETE", url, headers={'Content-Type': 'application/json','x-api-key': api_key}, data=payload)
    print(response)
    if response.status_code == 204:
        st.success(f"Successfully deleted asset with ID: {asset_id}")
        return True
    else:
        st.error(f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}")
        return False

def show_duplicate_photos(assets,limit):
     # Assuming this fetches asset information
    duplicates = find_duplicates_hash(assets)

    if duplicates:
        st.write(f"Total duplicates found (showing first {limit}) on total of : {len(find_duplicates_hash(assets))}")
        progress_bar = st.progress(0)
        filtered_duplicates = []
        for original, duplicate in duplicates:
            original_size_info = get_asset_info(original['id'],assets,'fileSizeInByte')
            duplicate_size_info = get_asset_info(duplicate['id'],assets, 'fileSizeInByte')

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
            
            original_size=get_asset_info(original['id'],assets,'fileSizeInByte')
            duplicate_size=get_asset_info(duplicate['id'],assets,'fileSizeInByte')

            st.write(f"Duplicate Pair {i}")
            
            #ORIGINAL SIZE
            image1 = np.array(stream_asset(original['id'],immich_server_url))
            image2 = np.array(stream_asset(duplicate['id'],immich_server_url))

            # render image-comparison
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
            )

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"Photo with ID: {original['id']}")
                st.write(f"File name: {original_size[1]}")
                st.write(f"Size: {original_size[0]}")
                st.write(f"Resolution: {original_size[2]}")
                st.write(f"Lens Model: {original_size[3]}")
                st.write(f"Created At: {original_size[4]}")
               

                if st.button(f"Delete {i}", key=f"delete-org-{i}"):
                    if delete_asset(original['id']):
                        st.success(f"Deleted photo {i}")
                        st.session_state['deleted_photo'] = True
                    else:
                        st.error(f"Failed to delete photo {i}")
                                        
            with col2:
                st.write(f"Photo with ID: {duplicate['id']}")
                st.write(f"File name: {duplicate_size[1]}")
                st.write(f"Size: {duplicate_size[0]}")
                st.write(f"Resolution: {duplicate_size[2]}")
                st.write(f"Lens Model: {duplicate_size[3]}")
                st.write(f"Created At: {duplicate_size[4]}")

                if st.button(f"Delete {i}", key=f"delete-dup-{i}"):
                    if delete_asset(duplicate['id']):
                        st.success(f"Deleted photo {i}")
                    else:
                        st.error(f"Failed to delete photo {i}")

            st.markdown("---")
        progress_bar.progress(100)

    else:
        st.write("No duplicates found.")

def main():
    # Initialize session state variables if they don't exist, using a pattern that avoids conflicts
    if 'enable_size_filter' not in st.session_state:
        st.session_state['enable_size_filter'] = True
    if 'size_ratio' not in st.session_state:
        st.session_state['size_ratio'] = 5
    if 'deleted_photo' not in st.session_state:
        st.session_state['deleted_photo'] = False
    if 'filter_nr' not in st.session_state:
        st.session_state['filter_nr'] = 10

    #################

    with st.sidebar.expander("Filter Settings", expanded=True):
        # Use session state directly for filter settings with UI elements, avoiding setting default values that conflict with session state
        st.checkbox("Enable Size Difference Filter", value=st.session_state['enable_size_filter'], key='enable_size_filter')
        st.number_input("Minimum Size Difference Ratio", min_value=1, value=st.session_state['size_ratio'], step=1, key='size_ratio')
        st.number_input("Nr of photo to show", min_value=1, value=st.session_state['filter_nr'], step=1, key='filter_nr')

        # Use a button to update session state for showing duplicates
        if st.button('Find Duplicates'):
            st.session_state['show_duplicates'] = True

    if st.session_state.get('show_duplicates') and st.session_state['deleted_photo'] == False:
        # Check if 'assets' is not None AND has content (i.e., it's not empty)
        print("Fetch con cache")
        assets = fetch_assets()
        limit=st.session_state['filter_nr']
        show_duplicate_photos(assets,limit) 
    
    if st.session_state.get('show_duplicates') and st.session_state['deleted_photo'] == True:
        # Check if 'assets' is not None AND has content (i.e., it's not empty)
        print("Fetch senza cache")
        assets = fetch_assets()
        limit=st.session_state['filter_nr']
        show_duplicate_photos(assets,limit) 
        show_duplicate_photos(assets,limit) 

    st.sidebar.markdown("---")

    # Add version and other data at the bottom
    program_version = "v0.0.4"  # Example version
    additional_data = "Immich duplicator finder"
    st.sidebar.markdown(f"**Version:** {program_version}\n\n{additional_data}")

if __name__ == "__main__":
    main()