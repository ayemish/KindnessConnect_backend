from fastapi import Header, HTTPException, Depends
from firebase_admin import auth

# This function verifies the "Bearer Token" sent by the frontend
async def get_current_user_uid(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authentication header")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        # Verify the ID token with Firebase
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        return uid
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")