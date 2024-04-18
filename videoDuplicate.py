import streamlit as st
import time
import os
import torch
import numpy as np
import faiss
from torchvision.models import resnet152, ResNet152_Weights
from torchvision.transforms import Compose, Resize, ToTensor, Normalize

from api import getVideo

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
index_path = 'video_faiss_index.bin'
metadata_path = 'video_metadata.npy'