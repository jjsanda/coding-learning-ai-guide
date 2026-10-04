"""API v1 router."""

from fastapi import APIRouter

from codeguide.api import assignments, auth, courses, insights, meta, submissions

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(meta.router)
api_v1.include_router(auth.router)
api_v1.include_router(courses.router)
api_v1.include_router(assignments.router)
api_v1.include_router(submissions.router)
api_v1.include_router(insights.router)
