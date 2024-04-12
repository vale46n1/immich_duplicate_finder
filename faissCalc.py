import torch
import numpy as np
import faiss
import os
from PIL import Image
#from torchvision.models import resnet18, ResNet18_Weights,resnet50, ResNet50_Weights, 
from torchvision.models import resnet152, ResNet152_Weights
from torchvision.transforms import Compose, Resize, ToTensor, Normalize
import streamlit as st
import multiprocessing
from multiprocessing import Pool

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Initialize the model for feature extraction Euclidean distance
#model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
#model.eval()  # Set model to evaluation mode
#transform = Compose([Resize((224, 224)),ToTensor(),Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),])

#model = resnet50(weights=ResNet50_Weights.DEFAULT)
#model.eval()  # Set model to evaluation mode
#transform = Compose([Resize((448, 448)), ToTensor(),Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),])

# Load ResNet152 with pretrained weights
model = resnet152(weights=ResNet152_Weights.DEFAULT)
model.eval()  # Set model to evaluation mode
transform = Compose([
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

def find_faiss_duplicates(index, metadata, threshold):
    """Find duplicates in the index based on the specified similarity threshold."""
    num_vectors = index.ntotal
    duplicate_pairs = set()

    message_placeholder = st.empty()
    progress_bar = st.progress(0)
    
    for i in range(num_vectors):
        # Check if stop has been requested
        if st.session_state['stop_requested']:
            message_placeholder.text("Processing was stopped by the user.")
            progress_bar.empty()
            st.session_state['stop_requested'] = False  # Reset the flag for future operations
            return None  # Or an appropriate response indicating stopping

        progress = int((i + 1) / num_vectors * 100)
        message_placeholder.text(f"Finding duplicate with threshold {threshold}: processing vector {i+1} of {num_vectors}")
        progress_bar.progress(progress / 100)

        query_vector = np.array([index.reconstruct(i)])
        distances, indices = index.search(query_vector, 2)  # Searching for top 2 to include the vector itself

        for j in range(1, indices.shape[1]):  # Ignore the first match as it's the vector itself
            if distances[0][j] < threshold:
                idx1, idx2 = i, indices[0][j]
                if idx1 != idx2:
                    duplicate_pairs.add((min(idx1, idx2), max(idx1, idx2)))

    message_placeholder.text(f"Finished processing {num_vectors} vectors.")
    progress_bar.empty()

    return [(metadata[pair[0]], metadata[pair[1]]) for pair in duplicate_pairs]