from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.stats import YearbookSummary, OverallStats
from backend.app.services.stats_service import StatsService

router = APIRouter()

@router.get("/yearbook/{year}", response_model=YearbookSummary)
def get_yearbook(year: int, db: Session = Depends(get_db)):
    return StatsService.get_yearbook(db=db, year=year)

@router.get("/overall", response_model=OverallStats)
def get_overall_stats(db: Session = Depends(get_db)):
    return StatsService.get_overall_stats(db=db)
