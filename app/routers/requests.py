# requests.py

import dotenv
dotenv.load_dotenv() # MUST be at the very top to load environment variables immediately

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Header
from app.config import db
from app.services.storage import upload_image
from app.models.schemas import RequestResponse, StoryGenerationInput 
from app.dependencies.auth import verify_firebase_token 
from datetime import datetime
import uuid
from typing import List, Optional
from firebase_admin import firestore

from openai import OpenAI
# --- GEMINI IMPORTS ---
import os
from google import genai
from google.genai.errors import APIError as GeminiAPIError
from google.genai.types import GenerateContentConfig


# Define model names and base URLs globally
GEMINI_MODEL = "gemini-2.5-flash"
HF_BASE_URL = "https://router.huggingface.co/v1" 
HF_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct" 

router = APIRouter(prefix="/requests", tags=["Requests"])

# --- REQUIRED HELPER FUNCTION: AGGRESSIVE CLEANING ---
def clean_story_output(raw_story: str) -> str:
    """Removes markdown artifacts and introductory phrases from AI output."""
    final_story = raw_story.strip()
    
    # 1. Remove markdown code blocks 
    if final_story.startswith('```') and final_story.endswith('```'):
        lines = final_story.split('\n')
        if len(lines) > 2:
            final_story = '\n'.join(lines[1:-1]).strip()

    # 2. Remove common introductory phrases 
    intro_phrases = [
        "here is the story:", "the story:", "story:", "narrative:", 
        "here is the narrative:", "i will generate the story now:", 
        "generated story:", "here is the refined story:", "final story:"
    ]
    for phrase in intro_phrases:
        if final_story.lower().startswith(phrase):
            final_story = final_story[len(phrase):].lstrip()
    
    # 3. Remove leading markdown artifacts
    while final_story.startswith('#') or final_story.startswith('*'):
        final_story = final_story.lstrip('#* ').strip()
    
    return final_story if final_story else raw_story.strip()



# 1. Create a New Donation Request 
@router.post("/", response_model=RequestResponse)
async def create_request(
    title: str = Form(...),
    category: str = Form(...),
    story: str = Form(...),
    goal_amount: float = Form(...),
    deadline: str = Form(...),
    requester_uid: str = Form(...), 
    bank_account_no: str = Form(...),
    bank_name: str = Form(...),
    show_name_publicly: bool = Form(True),
    file: UploadFile = File(...), 
    gallery_files: Optional[List[UploadFile]] = File(None) 
):
    try:
        # 1. Upload Mandatory Cover Image
        image_url = await upload_image(file)
        
        # 2. Upload Optional Gallery Images 
        gallery_urls = []
        if gallery_files:
            for gallery_file in gallery_files:
                url = await upload_image(gallery_file)
                gallery_urls.append(url)
        
        # 3. Prepare Data
        request_id = str(uuid.uuid4())
        new_request = {
            "id": request_id,
            "requester_uid": requester_uid,
            "title": title,
            "category": category,
            "story": story,
            "goal_amount": goal_amount,
            "collected_amount": 0.0,
            "deadline": deadline,
            "image_url": image_url,
            "gallery_urls": gallery_urls, 
            "status": "pending",
            "bank_account_no": bank_account_no,
            "bank_name": bank_name,
            "show_name_publicly": show_name_publicly, 
            "created_at": datetime.utcnow()
        }
        
        # 4. Save to Firestore
        db.collection("donation_requests").document(request_id).set(new_request)
        
        # 5. Look up Requester Name and Verification Status for the Response
        user_doc = db.collection("users").document(requester_uid).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}

        # Prepare response data 
        response_data = new_request.copy()
        
        # Determine name based on the public flag
        if new_request.get("show_name_publicly", True):
            response_data['requester_name'] = user_data.get("full_name", "Unknown")
        else:
            response_data['requester_name'] = "Anonymous Donor" 

        response_data['requester_verified'] = user_data.get("is_verified", False)
        
        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 2. Get All Active Requests 
@router.get("/", response_model=list[RequestResponse])
def get_all_requests():
    try:
        docs = db.collection("donation_requests").stream()
        requests = []
        
        user_data_cache = {} 

        for doc in docs:
            req = doc.to_dict()
            requester_uid = req.get("requester_uid")
            
            # 1. Check Cache or Fetch User Data
            if requester_uid and requester_uid not in user_data_cache:
                user_doc = db.collection("users").document(requester_uid).get()
                if user_doc.exists:
                    user_data_cache[requester_uid] = user_doc.to_dict()
                else:
                    user_data_cache[requester_uid] = {} 
            
            user_data = user_data_cache.get(requester_uid, {})

            # 2. Populate new fields in the response
            is_public = req.get("show_name_publicly", True) 
            
            # Apply privacy filter
            if is_public:
                 req['requester_name'] = user_data.get('full_name', "Unknown")
            else:
                 req['requester_name'] = "Anonymous Donor"

            # Verification status is always determined by the user record
            req['requester_verified'] = user_data.get('is_verified', False)

            requests.append(req)
            
        return requests
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. Get Single Request Details 
@router.get("/{request_id}", response_model=RequestResponse)
def get_request_details(request_id: str):
    doc = db.collection("donation_requests").document(request_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Request not found")
        
    req = doc.to_dict()
    requester_uid = req.get("requester_uid")

    # Fetch User Data
    user_doc = db.collection("users").document(requester_uid).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    # Populate new fields in the response
    is_public = req.get("show_name_publicly", True) 

    # Apply privacy filter
    if is_public:
        req['requester_name'] = user_data.get('full_name', "Unknown")
    else:
        req['requester_name'] = "Anonymous Donor"
        
    req['requester_verified'] = user_data.get('is_verified', False)
    
    return req


# 4. Verify (Approve) a Request - ADMIN ONLY
@router.put("/{request_id}/verify")
def verify_request(
    request_id: str, 
    uid: str 
):
    # 1. Check if the user is an Admin
    user_ref = db.collection("users").document(uid).get()
    
    print(f"Checking User: {uid}")
    if user_ref.exists:
        print(f"User Role: {user_ref.to_dict().get('role')}")
    else:
        print("User document does not exist!")

    if not user_ref.exists or user_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can verify requests")

    # 2. Update the request status
    request_ref = db.collection("donation_requests").document(request_id)
    if not request_ref.get().exists:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request_ref.update({"status": "verified"})
    
    return {"message": "Request approved successfully", "status": "verified"}


# 5. Reject a Request - ADMIN ONLY
@router.put("/{request_id}/reject")
def reject_request(
    request_id: str, 
    uid: str 
):
    # 1. Check if the user is an Admin
    user_ref = db.collection("users").document(uid).get()
    
    print(f"Checking User for Rejection: {uid}")
    if user_ref.exists:
        print(f"User Role: {user_ref.to_dict().get('role')}")
    else:
        print("User document does not exist!")

    if not user_ref.exists or user_ref.to_dict().get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can verify requests")

    # 2. Update the request status
    request_ref = db.collection("donation_requests").document(request_id)
    if not request_ref.get().exists:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request_ref.update({"status": "rejected"})
    
    return {"message": "Request rejected", "status": "rejected"}

# 6. Get Requests by User ID (My Requests)
@router.get("/user/{uid}", response_model=list[RequestResponse])
def get_requests_by_user(uid: str):
    """
    Retrieves all donation requests created by a specific user.
    """
    try:
        docs = db.collection("donation_requests").where("requester_uid", "==", uid).stream()
        
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
# 7. Initiate or Retrieve Chat Session ID
@router.post("/{request_id}/chat/{donor_uid}")
def initiate_chat(request_id: str, donor_uid: str):
    """
    Creates a unique chat room ID based on the requester and donor UIDs.
    This ensures only one chat exists per request/donor pair.
    """
    try:
        # 1. Fetch Request to get Requester UID
        request_doc = db.collection("donation_requests").document(request_id).get()
        if not request_doc.exists:
            raise HTTPException(status_code=404, detail="Request not found")
            
        requester_uid = request_doc.to_dict().get('requester_uid')

        # 2. Define a unique chat identifier (sorted to ensure uniqueness regardless of caller order)
        participants = sorted([requester_uid, donor_uid])
        
        # We use a custom chat ID format: request_id_UID1_UID2
        chat_id = f"{request_id}_{participants[0]}_{participants[1]}"
        
        # 3. Create the document in the 'chats' collection (if it doesn't exist)
        chat_ref = db.collection("chats").document(chat_id)
        
        if not chat_ref.get().exists:
            chat_ref.set({
                "id": chat_id,
                "request_id": request_id,
                "requester_uid": requester_uid,
                "donor_uid": donor_uid,
                "participants": participants,
                "created_at": datetime.utcnow()
            })
            
        return {"chat_id": chat_id, "requester_uid": requester_uid}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# 8. Generate Story (Primary: Gemini, Secondary: HF Llama 3)
@router.post("/generate_story")
def generate_story_text(data: StoryGenerationInput):
    """
    Attempts generation using Gemini first. If it fails (quota, server error), 
    it falls back to the Hugging Face Llama 3 model.
    """
    # Get Keys from the environment (loaded by dotenv at the top)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    HF_TOKEN = os.environ.get('HF_TOKEN')
    
    # --- STEP 1: Determine Prompt Content ---
    user_draft = data.story.strip() if data.story else ""
    
    # Define the core instructions and context
    context_details = f"CONTEXT: The campaign is for '{data.title}', category '{data.category}', aiming for ${data.goal_amount}."

    if user_draft:
        # --- PROMPT TYPE A: REFINE EXISTING DRAFT ---
        story_instruction = (
            f"ROLE: You are an expert fundraising copywriter. Your goal is to refine and expand the 'Initial Draft' below "
            f"into a professional, compelling, and emotionally sincere appeal. "
            f"{context_details} "
            f"TONE & STRUCTURE: The story must be highly urgent, sincere, and infused with hope. It must follow a three-part narrative structure: [The Conflict/Problem], [The Solution/Donor's Role], and [The Urgent Call to Action]. "
            f"FORMATTING: Your response MUST be ONLY the refined story text (under 250 words total). DO NOT include any titles, markdown headings, or introductory phrases."
        )
        user_content = f"Initial Draft: \"{user_draft}\""
    else:
        # --- PROMPT TYPE B: GENERATE NEW STORY ---
        story_instruction = (
            f"ROLE: You are an expert fundraising copywriter. Write a powerful and heart-felt fundraising story from a personal perspective (first person, 'I' or 'We'). "
            f"{context_details} "
            f"TONE & STRUCTURE: The story must evoke strong empathy and highlight an immediate, desperate need. It must create a sense of urgency, tying the donation directly to a life-changing outcome. "
            f"FORMATTING: Your response MUST be ONLY the story text (under 250 words total). DO NOT include any titles, markdown headings, or introductory phrases."
        )
        user_content = "Generate the full story now."
        
    # --- STEP 2: TRY PRIMARY API: GEMINI ---
    try:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found. Skipping primary API.")

        gemini_client = genai.Client()
        
        # NOTE: Gemini uses contents list directly for instructions
        contents = [story_instruction, user_content]

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=GenerateContentConfig(temperature=0.7, max_output_tokens=350),
        )
        
        raw_story = response.text.strip()
        final_story = clean_story_output(raw_story) 
        return {"story": final_story}

    except (GeminiAPIError, ValueError) as e:
        # Catch quota, auth, server errors, or missing key (ValueError)
        print(f"Gemini API Failed ({type(e).__name__}): {e}. Falling back to Hugging Face...")

    # --- STEP 3: TRY SECONDARY API: HUGGING FACE (LLAMA 3) ---
    try:
        if not HF_TOKEN:
            raise ValueError("HF_TOKEN not found. Cannot use secondary API.")

        hf_client = OpenAI(base_url=HF_BASE_URL, api_key=HF_TOKEN)
        
        # NOTE: HF/OpenAI uses the messages list format
        messages = [
            {"role": "system", "content": story_instruction},
            {"role": "user", "content": user_content}
        ]

        response = hf_client.chat.completions.create(
            model=HF_MODEL,
            messages=messages,
            max_tokens=350,
            temperature=0.7 
        )
        
        raw_story = response.choices[0].message.content.strip()
        final_story = clean_story_output(raw_story) 
        return {"story": final_story}

    except Exception as e:
        # Catch any failure from the secondary API
        print(f"Secondary API (Hugging Face) Failed: {e}")
        
    # --- STEP 4: FINAL FAILURE ---
    # If both APIs failed, raise a generic error
    raise HTTPException(
        status_code=503, 
        detail="Both AI generation services (Gemini and Hugging Face) are currently unavailable or rate-limited. Please try again later."
    )