import sqlite3, json
from collections import Counter

#############DATABASE###################

def startup_db_configurations():
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            immich_server_url text, 
            api_key text, 
            images_folder text, 
            timeout number
        )
    ''')
    conn.commit()
    conn.close()

def startup_processed_assets_db():
    conn = sqlite3.connect('processed_assets.db')  # Separate database for processed assets
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS processed_assets (
            asset_id TEXT PRIMARY KEY, 
            phash TEXT NOT NULL,
            asset_info TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_settings_from_db():
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM settings LIMIT 1")
    settings = c.fetchone()
    conn.close()
    return settings if settings else (None, None, None, None)

def save_settings_to_db(immich_server_url, api_key, images_folder, timeout):
    conn = sqlite3.connect('settings.db')
    c = conn.cursor()
    # This simple logic assumes one row of settings; adjust according to your needs
    c.execute("DELETE FROM settings")  # Clear existing settings
    c.execute("INSERT INTO settings VALUES (?, ?, ?, ?)", (immich_server_url, api_key, images_folder, timeout))
    conn.commit()
    conn.close()

def saveAssetInfoToDb(asset_id, phash, asset_info):
    conn = sqlite3.connect('processed_assets.db')
    c = conn.cursor()
    # Convert asset_info (a dict) to a string for storage; consider what info you need
    asset_info_str = json.dumps(asset_info)
    c.execute("INSERT OR REPLACE INTO processed_assets VALUES (?, ?, ?)",
              (asset_id, phash, asset_info_str))
    conn.commit()
    conn.close()

def isAssetProcessed(asset_id):
    conn = sqlite3.connect('processed_assets.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_assets WHERE asset_id = ?", (asset_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def bytes_to_megabytes(bytes_size):
    """Convert bytes to megabytes (MB) and format to 3 decimal places."""
    if bytes_size is None:
        return "0.001 MB"  # Assuming you want to return this default value for None input
    megabytes = bytes_size / (1024 * 1024)
    return f"{megabytes:.3f} MB"

def countProcessedAssets():
    conn = sqlite3.connect('processed_assets.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM processed_assets")
    count = c.fetchone()[0]
    conn.close()
    return count

def getHashFromDb(asset_id):
    conn = sqlite3.connect('processed_assets.db')
    c = conn.cursor()
    c.execute("SELECT phash FROM processed_assets WHERE asset_id = ?", (asset_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        return None
    
def countDuplicates():
    conn = sqlite3.connect('processed_assets.db')
    c = conn.cursor()
    # Fetch all hashes from the database
    c.execute("SELECT phash FROM processed_assets")
    hashes = c.fetchall()
    conn.close()
    # Flatten the list of tuples to a list of strings
    hash_list = [item[0] for item in hashes]
    # Use Counter to count occurrences of each hash
    hash_counts = Counter(hash_list)
    # Filter out hashes that appear only once (no duplicates)
    duplicates = {hash_: count for hash_, count in hash_counts.items() if count > 1}
    return duplicates