import streamlit as st
import time
from imagehash import phash
from db import saveAssetInfoToDb, isAssetProcessed
from immichApi import streamAsset
import gc 

def calculatepHashPhotos(assets, immich_server_url, api_key):
    if 'message' not in st.session_state or st.button('Start Processing'):
        st.session_state['message'] = ""
    if 'progress' not in st.session_state:
        st.session_state['progress'] = 0

    
    progress_bar = st.progress(st.session_state['progress'])
    stop_button = st.button('Stop Processing')
    message_placeholder = st.empty()

    total_assets = len(assets)
    processed_assets = 0
    skipped_assets = 0
    error_assets = 0
    total_time = 0

    for i, asset in enumerate(assets):
        
        if stop_button:
            st.session_state['message'] += "Processing stopped by user.\n"
            message_placeholder.text(st.session_state['message'])
            break

        asset_id = asset.get('id')
        start_time = time.time()

        if not isAssetProcessed(asset_id):
            image = streamAsset(asset_id, immich_server_url, "Original Photo (slow)", api_key)
            image_phash=''
            if image is not None:
                image_phash = phash(image)
                saveAssetInfoToDb(asset_id, str(image_phash), asset)
                processed_assets += 1
                st.session_state['message'] += f"Processed and saved asset {asset_id}\n"
                
                # Explicitly delete the image object and free memory
                del image
                gc.collect()
            else:
                st.session_state['message'] += f"Failed to fetch image for asset {asset_id}\n"
                error_assets += 1
        else:
            st.session_state['message'] += f"Asset {asset_id} has already been processed. Skipping.\n"
            skipped_assets += 1

        end_time = time.time()
        processing_time = end_time - start_time
        total_time += processing_time

        # Calculate the average processing time per asset
        average_time_per_asset = total_time / processed_assets if processed_assets > 0 else 0
        estimated_time_remaining = average_time_per_asset * (total_assets - processed_assets)
        estimated_time_remaining_min = int(estimated_time_remaining/60)

        # Update the UI
        progress_percentage = (i + 1) / total_assets
        st.session_state['progress'] = progress_percentage
        progress_bar.progress(progress_percentage)

        st.session_state['message'] += f"Estimated time remaining: {estimated_time_remaining_min} minutes\n"
        st.session_state['message'] += f"Asset {i + 1} / {total_assets} - (processed {processed_assets} - skipped {skipped_assets} - error {error_assets})\n"
        message_placeholder.text(st.session_state['message'])  # Update the placeholder with the new message
        st.session_state['message']=''

    if processed_assets >= total_assets:
        st.session_state['message'] += "Processing complete!"
        message_placeholder.text(st.session_state['message'])
        progress_bar.progress(1.0)

