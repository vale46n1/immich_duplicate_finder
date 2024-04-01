import torch
import numpy as np
import faiss
import os
from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights
from torchvision.transforms import Compose, Resize, ToTensor, Normalize
import streamlit as st

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Initialize the model for feature extraction Euclidean distance
model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
model.eval()  # Set model to evaluation mode
transform = Compose([
    Resize((224, 224)),
    ToTensor(),
    Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# Global variables for paths
index_path = 'faiss_index.bin'
metadata_path = 'metadata.npy'

def extract_features(image):
    """Extract features from an image."""
    image_tensor = transform(image).unsqueeze(0)  # Add batch dimension
    with torch.no_grad():
        features = model(image_tensor)
    return features.numpy().flatten()

# This function is adjusted to ensure that the FAISS index is always correctly initialized
def init_or_load_faiss_index():
    """Initialize or load the FAISS index and metadata."""
    if os.path.exists(index_path) and os.path.exists(metadata_path):
        # Load the index
        index = faiss.read_index(index_path)
        # Load metadata
        metadata = np.load(metadata_path, allow_pickle=True).tolist()
    else:
        # If the index and metadata do not exist, initialize them after extracting features from the first image
        # to determine the correct dimension. This part is handled in the update_faiss_index function.
        index = None  # Placeholder, will be initialized later
        metadata = []
    return index, metadata

def save_faiss_index_and_metadata(index, metadata):
    """Save the FAISS index and metadata to disk."""
    faiss.write_index(index, index_path)
    np.save(metadata_path, np.array(metadata, dtype=object))

def update_faiss_index(image, asset_id):
    """Update the FAISS index and metadata with a new image and its ID, 
    skipping if the asset_id has already been processed."""
    global index  # Assuming index is defined globally
    index, existing_metadata = init_or_load_faiss_index()
    
    # Check if the asset_id is already in metadata to decide whether to skip processing
    if asset_id in existing_metadata:
        return 'skipped'  # Skip processing this image

    features = extract_features(image)
    
    if index is None:
        # Initialize the FAISS index with the correct dimension if it's the first time
        dimension = features.shape[0]
        index = faiss.IndexFlatL2(dimension)
    
    index.add(np.array([features], dtype='float32'))
    existing_metadata.append(asset_id)
    
    save_faiss_index_and_metadata(index, existing_metadata)
    return 'processed'

################################SEARCH########################################
def load_index_and_metadata(index_path, metadata_path):
    if not os.path.exists(index_path) or not os.path.exists(metadata_path):
        print("Index or metadata file does not exist.")
        return None, []
    
    index = faiss.read_index(index_path)
    metadata = np.load(metadata_path, allow_pickle=True).tolist()
    return index, metadata

def find_faiss_duplicates(index, metadata, threshold):
    num_vectors = index.ntotal
    duplicate_pairs = set()

    # Initialize a placeholder for progress messages
    message_placeholder = st.empty()
    # Initialize the progress bar
    progress_bar = st.progress(0)

    for i in range(num_vectors):
        # Update the message placeholder and progress bar
        progress = int((i + 1) / num_vectors * 100)
        message_placeholder.text(f"Finding duplicate: processing vector {i+1} of {num_vectors}")
        progress_bar.progress(progress / 100)

        # Reconstruct the i-th vector from the index
        query_vector = np.array([index.reconstruct(i)])
        
        # Query this vector against the index
        distances, indices = index.search(query_vector, 2)  # Searching for top 2 to include the vector itself
        
        # Check distances to find duplicates
        for j in range(1, indices.shape[1]):  # Start from 1 to skip the vector itself
            if distances[0][j] < threshold:
                idx1, idx2 = i, indices[0][j]
                if idx1 != idx2:  # Ensure we're not comparing the vector to itself
                    pair = (min(idx1, idx2), max(idx1, idx2))
                    duplicate_pairs.add(pair)

    # Update the message to indicate completion
    message_placeholder.text(f"Finished processing {num_vectors} vectors.")
    progress_bar.empty() 

    # Convert index pairs to asset_id pairs
    duplicate_asset_ids = [(metadata[pair[0]], metadata[pair[1]]) for pair in duplicate_pairs if pair[0] != pair[1]]
    
    return duplicate_asset_ids

##############TEST
def process_images_and_find_duplicates():
    # Initialize or load the FAISS index and metadata
    index, metadata = init_or_load_faiss_index()

    # List of images to process
    image_files = ['D:\PROGETTI_VARI\Immich\Temp\image1.jpg', 'D:\PROGETTI_VARI\Immich\Temp\image2.jpg']
    asset_ids = ['image1', 'image2']  # Example asset IDs, typically these would be unique identifiers

    # Process each image
    for image_file, asset_id in zip(image_files, asset_ids):
        image = Image.open(image_file)
        status = update_faiss_index(image, asset_id)
        print(f"Processing {asset_id}: {status}")

    # Save the updated index and metadata
    save_faiss_index_and_metadata(index, metadata)

    # Attempt to find duplicates within the processed images
    threshold = 0.6  # Define a similarity threshold for considering images as duplicates
    duplicates = find_faiss_duplicates(index, metadata, threshold)
    print("Duplicate pairs found:")
    for dup_pair in duplicates:
        print(dup_pair)

# Ensure this is the main entry point to avoid running unintentionally
if __name__ == "__main__":
    process_images_and_find_duplicates()