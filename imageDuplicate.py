import os
import streamlit as st
import time

import torch
import numpy as np
import faiss
from torchvision.models import resnet152, ResNet152_Weights
from torchvision.transforms import Compose, Resize, ToTensor, Normalize

from api import getImage
from utility import display_asset_column
from api import getAssetInfo
from db import load_duplicate_pairs, is_db_populated, save_duplicate_pair
from streamlit_image_comparison import image_comparison

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Load ResNet152 with pretrained weights
model = resnet152(weights=ResNet152_Weights.DEFAULT)
model.eval()  # Set model to evaluation mode


def convert_image_to_rgb(image):
    """Convert image to RGB if it's RGBA."""
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image


transform = Compose([
    convert_image_to_rgb,
    Resize((224, 224)),  # Standard size for ImageNet-trained models
    ToTensor(),
    Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Global variables for paths
index_path = 'faiss_index.bin'
metadata_path = 'metadata.npy'

def extract_features(image):
    """Extract features from an image using a pretrained model."""
    image_tensor = transform(image).unsqueeze(0)  # Add batch dimension
    with torch.no_grad():
        features = model(image_tensor)
    return features.numpy().flatten()

def init_or_load_faiss_index():
    """Initialize or load the FAISS index and metadata, ensuring index is ready for use."""
    if os.path.exists(index_path) and os.path.exists(metadata_path):
        index = faiss.read_index(index_path)
        metadata = np.load(metadata_path, allow_pickle=True).tolist()
    else:
        index = None
        metadata = []
    return index, metadata

def save_faiss_index_and_metadata(index, metadata):
    """Save the FAISS index and metadata to disk."""
    faiss.write_index(index, index_path)
    np.save(metadata_path, np.array(metadata, dtype=object))

def update_faiss_index(immich_server_url,api_key, asset_id):
    
    """Update the FAISS index and metadata with a new image and its ID, 
    skipping if the asset_id has already been processed."""
    global index  # Assuming index is defined globally
    index, existing_metadata = init_or_load_faiss_index()
    
    # Check if the asset_id is already in metadata to decide whether to skip processing
    if asset_id in existing_metadata:
        return 'skipped'  # Skip processing this image

    image = getImage(asset_id, immich_server_url, "Thumbnail (fast)", api_key)
    if image is not None:
        features = extract_features(image)
    else:
        return 'error'
    
    if index is None:
        # Initialize the FAISS index with the correct dimension if it's the first time
        dimension = features.shape[0]
        index = faiss.IndexFlatL2(dimension)
    
    index.add(np.array([features], dtype='float32'))
    existing_metadata.append(asset_id)
    
    save_faiss_index_and_metadata(index, existing_metadata)
    return 'processed'

def calculateFaissIndex(assets, immich_server_url, api_key):
    # Initialize session state variables if they are not already set
    if 'message' not in st.session_state:
        st.session_state['message'] = ""
    if 'progress' not in st.session_state:
        st.session_state['progress'] = 0
    if 'stop_index' not in st.session_state:
        st.session_state['stop_index'] = False

    # Set up the UI components
    progress_bar = st.progress(st.session_state['progress'])
    stop_button = st.button('Stop Index Processing')
    message_placeholder = st.empty()

    # Check if stop was requested and reset it if button is pressed
    if stop_button:
        st.session_state['stop_index'] = True
        st.session_state['calculate_faiss'] = False

    total_assets = len(assets)
    processed_assets = 0
    skipped_assets = 0
    error_assets = 0
    total_time = 0

    for i, asset in enumerate(assets):
        if st.session_state['stop_index']:
            st.session_state['message'] = "Processing stopped by user."
            message_placeholder.text(st.session_state['message'])
            break  # Break the loop if stop is requested

        asset_id = asset.get('id')
        start_time = time.time()

        status = update_faiss_index(immich_server_url,api_key, asset_id)
        if status == 'processed':
            processed_assets += 1
        elif status == 'skipped':
            skipped_assets += 1
        elif status == 'error':
            error_assets += 1

        end_time = time.time()
        processing_time = end_time - start_time
        total_time += processing_time

        # Update progress and messages
        progress_percentage = (i + 1) / total_assets
        st.session_state['progress'] = progress_percentage
        progress_bar.progress(progress_percentage)
        estimated_time_remaining = (total_time / (i + 1)) * (total_assets - (i + 1))
        estimated_time_remaining_min = int(estimated_time_remaining / 60)

        st.session_state['message'] = f"Processing asset {i + 1}/{total_assets} - (Processed: {processed_assets}, Skipped: {skipped_assets}, Errors: {error_assets}). Estimated time remaining: {estimated_time_remaining_min} minutes."
        message_placeholder.text(st.session_state['message'])

    # Reset stop flag at the end of processing
    st.session_state['stop_index'] = False
    if processed_assets >= total_assets:
        st.session_state['message'] = "Processing complete!"
        message_placeholder.text(st.session_state['message'])
        progress_bar.progress(1.0)

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
                # Check if the indices in sorted_pair are within the bounds of metadata
                if sorted_pair[0] < len(metadata) and sorted_pair[1] < len(metadata):
                    save_duplicate_pair(metadata[sorted_pair[0]], metadata[sorted_pair[1]], distances[0][j])
                else:
                    st.error(f"Metadata index out of range: {sorted_pair}")
                    # Optionally log more details or handle this case further

    message_placeholder.text(f"Finished processing {num_vectors} vectors.")
    progress_bar.empty()

def show_duplicate_photos_faiss(assets, limit, min_threshold, max_threshold,immich_server_url,api_key):
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
            try:
                # Check if stop was requested
                if st.session_state.get('stop_requested', False):
                    st.write("Processing was stopped by the user.")
                    st.session_state['stop_requested'] = False  # Reset the flag for future operations
                    st.session_state['generate_db_duplicate'] = False
                    break  # Exit the loop

                progress = (i + 1) / num_duplicates_to_show
                progress_bar.progress(progress)

                asset_id_1, asset_id_2 = dup_pair

                image1 = getImage(asset_id_1, immich_server_url, 'Thumbnail (fast)', api_key)
                image2 = getImage(asset_id_2, immich_server_url, 'Thumbnail (fast)', api_key)
                asset1_info = getAssetInfo(asset_id_1, assets)
                asset2_info = getAssetInfo(asset_id_2, assets)

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
                        in_memory=False,
                    )

                    col1, col2 = st.columns(2)
                #    with col1:
                #        st.image(image1, caption=f"Name: {asset_id_1}")
                #    with col2:
                #        st.image(image2, caption=f"Name: {asset_id_2}")
                    
                    display_asset_column(col1, asset1_info, asset2_info, asset_id_1,asset_id_2, immich_server_url, api_key)
                    display_asset_column(col2, asset2_info, asset1_info, asset_id_2,asset_id_1, immich_server_url, api_key)
                else:
                    st.write(f"Missing information for one or both assets: {asset_id_1}, {asset_id_2}")

                st.markdown("---")
            except:
                st.write(f"Missing information for one or both assets")
        progress_bar.progress(100)
    else:
        st.write("No duplicates found.")

