from fastapi import APIRouter

from backend.app.api.papers import router as papers_router
from backend.app.api.system import router as system_router
from backend.app.api.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(workspaces_router)
api_router.include_router(papers_router)
