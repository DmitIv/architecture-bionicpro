from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.reports import router as reports_router

app = FastAPI(
    title="Reports API",
    description="API for BionicPRO reports",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Reports API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
