from datetime import datetime
import streamlit as st
from datetime import datetime
from api import deleteAsset, updateAsset
from db import delete_duplicate_pair

def compare_and_color_data(value1, value2):
    date1 = datetime.fromisoformat(value1.rstrip('Z'))
    date2 = datetime.fromisoformat(value2.rstrip('Z'))
    
    # Compare the datetime objects
    if date1 > date2:  # value1 is newer
        return f"<span style='color: red;'>{value1}</span>"
    elif date1 < date2:  # value1 is older
        return f"<span style='color: green;'>{value1}</span>"
    else:  # They are the same
        return f"{value1}"

def compare_and_color(value1, value2):
    if value1 > value2:
        return f"<span style='color: green;'>{value1}</span>"
    elif value1 < value2:
        return f"<span style='color: red;'>{value1}</span>"
    else:
        return f"{value1}"

def display_asset_column(col, asset1_info, asset2_info, asset_id_1,asset_id_2, server_url, api_key):
    details = f"""
    - **File name:** {asset1_info[1]}
    - **Photo with ID:** {asset_id_1}
    - **Size:** {compare_and_color(asset1_info[0], asset2_info[0])}
    - **Resolution:** {compare_and_color(asset1_info[2], asset2_info[2])}
    - **Lens Model:** {asset1_info[3]}
    - **Created At:** {compare_and_color_data(asset1_info[4], asset2_info[4])}
    - **Is External:** {'Yes' if asset1_info[5] else 'No'}
    - **Is Offline:** {'Yes' if asset1_info[6] else 'No'}
    - **Is Read-Only:** {'Yes' if asset1_info[7] else 'No'}
    - **Is Trashed:** {'Yes' if asset1_info[8] else 'No'}
    - **Is Favorite:** {'Yes' if asset1_info[9] else 'No'}
    """
    with col:
        st.markdown(details, unsafe_allow_html=True)
        delete_button_key = f"delete-{asset_id_1}"
        delete_button_label = f"Delete {asset_id_1}"
        if st.button(delete_button_label, key=delete_button_key):
            try:
                if deleteAsset(server_url, asset_id_1, api_key):
                    st.success(f"Deleted photo {asset_id_1}")
                    st.session_state[f'deleted_photo_{asset_id_1}'] = True
                    st.session_state['show_faiss_duplicate'] = False
                    #remove from asset db
                    delete_duplicate_pair(asset_id_1,asset_id_2)
                else:
                    st.error(f"Failed to delete photo {asset_id_1}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                print(f"Failed to delete photo {asset_id_1}: {str(e)}")