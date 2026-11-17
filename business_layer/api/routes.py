"""Aggregate the independent business definition and data HTTP layers."""

from fastapi import APIRouter

from business_layer.api.data_routes import router as data_router
from business_layer.api.entity_routes import router as entities_router
from business_layer.api.language_routes import router as language_router

router = APIRouter()
router.include_router(entities_router)
router.include_router(data_router)
router.include_router(language_router)
