from fastapi import APIRouter, HTTPException, Depends
from app.config import db
from app.models.schemas import DonationCreate, DonationResponse
from datetime import datetime
import uuid
from firebase_admin import firestore
from typing import Optional 
from typing import Dict

router = APIRouter(prefix="/donations", tags=["Donations"])



# 1. Make a Donation 
@router.post("/", response_model=DonationResponse)
def create_donation(donation: DonationCreate):
 
    try:
        # 1. Fetch Request Details to get the Title
        request_ref = db.collection("donation_requests").document(donation.request_id)
        request_doc = request_ref.get()
        
        if not request_doc.exists:
            raise HTTPException(status_code=404, detail="Donation Request not found")
        
        request_data = request_doc.to_dict()
        # Retrieve title safely from request data
        request_title = request_data.get('title', 'Unknown Campaign Title - Data Error')

        # 2. Create the Donation Record
        donation_id = str(uuid.uuid4())
        new_donation = {
            "id": donation_id,
            "request_id": donation.request_id,
            "donor_uid": donation.donor_uid,
            "amount": donation.amount,
            "payment_method": donation.payment_method,
            "timestamp": datetime.utcnow().isoformat(), 
            "request_title": request_title 
        }
        
        db.collection("donations").document(donation_id).set(new_donation)

        # 3. ATOMIC UPDATE
        request_ref.update({
            "collected_amount": firestore.Increment(donation.amount)
        })

        return new_donation

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Donation processing failed: {str(e)}")



# 2. Get  Donations 
@router.get("/user/{uid}", response_model=list[DonationResponse])
def get_user_donations(uid: str):
    """
    Retrieves all donations made by a specific user, checking both the 
    authenticated UID and the test placeholder ID.
    """
    try:
        # 1. Query for donations matching the actual authenticated UID (New data)
        donation_docs_real = list(db.collection("donations").where("donor_uid", "==", uid).stream())
        donations_real = [doc.to_dict() for doc in donation_docs_real]

        # 2. Query for donations matching the test placeholder ID (Old data fallback)
        donation_docs_test = list(db.collection("donations").where("donor_uid", "==", "web_donor_test").stream())
        donations_test = [doc.to_dict() for doc in donation_docs_test]

        # 3. Merge all results
        donations_list = donations_real + donations_test

        # 4. Format time data for frontend display
        for donation in donations_list:
            if isinstance(donation.get('timestamp'), datetime):
                donation['timestamp'] = donation['timestamp'].isoformat()
            
            if 'request_title' not in donation:
                 donation['request_title'] = 'Unknown Campaign'
                 
        return donations_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving donations: {str(e)}")
    
    
# Dependency to check admin role (reusing your existing pattern)
def get_admin(admin_uid: str):
    admin_ref = db.collection("users").document(admin_uid).get()
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        # Note: You need a dependency function like this in your users.py or similar
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return admin_uid


# 3. Get All Donations (Admin Only)
@router.get("/all", response_model=list[DonationResponse])
def get_all_donations(admin_uid: str = Depends(get_admin)):
    """
    Retrieves all donations made by all users for the Admin Ledger.
    Enriches the data with the donor's full name.
    """
    try:
        donation_docs = db.collection("donations").stream()
        donations_list = []
        user_data_cache: Dict[str, dict] = {}

        for doc in donation_docs:
            donation = doc.to_dict()
            donor_uid = donation.get("donor_uid")

            # 1. Check Cache or Fetch Donor Data
            if donor_uid and donor_uid not in user_data_cache:
                user_doc = db.collection("users").document(donor_uid).get()
                user_data = user_doc.to_dict() if user_doc.exists else {}
                user_data_cache[donor_uid] = user_data
            
            user_data = user_data_cache.get(donor_uid, {})

            # 2. Enrich the donation data with donor name
            donor_name = user_data.get('full_name', "Anonymous Donor (UID Missing)")
            
            # Add the new field to the response structure
            donation['donor_name'] = donor_name 

            # Format time data
            if isinstance(donation.get('timestamp'), datetime):
                donation['timestamp'] = donation['timestamp'].isoformat()
            
            if 'request_title' not in donation:
                donation['request_title'] = 'Unknown Campaign'

            donations_list.append(donation)
        
        return donations_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving all donations: {str(e)}")