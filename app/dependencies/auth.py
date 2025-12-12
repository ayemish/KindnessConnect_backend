# app/dependencies/auth.py

from fastapi import Header, HTTPException, Depends, status
from firebase_admin import auth as firebase_auth


# This is the primary dependency used by endpoints like /users/profile
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
        
        # This is the call that is failing.
        decoded_token = firebase_auth.verify_id_token(token)
        
        return decoded_token['uid'] 
        
    except Exception as e:
        
        print(f"!!! FIREBASE TOKEN VERIFICATION FAILED: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

