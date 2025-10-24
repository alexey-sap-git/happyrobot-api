# main.py - HappyRobot API with Carrier Verification & Load Search

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import random
import json
import os
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("HAPPYROBOT_API_KEY", "")
LOADS_FILE = "loads.json"
FMCSA_API_BASE = "https://mobile.fmcsa.dot.gov/qc/services"
FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")  # Set via environment variable

# FastAPI App
app = FastAPI(
    title="HappyRobot Freight API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS ====================

class CarrierVerificationRequest(BaseModel):
    mc_number: str

class CarrierVerificationResponse(BaseModel):
    mc_number: str
    is_eligible: bool
    company_name: Optional[str] = None
    safety_rating: Optional[str] = None
    operating_status: Optional[str] = None
    message: str

class LoadResponse(BaseModel):
    load_id: str
    origin: str
    destination: str
    pickup_datetime: str
    delivery_datetime: str
    equipment_type: str
    loadboard_rate: float
    notes: str
    weight: int
    commodity_type: str
    num_of_pieces: int
    miles: int
    dimensions: str

# ==================== DATA ====================

# Mock carrier database
MOCK_CARRIERS = {
    "123456": {"name": "ABC Trucking LLC", "rating": "Satisfactory"},
    "789012": {"name": "XYZ Transport Inc", "rating": "Satisfactory"},
    "456789": {"name": "Fast Freight Solutions", "rating": "Satisfactory"},
    "111222": {"name": "Nationwide Carriers", "rating": "Not Rated"},
    "333444": {"name": "Regional Logistics", "rating": "Conditional"},
}

# Load loads from JSON file
def load_loads_from_file():
    """Load freight loads from loads.json file"""
    if not os.path.exists(LOADS_FILE):
        print(f"Warning: {LOADS_FILE} not found. Using empty list.")
        return []
    
    try:
        with open(LOADS_FILE, 'r') as f:
            loads = json.load(f)
            print(f"Loaded {len(loads)} loads from {LOADS_FILE}")
            return loads
    except Exception as e:
        print(f"Error loading {LOADS_FILE}: {e}")
        return []

# ==================== HELPER FUNCTIONS ====================

def verify_api_key(authorization: str = Header(None)):
    """Verify API key from Authorization header with ApiKey scheme"""
    if not authorization:
        raise HTTPException(status_code=403, detail="Missing Authorization header")

    # Expected format: "ApiKey <key>"
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "ApiKey":
        raise HTTPException(status_code=403, detail="Invalid Authorization format. Expected: ApiKey <key>")

    api_key = parts[1]
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Root endpoint - API information"""
    loads = load_loads_from_file()
    return {
        "service": "HappyRobot Freight API",
        "version": "1.0.0",
        "status": "operational",
        "loads_available": len(loads),
        "endpoints": {
            "verify_carrier": "/api/v1/verify-carrier",
            "search_loads": "/api/v1/loads/search"
        }
    }

@app.get("/api/v1/verify-carrier/{mc_number}", response_model=CarrierVerificationResponse)
async def verify_carrier(
    mc_number: str,
    authorization: str = Header(None)
):
    """Carrier verification using FMCSA API"""
    verify_api_key(authorization)

    mc_number = mc_number.strip()

    # Validate format
    if not mc_number.isdigit():
        return CarrierVerificationResponse(
            mc_number=mc_number,
            is_eligible=False,
            message="Invalid MC number format"
        )

    # Check if FMCSA API key is configured
    if not FMCSA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="FMCSA API key not configured. Set FMCSA_API_KEY environment variable."
        )

    # Call FMCSA API
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # FMCSA API uses DOT number, but we'll try with MC number
            # You may need to convert MC to DOT or use a different endpoint
            url = f"{FMCSA_API_BASE}/carriers/{mc_number}"
            params = {"webKey": FMCSA_API_KEY}

            print(f"[DEBUG] Calling FMCSA API: {url}")
            print(f"[DEBUG] API Key (first 10 chars): {FMCSA_API_KEY[:10]}...")

            response = await client.get(url, params=params)

            print(f"[DEBUG] FMCSA Response Status: {response.status_code}")
            print(f"[DEBUG] FMCSA Response Body: {response.text[:500]}")

            if response.status_code == 404:
                return CarrierVerificationResponse(
                    mc_number=mc_number,
                    is_eligible=False,
                    message="Carrier not found in FMCSA database"
                )

            if response.status_code == 401:
                raise HTTPException(status_code=500, detail="Invalid FMCSA API key")

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"FMCSA API error: {response.status_code} - {response.text[:200]}"
                )

            # Parse FMCSA response
            data = response.json()
            content = data.get("content", {})

            if not content:
                return CarrierVerificationResponse(
                    mc_number=mc_number,
                    is_eligible=False,
                    message="Carrier not found in FMCSA database"
                )

            # Extract carrier information directly from the response
            carrier = content.get("carrier", {})

            if not carrier:
                return CarrierVerificationResponse(
                    mc_number=mc_number,
                    is_eligible=False,
                    message="Carrier information not available"
                )

            # Extract relevant fields
            company_name = carrier.get("legalName") or carrier.get("dbaName", "Unknown")
            allowed_to_operate = carrier.get("allowedToOperate", "N")
            status_code = carrier.get("statusCode", "")
            safety_rating = carrier.get("safetyRating")
            oos_date = carrier.get("oosDate")

            # Determine eligibility
            # Carrier is eligible if:
            # 1. allowedToOperate = "Y"
            # 2. Not out of service (oosDate is null)
            is_eligible = (allowed_to_operate == "Y" and oos_date is None)

            # Determine operating status message
            if oos_date:
                operating_status = "Out of Service"
            elif allowed_to_operate == "Y":
                operating_status = "Active"
            else:
                operating_status = "Not Authorized"

            message = f"Carrier is {'eligible' if is_eligible else 'not eligible'} to operate"

            return CarrierVerificationResponse(
                mc_number=mc_number,
                is_eligible=is_eligible,
                company_name=company_name,
                safety_rating=safety_rating,
                operating_status=operating_status,
                message=message
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="FMCSA API request timed out")
    except httpx.RequestError as e:
        print(f"[ERROR] FMCSA Request Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error connecting to FMCSA API: {str(e)}")
    except Exception as e:
        print(f"[ERROR] Unexpected Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/v1/loads/search", response_model=List[LoadResponse])
async def search_loads(
    origin: Optional[str] = Query(None, description="Origin city or state (e.g., 'Chicago, IL')"),
    destination: Optional[str] = Query(None, description="Destination city or state (e.g., 'Dallas, TX')"),
    equipment_type: Optional[str] = Query(None, description="Equipment type - must match exactly (e.g., 'Dry Van', 'Flatbed', 'Reefer')"),
    max_results: int = Query(5, ge=1, le=20, description="Maximum number of results to return"),
    authorization: str = Header(None)
):
    """
    Search available loads with STRICT matching.

    - origin: Must match city/state (case-insensitive, partial match allowed)
    - destination: Must match city/state (case-insensitive, partial match allowed)
    - equipment_type: STRICT exact match required (case-insensitive)

    All filters are applied with AND logic (all conditions must be met).
    """
    verify_api_key(authorization)
    
    # Load all loads from file
    all_loads = load_loads_from_file()
    
    if not all_loads:
        return []
    
    # Start with all loads
    results = all_loads.copy()
    
    # STRICT Filter by origin (must contain the search term)
    if origin:
        origin_lower = origin.lower().strip()
        results = [
            load for load in results 
            if origin_lower in load.get("origin", "").lower()
        ]
        print(f"After origin filter '{origin}': {len(results)} loads")
    
    # STRICT Filter by destination (must contain the search term)
    if destination:
        destination_lower = destination.lower().strip()
        results = [
            load for load in results 
            if destination_lower in load.get("destination", "").lower()
        ]
        print(f"After destination filter '{destination}': {len(results)} loads")
    
    # STRICT Filter by equipment type (EXACT match, case-insensitive)
    if equipment_type:
        equipment_lower = equipment_type.lower().strip()
        results = [
            load for load in results 
            if load.get("equipment_type", "").lower() == equipment_lower
        ]
        print(f"After equipment_type filter '{equipment_type}': {len(results)} loads")
    
    # If no matches found, return empty list (strict mode - no suggestions)
    if not results:
        print(f"No loads found matching criteria: origin={origin}, dest={destination}, equip={equipment_type}")
        return []
    
    # Limit results
    results = results[:max_results]
    
    print(f"Returning {len(results)} loads")
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)