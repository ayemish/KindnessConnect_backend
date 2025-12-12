# app/config.py 

import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv


load_dotenv() 


CRED_PATH = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_PATH")

def initialize_firebase():
    """Initializes the Firebase Admin SDK based on environment variables."""
    # Check 1: Ensure the path environment variable is set
    if not CRED_PATH:
        print(" [WARNING] Firebase initialization skipped: FIREBASE_ADMIN_CREDENTIALS_PATH environment variable not set.")
        # We raise an exception here because the database is critical to the app's functionality.
        raise ValueError("FIREBASE_ADMIN_CREDENTIALS_PATH environment variable not set.")

    # Check 2: Ensure the file exists at the specified path
    if not os.path.exists(CRED_PATH):
        raise FileNotFoundError(f" [ERROR] Could not find the Firebase Service Account key at path: {CRED_PATH}. Check your .env file.")

    # Check 3: Check if Firebase is already initialized
    if not firebase_admin._apps:
        try:
            # Load the certificate from the file path
            cred = credentials.Certificate(CRED_PATH) 
            firebase_admin.initialize_app(cred)
            print(" [INFO] Firebase initialized successfully!")
        except Exception as e:
            # Catches errors like invalid JSON format (JSONDecodeError)
            raise RuntimeError(f" [FATAL] Firebase initialization failed. Check JSON file format: {e}") from e

# Initialize immediately when this module is imported
# This ensures Firebase is ready before any other part of the app tries to access it.
initialize_firebase()


db = firestore.client()