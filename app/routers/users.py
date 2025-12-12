from fastapi import APIRouter, HTTPException, Depends, status
from app.config import db
from app.models.schemas import UserCreate, UserResponse
from datetime import datetime
from typing import Optional, List
from app.dependencies.auth import verify_firebase_token 
from firebase_admin import auth as firebase_auth

router = APIRouter(prefix="/users", tags=["Users"])


def get_admin(admin_uid: str):
    admin_ref = db.collection("users").document(admin_uid).get()
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges: Admin access required")
    return admin_uid


# --- ENDPOINT 1: Get All Users (Admin Only) ---
@router.get("/", response_model=List[UserResponse])
def get_all_users(admin_uid: str = Depends(get_admin)): 
    """
    Retrieves a list of all registered users for administrative oversight.
    """
    try:
        
        
        # 2. Fetch all users
        docs = db.collection("users").stream()
        
        users_list = []
        for doc in docs:
            user_data = doc.to_dict()
            
           
            user_data['uid'] = doc.id 
            
          
            # This prevents 422 errors on old or incomplete documents.
            user_data['is_verified'] = user_data.get('is_verified', False)
            user_data['is_active'] = user_data.get('is_active', True)
            user_data['role'] = user_data.get('role', 'user') 
            
           
            # Pydantic is usually good with Firestore Timestamps, but adding a fallback helps.
            user_data['created_at'] = user_data.get('created_at', datetime.utcnow())

            users_list.append(user_data) 
            
        return users_list
        
    except Exception as e:
        print(f"Detailed Server Error (GET /users/): {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving users: {str(e)}")
    
    
    
    
# --- ENDPOINT 2: Register/Create User Profile (Used post-Firebase Signup) ---
@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user_profile(user: UserCreate):
   
    try:
        user_ref = db.collection("users").document(user.uid)
        
        # Check if the user document already exists (safety check, should not happen post-signup)
        doc = user_ref.get()
        if doc.exists:
            return doc.to_dict()
        
        # Prepare new user data dictionary
        user_data = user.model_dump() # Use model_dump() for Pydantic v2
        user_data["created_at"] = datetime.utcnow()
        user_data["is_active"] = True
        user_data["is_verified"] = False
        
        # Persist to Firestore
        user_ref.set(user_data)
        
        return user_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")




# --- ENDPOINT 3: Get User Profile  ---
@router.get("/profile", response_model=UserResponse)
def get_user_profile(uid: str = Depends(verify_firebase_token)):
    """
    Retrieves the authenticated user's profile information using the UID from the Bearer token.
    (This replaces the old /me endpoint)
    """
    try:
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if not doc.exists:
            # If token is valid but DB record is missing, return 404
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found in database")
            
        user_data = doc.to_dict()
        # Add UID back into the dictionary for the Pydantic model
        user_data['uid'] = uid 
        
        return user_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- ENDPOINT 4: Verify User Account (Admin Only) ---
@router.put("/{uid}/verify", response_model=UserResponse)
def verify_user_account(uid: str, admin_uid: str = Depends(verify_firebase_token)):
    """
    Administrative endpoint to verify a user account.
    Validates that the requestor (admin_uid) has 'admin' privileges.
    """
    try:
        # 1. Validate Admin Privileges
        admin_ref = db.collection("users").document(admin_uid).get()
        if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges: Admin access required")

        # 2. Perform Verification
        user_ref = db.collection("users").document(uid)
        if not user_ref.get().exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
            
        user_ref.update({"is_verified": True})
        
        # 3. Retrieve and return the updated user object
        updated_user_data = user_ref.get().to_dict()
        updated_user_data['uid'] = uid
        
        return updated_user_data
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))       
    
    
    # --- ENDPOINT 5: Delete User Account (Admin Only) ---
@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_account(uid: str, admin_uid: str = Depends(verify_firebase_token)):
    """
    Administrative endpoint to delete a user account from both Firestore and Firebase Auth.
    """
    try:
        # 1. Validate Admin Privileges (using the same check as verify)
        admin_ref = db.collection("users").document(admin_uid).get()
        if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges: Admin access required")

        # 2. Delete the user from Firestore (Profile Metadata)
        user_ref = db.collection("users").document(uid)
        if not user_ref.get().exists:
            # If the user is missing in Firestore, proceed to delete from Auth
            pass 
        else:
            user_ref.delete()

        # 3. Delete the user from Firebase Authentication (Email/Password credentials)
        try:
            firebase_auth.delete_user(uid)
        except Exception as e:
            # Catch error if user doesn't exist in Firebase Auth but existed in Firestore
            print(f"User {uid} not found in Firebase Auth: {e}")

        # 4. Return 204 No Content on success
        return 

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"User deletion failed: {str(e)}")