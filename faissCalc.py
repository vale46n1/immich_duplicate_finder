import torch
import numpy as np
import faiss
import os
from torchvision.models import resnet152, ResNet152_Weights
from torchvision.transforms import Compose, Resize, ToTensor, Normalize
from immichApi import streamAsset

# Set the environment variable to allow multiple OpenMP libraries
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

def update_faiss_index(immich_server_url,api_key, asset_id):
    
    """Update the FAISS index and metadata with a new image and its ID, 
    skipping if the asset_id has already been processed."""
    global index  # Assuming index is defined globally
    index, existing_metadata = init_or_load_faiss_index()
    
    # Check if the asset_id is already in metadata to decide whether to skip processing
    if asset_id in existing_metadata:
        return 'skipped'  # Skip processing this image

    image = streamAsset(asset_id, immich_server_url, "Thumbnail (fast)", api_key)
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
