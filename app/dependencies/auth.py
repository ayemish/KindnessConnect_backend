# app/dependencies/auth.py

from fastapi import Header, HTTPException, Depends, status
from firebase_admin import auth as firebase_auth, initialize_app

# Ensure Firebase Admin is initialized once, typically in app/config.py or app/main.py
# (If it's initialized elsewhere, omit this part)

def verify_firebase_token(authorization: str = Header(...)):
    """Verifies the Firebase ID Token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    
    try:
        # Verify the token using Firebase Admin SDK.
        # This confirms the token is valid, unexpired, and issued by Firebase.
        decoded_token = firebase_auth.verify_id_token(token)
        
        # The UID is the unique, verified identifier for the user.
        return decoded_token['uid'] 
        
    except Exception as e:
        # Catch exceptions like invalid signature, expired token, or network errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )