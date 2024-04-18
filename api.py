import requests, json
import streamlit as st
from PIL import Image, UnidentifiedImageError, ImageFile
from io import BytesIO
from db import bytes_to_megabytes
from pillow_heif import register_heif_opener

@st.cache_data(show_spinner=True) 
def fetchAssets(immich_server_url, api_key, timeout):
    # Initialize messaging and progress
    if 'fetch_message' not in st.session_state:
        st.session_state['fetch_message'] = ""
    message_placeholder = st.empty()

    # Initialize assets to None or an empty list, depending on your usage expectation
    assets = []

    # Remove trailing slash from immich_server_url if present
    base_url = immich_server_url.rstrip('/')
    asset_info_url = f"{base_url}/api/asset/"
    
    try:
        with st.spinner('Fetching assets...'):
            # Make the HTTP GET request
            response = requests.get(asset_info_url, headers={'Accept': 'application/json', 'x-api-key': api_key}, verify=False, timeout=timeout)
            response.raise_for_status()  # This will raise an exception for HTTP errors
            
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                if response.text:
                    assets = response.json()  # Decode JSON response into a list of assets
                    assets = [asset for asset in assets if asset.get("type") == "IMAGE"]                       
                    st.session_state['fetch_message'] = 'Assets fetched successfully!'
                else:
                    st.session_state['fetch_message'] = 'Received an empty response.'
                    assets = []  # Set assets to empty list if response is empty
            else:
                st.session_state['fetch_message'] = f'Unexpected Content-Type: {content_type}\nResponse content: {response.text}'
                assets = []  # Set assets to empty list if unexpected content type

    except requests.exceptions.ConnectTimeout:
        st.session_state['fetch_message'] = 'Failed to connect to the server. Please check your network connection and try again.'
        assets = []  # Set assets to empty list on connection timeout

    except requests.exceptions.HTTPError as e:
        st.session_state['fetch_message'] = f'HTTP error occurred: {e}'
        assets = []  # Set assets to empty list on HTTP error

    except requests.exceptions.RequestException as e:
        st.session_state['fetch_message'] = f'Error fetching assets: {e}'
        assets = []  # Set assets to empty list on other request errors

    message_placeholder.text(st.session_state['fetch_message'])
    return assets

#@st.cache_data(show_spinner=True)
def streamAsset(asset_id, immich_server_url,photo_choice,api_key):   
    # Determine whether to fetch the original or thumbnail based on user selection
    register_heif_opener()
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    if photo_choice == 'Thumbnail (fast)':
        response = requests.request("GET", f"{immich_server_url}/api/asset/thumbnail/{asset_id}?format=JPEG", headers={'Accept': 'application/octet-stream','x-api-key': api_key}, data={})
    else:
        asset_download_url = f"{immich_server_url}/api/download/asset/{asset_id}"
        response = requests.post(asset_download_url, headers={'Accept': 'application/octet-stream', 'x-api-key': api_key}, stream=True)
        
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
        finally:
            image_bytes.close()  # Ensure the stream is always closed
            del image_bytes 
    else:
        print(f"Skipping non-image asset_id {asset_id} with Content-Type: {response.headers.get('Content-Type')}")
        return None

def getAssetInfo(asset_id, assets):
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
        is_trashed = asset_info.get('isTrashed', False)  # Extract isTrashed
        is_favorite = asset_info.get('isFavorite', False)        
        # Add more fields as needed and return them
        return formatted_file_size, original_file_name, resolution, lens_model, creation_date, is_external, is_offline, is_read_only,is_trashed,is_favorite
    else:
        return None
    
def getServerStatistics(immich_server_url, api_key):
    try:
        response = requests.get(f"{immich_server_url}/api/server-info/statistics", headers={'Accept': 'application/json', 'x-api-key': api_key})
        if response.ok:        
            return response.json()  # This will parse the JSON response body and return it as a dictionary
        else:
            return None
    except:
        return None
    
def deleteAsset(immich_server_url, asset_id, api_key):
    st.session_state['show_faiss_duplicate'] = False
    url = f"{immich_server_url}/api/asset"
    payload = json.dumps({
        "force": True,
        "ids": [asset_id]
    })
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }

    try:
        response = requests.delete(url, headers=headers, data=payload)
        if response.status_code == 204:
            st.success(f"Successfully deleted asset with ID: {asset_id}")
            print(f"Successfully deleted asset with ID: {asset_id}")
            return True
        else:
            # Provide more detailed error feedback
            error_message = response.json().get('message', 'No additional error message provided.')
            st.error(f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            print(f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            return False
    except requests.RequestException as e:
        # Handle request-related exceptions
        st.error(f"Request failed: {str(e)}")
        print(f"Request failed: {str(e)}")
        return False

def updateAsset(immich_server_url, asset_id, api_key, dateTimeOriginal, description, isFavorite, latitude, longitude, isArchived):
    url = f"{immich_server_url}/api/asset/{asset_id}"  # Ensure the URL is constructed correctly
    
    payload = json.dumps({
        "dateTimeOriginal": dateTimeOriginal,
        "description": description,
        "isArchived": isArchived,
        "isFavorite": isFavorite,
        "latitude": latitude,
        "longitude": longitude
    })
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': api_key  # Authorization via API key
    }

    try:
        response = requests.put(url, headers=headers, data=payload)
        if response.status_code == 200:
            response_data = response.json()
            st.success(f"Successfully move on archive asset with ID: {asset_id}")
            print(f"Successfully move on archive asset with ID: {asset_id}. Response: {response_data}")
            return True
        else:
            error_message = response.json().get('message', 'No additional error message provided.')
            st.error(f"Failed to move on archive asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            print(f"Failed to move on archive asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}")
            return False
    except requests.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        print(f"Request failed: {str(e)}")
        return False