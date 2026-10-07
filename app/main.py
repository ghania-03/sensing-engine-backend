from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import forecast, trends, health


app = FastAPI(title="Sensing Engine API")

# Allow local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://localhost:8080",
        "https://sensing-engine-frontend-psi.vercel.app",
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers from the `routes` package under /api
app.include_router(health.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(trends.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "Sensing Engine backend running"}
