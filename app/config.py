# app/config.py (Cleaned and Securely Configured)

import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv # Import to load the .env file

# Load variables from .env file (assuming you use a .env file)
load_dotenv() 

# 1. Retrieve the path from the environment variable set in your .env file
# We are now looking for a variable that holds the PATH to the file.
CRED_PATH = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_PATH")

def initialize_firebase():
    # Check 1: Ensure the path environment variable is set
    if not CRED_PATH:
        print("⚠️ Firebase initialization skipped: FIREBASE_ADMIN_CREDENTIALS_PATH environment variable not set.")
        return

    # Check 2: Ensure the file exists at the specified path
    if not os.path.exists(CRED_PATH):
        raise FileNotFoundError(f"Could not find the Firebase Service Account key at path: {CRED_PATH}. Check your .env file.")

    # Check 3: Check if Firebase is already initialized
    if not firebase_admin._apps:
        # Load the certificate from the file path
        cred = credentials.Certificate(CRED_PATH) 
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully!")

# Initialize immediately when this module is imported
initialize_firebase()

# Create the Firestore client
db = firestore.client()