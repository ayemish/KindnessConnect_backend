from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <--- The key ingredient!
from app.config import db
from app.services.storage import supabase, bucket
from app.routers import users, requests, donations, sponsors
from app.routers import verification


app = FastAPI(title="KindnessConnect API", version="1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows ALL websites (including localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all actions (GET, POST, etc.)
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