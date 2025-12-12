# app/config.py

import os
import firebase_admin
from firebase_admin import credentials, firestore
import json # Import the json library to handle the credential string

# Initialize Firestore placeholder globally
db = None

def initialize_firebase():
    """
    Initializes Firebase Admin SDK using a dual approach:
    1. Secure Environment Variable (for Render/Deployment)
    2. Local File Path (for local development)
    """
    global db
    
    # --- Check 1: Try reading from the secure Environment Variable (DEPLOYMENT PATH) ---
    # Render, Vercel, etc., will have this set.
    admin_json_string = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    
    if admin_json_string:
        print("[INFO] Initializing Firebase from Environment Variable...")
        try:
            # 1. Load the JSON string into a Python dictionary
            cred_dict = json.loads(admin_json_string)
            
            # 2. Use the dictionary directly to create credentials
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            print("[INFO] Firebase initialized successfully!")
            return
            
        except Exception as e:
            # If JSON parsing or initialization fails
            print(f"[FATAL ERROR] Failed to initialize Firebase from environment variable: {e}")
            raise RuntimeError("Firebase initialization failed from environment.")


    # --- Check 2: Fallback for local development (LOCAL PATH) ---
    # This path uses your local .env file and the secrets/firebase-adminsdk.json file.
    CRED_PATH = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_PATH")
    
    if CRED_PATH and os.path.exists(CRED_PATH):
        print(f"[INFO] Initializing Firebase from local file: {CRED_PATH}")
        try:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("[INFO] Firebase initialized successfully from local file!")
            return
        except Exception as e:
            print(f"[FATAL ERROR] Failed to initialize Firebase from local file: {e}")
            raise RuntimeError("Firebase initialization failed from local file.")

    # If neither path works
    print("[FATAL ERROR] Firebase credentials missing for both deployment and local paths.")
    raise RuntimeError("Cannot start application without Firebase credentials.")

# Call initialization on import (this happens when FastAPI starts)
initialize_firebase()