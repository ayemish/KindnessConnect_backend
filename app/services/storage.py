import os
from supabase import create_client, Client
from fastapi import UploadFile
import uuid
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# 2. Get variables from .env
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
bucket: str = os.environ.get("SUPABASE_BUCKET")

# 3. Create the Supabase Client (This is the variable missing in your error)
if not url or not key:
    print(" Error: SUPABASE_URL or SUPABASE_KEY is missing in .env file")
    supabase = None
else:
    supabase: Client = create_client(url, key)

async def upload_image(file: UploadFile) -> str:
    """
    Uploads a file to Supabase Storage and returns the public URL.
    """
    try:
        if not supabase:
            raise Exception("Supabase client is not initialized.")

        # Generate a unique filename
        file_ext = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        
        # Read file bytes
        file_content = await file.read()
        
        # Upload to Supabase
        supabase.storage.from_(bucket).upload(
            path=file_name,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        # Get Public URL
        public_url = supabase.storage.from_(bucket).get_public_url(file_name)
        
        return public_url
    except Exception as e:
        print(f"Error uploading to Supabase: {e}")
        raise e