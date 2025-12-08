# sponsors.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from app.config import db
from app.services.storage import upload_image 
from app.models.schemas import (
    SponsorDealResponse, SponsorDealBase, 
    SponsorCreate, SponsorResponse, 
    SponsorUpdate
)
from datetime import datetime
import uuid
from typing import List, Optional
from firebase_admin import firestore 
from app.services.color_extraction import get_dominant_rgb_from_image, get_palette_from_colors 
import io 

router = APIRouter(prefix="/sponsors", tags=["Sponsors"])

# --- 1. SPONSOR DEALS (Fixed, can be pre-loaded in DB) ---

# Mock list of deals (In a real app, this would be loaded from Firestore)
MOCK_DEALS = [
    {"id": "deal-1", "name": "1 Week Standard", "duration_days": 7, "price_usd": 100.00},
    {"id": "deal-2", "name": "2 Week Premium", "duration_days": 14, "price_usd": 180.00},
    {"id": "deal-3", "name": "1 Month Platinum", "duration_days": 30, "price_usd": 350.00},
]

@router.get("/deals", response_model=List[SponsorDealResponse])
def get_sponsor_deals():
    """Returns the list of available sponsorship tiers."""
    return MOCK_DEALS

# ---  Generate colors from an uploaded logo ---

@router.post("/generate_theme", tags=["Sponsors"])
async def generate_theme_from_logo(logo_file: UploadFile = File(...)):
    """
    Receives a logo image, extracts dominant colors, and generates a 
    recommended primary/background HEX color theme via Colormind API.
    """
    # 1. Read file content into bytes
    try:
        # NOTE: .read() consumes the file, so it cannot be read again later.
        file_bytes = await logo_file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the uploaded logo file.")
    
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Logo file is empty.")

    # 2. Extract dominant RGB colors from the image
    dominant_rgbs = get_dominant_rgb_from_image(file_bytes)
    
    if not dominant_rgbs:
        # This occurs if the Pillow processing fails (e.g., corrupted file)
        raise HTTPException(status_code=500, detail="Failed to extract dominant colors from image. Please ensure the file is a valid image.")

    # 3. Use dominant RGBs to generate a harmonious theme palette
    # The service calls Colormind and selects the best primary and light background colors
    primary_hex, light_bg_hex = get_palette_from_colors(dominant_rgbs)

    return {
        "primary_color_hex": primary_hex,
        "light_bg_hex": light_bg_hex
    }


# --- 2. SPONSOR CREATION ---

@router.post("/", response_model=SponsorResponse)
async def create_sponsor_request(
    sponsor_name: str = Form(...),
    contact_email: str = Form(...),
    deal_id: str = Form(...),
    primary_color_hex: str = Form(...),
    light_bg_hex: str = Form(...),
    website_url: Optional[str] = Form(None),
    logo_file: UploadFile = File(...)
):
    """Submits a new sponsorship request with logo upload."""
    try:
        # 1. Upload Logo Image
        logo_url = await upload_image(logo_file)
        
        # 2. Prepare Data
        sponsor_id = str(uuid.uuid4())
        new_sponsor = {
            "id": sponsor_id,
            "sponsor_name": sponsor_name,
            "contact_email": contact_email,
            "deal_id": deal_id,
            "primary_color_hex": primary_color_hex,
            "light_bg_hex": light_bg_hex,
            "website_url": website_url,
            "logo_url": logo_url,
            "status": "pending",
            "is_active_theme": False,
            "created_at": datetime.utcnow()
        }
        
        # 3. Save to Firestore
        db.collection("sponsors").document(sponsor_id).set(new_sponsor)
        
        return new_sponsor

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sponsor submission failed: {str(e)}")

# --- 3. ADMIN MANAGEMENT (Read, Update) ---

@router.get("/", response_model=List[SponsorResponse])
def get_all_sponsors(admin_uid: str): # Requires Admin UID query param
    """Retrieves all sponsors (Admin only)."""
    
    # ---  Implement Admin role check for Read access ---
    admin_ref = db.collection("users").document(admin_uid).get()
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Insufficient privileges: Admin access required")
   

    try:
        docs = db.collection("sponsors").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{sponsor_id}", response_model=SponsorResponse)
def update_sponsor_status(sponsor_id: str, update: SponsorUpdate, admin_uid: str):
    """Admin updates sponsor status or activates/deactivates the theme."""
    
    # ---  I Admin role check for Update access ---
    admin_ref = db.collection("users").document(admin_uid).get()
    
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Insufficient privileges: Admin access required")
    
    
    sponsor_ref = db.collection("sponsors").document(sponsor_id)
    if not sponsor_ref.get().exists:
        raise HTTPException(status_code=404, detail="Sponsor not found")
        
    update_data = update.dict(exclude_none=True)

    # --- SAFETY CHECK - Return early if no data to update ---
    if not update_data:
        return sponsor_ref.get().to_dict()
   
    
    # --- : Implement logic to ensure only one theme is active ---
    if update_data.get("is_active_theme") == True:
        try:
            # 1. Query for the currently active sponsor
            active_docs = db.collection("sponsors").where("is_active_theme", "==", True).limit(1).stream()
            
            # 2. Deactivate the old active sponsor if found
            for doc in active_docs:
                doc.reference.update({"is_active_theme": False})
        except Exception as e:
            # Log the potential error, but proceed to activate the new one
            print(f"Warning: Failed to deactivate previous sponsor (Continuing): {e}")

            
    sponsor_ref.update(update_data)
    
    # Return updated document
    updated_doc = sponsor_ref.get().to_dict()
    return updated_doc

# --- 4. PUBLIC ACTIVE THEME (For frontend theme check) ---

@router.get("/active", response_model=Optional[SponsorResponse])
def get_active_sponsor():
    """Returns the single currently active sponsor for the website theme."""
    try:
        # Query for the single sponsor where is_active_theme is true
        docs = db.collection("sponsors").where("is_active_theme", "==", True).limit(1).stream()
        
        for doc in docs:
            return doc.to_dict()
            
        return None # No active sponsor found
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))