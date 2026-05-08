from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    availability,
    bookings,
    business,
    services,
    staff,
    ws,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(business.router)
api_router.include_router(services.router)
api_router.include_router(staff.router)
api_router.include_router(availability.router)
api_router.include_router(bookings.router)
api_router.include_router(admin.router)
api_router.include_router(ws.router)
