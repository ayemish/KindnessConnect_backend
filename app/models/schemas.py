from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# =======================
# USER SCHEMAS 
# =======================

class UserBase(BaseModel):
    """User details for registration/profile."""
    email: EmailStr
    full_name: str
    role: str = "donor"  # Default role
    
    phone_number: Optional[str] = None
    profile_image_url: Optional[str] = None

class UserCreate(UserBase):
    uid: str

class UserResponse(UserBase):
    uid: str
    is_verified: bool = False
    created_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


# =======================
# REQUEST SCHEMAS 
# =======================

class RequestCreate(BaseModel):
    """Schema for creating a donation campaign (includes receiving bank details)."""
    title: str
    category: str
    story: str
    goal_amount: float
    deadline: str
    bank_account_no: str
    bank_name: str
    show_name_publicly: bool = True 

class RequestResponse(BaseModel):
    """Schema for returning campaign details."""
    id: str
    requester_uid: str
    title: str
    category: str
    story: str
    goal_amount: float
    collected_amount: float = 0.0
    
    image_url: Optional[str] = None     
    gallery_urls: List[str] = []        
    
    status: str                         
    created_at: datetime
    
    requester_name: Optional[str] = "Unknown"
    requester_verified: bool = False


# =======================
# DONATION SCHEMAS 
# =======================

class DonationCreate(BaseModel):
    request_id: str
    donor_uid: str
    amount: float
    payment_method: str
    request_title: Optional[str] = None 

class DonationResponse(BaseModel):
    id: str
    request_id: str
    donor_uid: str
    amount: float
    timestamp: datetime
    
    
    payment_method: Optional[str] = "card"
    request_title: Optional[str] = "Unknown Campaign"
    
    
    
# Schema for AI Story Generation Input
class StoryGenerationInput(BaseModel):
    title: str
    category: str
    goal_amount: float
    story: Optional[str] = ""
    
    
# =======================
# SPONSOR SCHEMAS 
# =======================

class SponsorDealBase(BaseModel):
    """Defines fixed sponsorship tiers and prices."""
    name: str # e.g., "1 Week Standard"
    duration_days: int
    price_usd: float

class SponsorDealResponse(SponsorDealBase):
    id: str
    class Config:
        from_attributes = True


class SponsorContactBase(BaseModel):

    sponsor_name: str
    contact_email: EmailStr 
    deal_id: str
    website_url: Optional[str] = None

class SponsorCreate(SponsorContactBase):  
    """Data submitted by a potential sponsor."""
    
    # Custom Theme Data
    primary_color_hex: str 
    light_bg_hex: str 


class SponsorResponse(SponsorContactBase): 
    """Data returned for a sponsor record."""

    contact_email: str 
    primary_color_hex: str   
    light_bg_hex: str
    
    id: str
    logo_url: Optional[str] = None
    status: str = "pending" 
    created_at: datetime
    
    # Runtime fields to enable the theme change
    is_active_theme: bool = False
    
    class Config:
        from_attributes = True

class SponsorUpdate(BaseModel):
    """Schema for admin to approve/reject/activate a sponsor."""
    status: Optional[str] = None
    is_active_theme: Optional[bool] = None
    
    
    primary_color_hex: Optional[str] = None
    light_bg_hex: Optional[str] = None
    website_url: Optional[str] = None
    
   
    contact_email: Optional[EmailStr] = None
    
    
  

# =======================
# VERIFICATION SCHEMAS
# =======================

class VerificationDealBase(BaseModel):
    """Defines fixed tiers for verification and associated cost."""
    name: str  
    cost_usd: float
    duration_days: int 
    
class VerificationDealResponse(VerificationDealBase):
    id: str
    class Config:
        from_attributes = True

class VerificationRequestCreate(BaseModel):
    """Data submitted by a user requesting verification."""
    requester_uid: str
    deal_id: str
    
    
class VerificationRequestResponse(VerificationRequestCreate):
    """Data returned for a verification request record."""
    id: str
    user_name: Optional[str] = None 
    status: str = "pending" 
    
    created_at: datetime
    
    class Config:
        from_attributes = True

class VerificationRequestUpdate(BaseModel):
    """Schema for admin to approve/reject a request."""
    status: Optional[str] = None
    
    # Optional field to update the user's main verification status upon approval
    is_verified: Optional[bool] = None