from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from app.config import db
from app.services.storage import supabase, bucket
from app.routers import users, requests, donations, sponsors
from app.routers import verification


app = FastAPI(title="KindnessConnect API", version="1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(requests.router)
app.include_router(donations.router)
app.include_router(sponsors.router)
app.include_router(verification.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to KindnessConnect API", "status": "Running"}