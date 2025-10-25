# HappyRobot Freight API

A FastAPI-based freight management API for carrier verification and load searching.

## Features

- **Carrier Verification**: Verify carrier eligibility using FMCSA database
- **Load Search**: Search available freight loads by origin, destination, and equipment type

## Quick Start

### Using Docker (Recommended)

```bash
docker-compose up
```

### Using Python

```bash
pip install -r requirements.txt
python main.py
```

API runs on: `http://localhost:8000`

## Environment Variables

Create a `.env` file:

```
HAPPYROBOT_API_KEY=your_api_key_here
FMCSA_API_KEY=your_fmcsa_key_here
```

## API Endpoints

### 1. Verify Carrier
```
GET /api/v1/verify-carrier/{mc_number}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/verify-carrier/1610653" \
  -H "Authorization: ApiKey YOUR_API_KEY"
```

### 2. Search Loads
```
GET /api/v1/loads/search
```

**Parameters:**
- `origin` - Origin city/state (optional)
- `destination` - Destination city/state (optional)
- `equipment_type` - Equipment type: "Dry Van", "Flatbed", "Reefer" (optional)
- `max_results` - Max results (1-20, default: 5)

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/loads/search?origin=Chicago&equipment_type=Dry%20Van" \
  -H "Authorization: ApiKey YOUR_API_KEY"
```

## Authentication

All endpoints require an API key in the Authorization header:

```
Authorization: ApiKey YOUR_API_KEY
```