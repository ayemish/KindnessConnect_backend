# app/routers/verification.py (Cleaned and Completed)

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status 
from app.config import db
# NOTE: upload_image is commented out as you are testing without files
# from app.services.storage import upload_image 
from app.models.schemas import (
    VerificationDealResponse, 
    VerificationRequestResponse, 
    VerificationRequestUpdate
)
from datetime import datetime
import uuid
from typing import List, Optional

router = APIRouter(prefix="/verification", tags=["Verification"])

# Mock Deals (Defined globally for use in AdminVerification.jsx too)
MOCK_DEALS = [
    {"id": "badge-1", "name": "1 Year Standard Badge", "cost_usd": 25.00, "duration_days": 365},
    {"id": "badge-2", "name": "Lifetime Badge", "cost_usd": 150.00, "duration_days": 9999},
]

# --- DEPENDENCY: Admin Check ---
def get_admin(admin_uid: str):
    """Dependency to validate admin privileges."""
    admin_ref = db.collection("users").document(admin_uid).get()
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    return admin_uid
# ------------------------------

# 1. Get Verification Deals
@router.get("/deals", response_model=List[VerificationDealResponse])
def get_verification_deals():
    """Returns the list of available verification badge tiers."""
    return MOCK_DEALS

# 2. Submit New Verification Request (Temporary: NO file upload)
@router.post("/", response_model=VerificationRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_verification_request(
    requester_uid: str = Form(...),
    deal_id: str = Form(...),
    # proof_description: str = Form(...), # Removed for simplified test
    # proof_document: UploadFile = File(...) # Removed for simplified test
):
    try:
        # document_url = await upload_image(proof_document) # Removed for simplified test
        document_url = "N/A - File Upload Skipped for Testing" # Placeholder
        proof_description = "N/A - Description Skipped for Testing" # Placeholder
        
        # 2. Fetch User Name for contextual display
        user_doc = db.collection("users").document(requester_uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requester user not found.")
            
        user_name = user_doc.to_dict().get("full_name", "Unknown User")
        
        # 3. Prepare Data
        request_id = str(uuid.uuid4())
        new_request = {
            "id": request_id,
            "requester_uid": requester_uid,
            "user_name": user_name,
            "deal_id": deal_id,
            "proof_description": proof_description,
            "proof_document_url": document_url,
            "status": "pending",
            "created_at": datetime.utcnow()
        }
        
        # 4. Save to Firestore
        db.collection("verification_requests").document(request_id).set(new_request)
        
        return new_request

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Verification request submission failed: {str(e)}")

# 3. Get All Verification Requests (Admin Only) (No changes needed)
@router.get("/", response_model=List[VerificationRequestResponse])
def get_all_verification_requests(admin_uid: str = Depends(get_admin)):
    """Retrieves all verification requests (Admin only)."""
    
    try:
        docs = db.collection("verification_requests").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 4. Update Verification Request Status (Admin Only)
@router.put("/{request_id}", response_model=VerificationRequestResponse)
def update_verification_status(
    request_id: str, 
    update: VerificationRequestUpdate, 
    admin_uid: str = Depends(get_admin)
):
    """Admin approves or rejects a verification request."""
        
    request_ref = db.collection("verification_requests").document(request_id)
    if not request_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification request not found.")

    update_data = update.dict(exclude_none=True)
    
    if not update_data:
        return request_ref.get().to_dict()

    # CRITICAL: If status is 'approved', update the main user record's is_verified flag
    if update_data.get("status") == "approved":
        current_request = request_ref.get().to_dict()
        user_uid = current_request.get("requester_uid")
        
        # FINAL FIX: Update user's global verification status in the 'users' collection
        db.collection("users").document(user_uid).update({"is_verified": True})
        
    elif update_data.get("status") == "rejected":
        # Optionally handle badge revocation here
        pass

    try:
        request_ref.update(update_data)
        return request_ref.get().to_dict()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update request status: {str(e)}")