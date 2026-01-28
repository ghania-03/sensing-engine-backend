# Sensing Engine - Backend

## Description
This is the backend of the **Sensing Engine** project built with **FastAPI**.  
It handles all API endpoints for demand forecasting, trends, and health checks.  

## Folder Structure
backend/
│
├── app/ # Main application code
│ ├── routes/ # API route definitions
│ ├── controllers/ # Business logic
│ ├── models/ # Data models
│ ├── services/ # Services and utilities
│ └── utils/ # Helper functions
├── scripts/ # Optional scripts
├── main.py # FastAPI entry point
├── requirements.txt # Python dependencies


## Installation

1. **Create a virtual environment:**
```bash
python -m venv .venv
Activate the virtual environment:

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
Install dependencies:

pip install -r requirements.txt
Run Backend
uvicorn main:app --reload
Server will start on http://127.0.0.1:8000

API endpoints are prefixed with /api

Example: GET http://127.0.0.1:8000/api/health

Notes
The backend currently does not require a .env file.

.venv and __pycache__ are ignored in version control.

For deployment, create a new virtual environment locally and install dependencies.

