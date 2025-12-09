import requests
import streamlit as st
from PIL import Image, UnidentifiedImageError, ImageFile
from io import BytesIO
from db import bytes_to_megabytes
from pillow_heif import register_heif_opener
import os


@st.cache_data(show_spinner=True)
def fetchAssets(immich_server_url, api_key, timeout, type):
    # Initialize messaging and progress
    if "fetch_message" not in st.session_state:
        st.session_state["fetch_message"] = ""
    message_placeholder = st.empty()

    # Initialize assets to None or an empty list, depending on your usage expectation
    assets = []

    # Remove trailing slash from immich_server_url if present
    base_url = immich_server_url.rstrip("/")
    search_candidates = [
        f"{base_url}/api/search/metadata",
        f"{base_url}/search/metadata",
    ]
    legacy_candidates = [
        f"{base_url}/api/assets",
        f"{base_url}/api/assets/",
        f"{base_url}/api/asset",
        f"{base_url}/api/asset/",
    ]

    try:
        with st.spinner("Fetching assets..."):
            search_error = None

            # Try modern search endpoint first for paginated assets.
            for search_url in search_candidates:
                try:
                    collected_assets = []
                    next_page = 1
                    size = 250
                    search_succeeded = True

                    while next_page:
                        payload = {
                            "page": next_page,
                            "size": size,
                            "order": "desc",
                        }
                        if type:
                            payload["type"] = type

                        response = requests.post(
                            search_url,
                            headers={
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                                "x-api-key": api_key,
                            },
                            json=payload,
                            timeout=timeout,
                            verify=False,
                        )

                        if (
                            response.status_code == 404
                            or "text/html" in response.headers.get("Content-Type", "")
                        ):
                            # Endpoint not available, try next candidate.
                            search_succeeded = False
                            break

                        response.raise_for_status()
                        data = response.json()
                        asset_block = (
                            data.get("assets", {}) if isinstance(data, dict) else {}
                        )
                        page_items = asset_block.get("items", [])
                        collected_assets.extend(page_items)

                        next_page_token = asset_block.get("nextPage")
                        if next_page_token:
                            try:
                                next_page = int(next_page_token)
                            except (TypeError, ValueError):
                                next_page = None
                        else:
                            next_page = None

                    if search_succeeded:
                        filtered_assets = (
                            collected_assets
                            if not type
                            else [
                                asset
                                for asset in collected_assets
                                if asset.get("type") == type
                            ]
                        )
                        assets = filtered_assets
                        if filtered_assets:
                            st.session_state["fetch_message"] = (
                                "Assets fetched successfully!"
                            )
                        else:
                            st.session_state["fetch_message"] = (
                                "No assets returned by Immich."
                            )
                        break

                except requests.exceptions.RequestException as search_err:
                    search_error = search_err
                    continue

            else:
                # Fall back to legacy endpoints if search did not succeed.
                response = None
                last_error = search_error
                last_response = None

                for legacy_url in legacy_candidates:
                    try:
                        attempt = requests.get(
                            legacy_url,
                            headers={
                                "Accept": "application/json",
                                "x-api-key": api_key,
                            },
                            verify=False,
                            timeout=timeout,
                            params={"assetType": type} if type else None,
                        )
                    except requests.exceptions.RequestException as attempt_error:
                        last_error = attempt_error
                        continue

                    last_response = attempt

                    if (
                        attempt.status_code == 404
                        or "text/html" in attempt.headers.get("Content-Type", "")
                    ):
                        # Try the next candidate URL if this one is clearly wrong.
                        continue

                    response = attempt
                    break

                if response is None:
                    if last_error:
                        raise last_error
                    if last_response is not None:
                        last_response.raise_for_status()
                    raise RuntimeError("Failed to contact Immich server.")

                response.raise_for_status()  # This will raise an exception for HTTP errors

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    if response.text:
                        data = response.json()
                        if isinstance(data, dict):
                            assets_payload = (
                                data.get("items")
                                or data.get("assets")
                                or data.get("data")
                                or []
                            )
                        else:
                            assets_payload = data

                        assets = (
                            assets_payload  # Decode JSON response into a list of assets
                        )
                        assets = [
                            asset for asset in assets if asset.get("type") == type
                        ]
                        st.session_state["fetch_message"] = (
                            "Assets fetched successfully!"
                        )
                    else:
                        st.session_state["fetch_message"] = (
                            "Received an empty response."
                        )
                        assets = []  # Set assets to empty list if response is empty
                else:
                    st.session_state["fetch_message"] = (
                        f"Unexpected Content-Type: {content_type}\nResponse content: {response.text}"
                    )
                    assets = []  # Set assets to empty list if unexpected content type

            # Ensure search loop did not break without setting success message.
            if not assets:
                if not st.session_state.get("fetch_message"):
                    st.session_state["fetch_message"] = (
                        "No assets found or failed to fetch assets."
                    )

    except requests.exceptions.ConnectTimeout:
        st.session_state["fetch_message"] = (
            "Failed to connect to the server. Please check your network connection and try again."
        )
        assets = []  # Set assets to empty list on connection timeout

    except requests.exceptions.HTTPError as e:
        st.session_state["fetch_message"] = f"HTTP error occurred: {e}"
        assets = []  # Set assets to empty list on HTTP error

    except requests.exceptions.RequestException as e:
        st.session_state["fetch_message"] = f"Error fetching assets: {e}"
        assets = []  # Set assets to empty list on other request errors

    message_placeholder.text(st.session_state["fetch_message"])
    return assets


def getImage(asset_id, immich_server_url, photo_choice, api_key):
    # Determine whether to fetch the original or thumbnail based on user selection
    register_heif_opener()
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    base_url = immich_server_url.rstrip("/")
    headers = {"Accept": "image/*", "x-api-key": api_key}

    if photo_choice == "Thumbnail (fast)":
        thumbnail_url = f"{base_url}/api/assets/{asset_id}/thumbnail"
        response = requests.get(
            thumbnail_url,
            headers=headers,
            params={"size": "thumbnail"},
        )
    else:
        original_url = f"{base_url}/api/assets/{asset_id}/original"
        response = requests.get(original_url, headers=headers, stream=True)

    if response.status_code == 200 and "image/" in response.headers.get(
        "Content-Type", ""
    ):
        image_bytes = BytesIO(response.content)
        try:
            image = Image.open(image_bytes)
            image.load()  # Force loading the image data while the file is open
            image_bytes.close()  # Now we can safely close the stream
            return image
        except UnidentifiedImageError:
            print(
                f"Failed to identify image for asset_id {asset_id}. Content-Type: {response.headers.get('Content-Type')}"
            )
            image_bytes.close()  # Ensure the stream is closed even if an error occurs
            return None
        finally:
            image_bytes.close()  # Ensure the stream is always closed
            del image_bytes
    else:
        print(
            f"Skipping non-image asset_id {asset_id} with Content-Type: {response.headers.get('Content-Type')}"
        )
        return None


def getAssetInfo(asset_id, assets):
    # Search for the asset in the provided list of assets.
    asset_info = next((asset for asset in assets if asset["id"] == asset_id), None)

    if asset_info:
        # Extract all required info.
        try:
            formatted_file_size = bytes_to_megabytes(
                asset_info["exifInfo"]["fileSizeInByte"]
            )
        except KeyError:
            formatted_file_size = "Unknown"

        original_file_name = asset_info.get("originalFileName", "Unknown")
        resolution = "{} x {}".format(
            asset_info.get("exifInfo", {}).get("exifImageHeight", "Unknown"),
            asset_info.get("exifInfo", {}).get("exifImageWidth", "Unknown"),
        )
        lens_model = asset_info.get("exifInfo", {}).get("lensModel", "Unknown")
        creation_date = asset_info.get("fileCreatedAt", "Unknown")
        original_path = asset_info.get("originalPath", "Unknown")
        is_offline = asset_info.get("isOffline", False)
        is_trashed = asset_info.get("isTrashed", False)  # Extract isTrashed
        is_favorite = asset_info.get("isFavorite", False)
        # Add more fields as needed and return them
        return (
            formatted_file_size,
            original_file_name,
            resolution,
            lens_model,
            creation_date,
            original_path,
            is_offline,
            is_trashed,
            is_favorite,
        )
    else:
        return None


def getServerStatistics(immich_server_url, api_key):
    base_url = immich_server_url.rstrip("/")
    try:
        response = requests.get(
            f"{base_url}/api/server/stats",
            headers={"Accept": "application/json", "x-api-key": api_key},
        )
        if response.ok:
            return (
                response.json()
            )  # This will parse the JSON response body and return it as a dictionary
        else:
            return None
    except Exception:
        return None


def deleteAsset(immich_server_url, asset_id, api_key):
    st.session_state["show_faiss_duplicate"] = False
    base_url = immich_server_url.rstrip("/")
    url = f"{base_url}/api/assets"
    payload = {"force": True, "ids": [asset_id]}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
    }

    try:
        response = requests.delete(url, headers=headers, json=payload)
        if response.status_code in (200, 204):
            st.success(f"Successfully deleted asset with ID: {asset_id}")
            print(f"Successfully deleted asset with ID: {asset_id}")
            return True
        else:
            # Provide more detailed error feedback
            error_message = response.json().get(
                "message", "No additional error message provided."
            )
            st.error(
                f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}"
            )
            print(
                f"Failed to delete asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}"
            )
            return False
    except requests.RequestException as e:
        # Handle request-related exceptions
        st.error(f"Request failed: {str(e)}")
        print(f"Request failed: {str(e)}")
        return False


def updateAsset(
    immich_server_url,
    asset_id,
    api_key,
    dateTimeOriginal,
    description,
    isFavorite,
    latitude,
    longitude,
    isArchived,
):
    base_url = immich_server_url.rstrip("/")
    url = f"{base_url}/api/assets/{asset_id}"

    payload = {
        "dateTimeOriginal": dateTimeOriginal,
        "description": description,
        "isArchived": isArchived,
        "isFavorite": isFavorite,
        "latitude": latitude,
        "longitude": longitude,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,  # Authorization via API key
    }

    try:
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            st.success(f"Successfully move on archive asset with ID: {asset_id}")
            print(
                f"Successfully move on archive asset with ID: {asset_id}. Response: {response_data}"
            )
            return True
        else:
            error_message = response.json().get(
                "message", "No additional error message provided."
            )
            st.error(
                f"Failed to move on archive asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}"
            )
            print(
                f"Failed to move on archive asset with ID: {asset_id}. Status code: {response.status_code}. Message: {error_message}"
            )
            return False
    except requests.RequestException as e:
        st.error(f"Request failed: {str(e)}")
        print(f"Request failed: {str(e)}")
        return False


# For video function
def getVideoAndSave(asset_id, immich_server_url, api_key, save_directory):
    # Ensure the directory exists
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    base_url = immich_server_url.rstrip("/")
    response = requests.get(
        f"{base_url}/api/assets/{asset_id}/original",
        headers={"Accept": "*/*", "x-api-key": api_key},
        stream=True,
    )
    file_path = os.path.join(save_directory, f"{asset_id}.mp4")

    if response.status_code == 200 and "video/" in response.headers.get(
        "Content-Type", ""
    ):
        try:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        except Exception as e:
            print(f"Failed to save video for asset_id {asset_id}. Error: {e}")
            return None
    else:
        print(
            f"Failed to retrieve video for asset_id {asset_id}. Status Code: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}"
        )
        return None
