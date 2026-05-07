from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.routes import router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    default_response_class=ORJSONResponse,
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

allow_all_origins = settings.allow_all_cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else settings.cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if request.url.path.endswith("/health"):
        raise exc
    return ORJSONResponse(
        status_code=500,
        content={"detail": "服務處理請求時發生錯誤，請查看後端日誌。"},
    )


app.include_router(router, prefix=settings.api_prefix)
