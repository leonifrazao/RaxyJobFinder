import asyncio
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from buscador_vagas import JobFinder

# App

app = FastAPI(
    title="RaxyJobFinder API",
    description="Wrapper REST do SDK RaxyJobFinder com SSE para eventos em tempo real.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# Config Redis

REDIS_URL = os.getenv("RAXY_REDIS_URL", "redis://localhost:6379/0")
REDIS_EVENTS_CHANNEL = os.getenv("RAXY_REDIS_CHANNEL", "raxy:events")
REDIS_DATA_CHANNEL = os.getenv("RAXY_REDIS_DATA_CHANNEL", "vagas:disponiveis")


# Schemas

class SearchRequest(BaseModel):
    portal: str = Field("linkedin", description="linkedin | gupy | glassdoor")
    keywords: str = Field("Vagas", description="Termo de busca")
    location: str = Field("Brasil", description="Localização")
    location_id: Optional[str] = Field(None, description="ID da localização (pula typeahead)")
    location_choice: Optional[int] = Field(None, description="Índice 1-based no typeahead")
    work_type: str = Field("normal", description="normal | remote | hybrid — só LinkedIn")
    under_10_applicants: bool = Field(False, description="Menos de 10 candidatos — só LinkedIn")
    recent_period: str = Field("any", description="any | day | week | month — só LinkedIn")
    proxy_provider: str = Field("united-states", description="Provedor de proxies por país")
    proxy_sources: Optional[list[str]] = Field(None, description="URLs/arquivos de proxies manuais")
    valid_count: int = Field(25, ge=1, description="Pool de bridges")
    jobs_per_proxy: int = Field(5, ge=1, description="Vagas por proxy antes de rotacionar")
    max_count: int = Field(177, ge=1, description="Máx. de configs de proxy a carregar")
    threads: int = Field(8, ge=1, le=32, description="Workers para testar proxies")
    timeout: float = Field(12.0, gt=0, description="Timeout do proxy (s)")
    detail_timeout: float = Field(15.0, gt=0, description="Timeout do detalhe (s)")
    filters: Optional[dict] = Field(None, description="Filtro programático (JobFilterSet.from_dict)")
    details_limit: int = Field(20, ge=0, description="Máx. de vagas para detalhar (0 = todas)")
    start: int = Field(0, ge=0, description="Offset inicial de paginação")
    max_jobs: int = Field(0, ge=0, description="Máx. de vagas (0 = só 1ª página)")
    detail_threads: int = Field(5, ge=1, le=20, description="Threads paralelas para detalhes")
    gd_cookie: str = Field("", description="Cookie de sessão Glassdoor")
    filter_by_keywords: bool = Field(False, description="Filtrar keyword no título antes do detalhe")
    jobs_output: Optional[str] = Field(None, description="Caminho de saída vagas básicas")
    details_output: Optional[str] = Field(None, description="Caminho de saída vagas detalhadas")


# Helper: executar busca em thread separada (SDK é síncrono)

def _run_search(req: SearchRequest) -> list[dict]:
    """Executa a busca síncrona do SDK e retorna lista de dicts."""
    from buscador_vagas import JobFilterSet

    filterset = None
    if req.filters:
        filterset = JobFilterSet.from_dict(req.filters)

    # Caminhos de saída padrão por portal
    jobs_out = req.jobs_output or f"output/{req.portal}/vagas.json"
    details_out = req.details_output or f"output/{req.portal}/detalhadas.json"

    # Garante diretório de saída
    os.makedirs(os.path.dirname(jobs_out), exist_ok=True)
    os.makedirs(os.path.dirname(details_out), exist_ok=True)

    finder = JobFinder(
        portal=req.portal,
        keywords=req.keywords,
        location=req.location,
        location_id=req.location_id,
        location_choice=req.location_choice,
        work_type=req.work_type,
        under_10_applicants=req.under_10_applicants,
        recent_period=req.recent_period,
        proxy_provider=req.proxy_provider,
        proxy_sources=req.proxy_sources,
        valid_count=req.valid_count,
        jobs_per_proxy=req.jobs_per_proxy,
        max_count=req.max_count,
        threads=req.threads,
        timeout=req.timeout,
        detail_timeout=req.detail_timeout,
        filters=filterset,
        details_limit=req.details_limit,
        start=req.start,
        max_jobs=req.max_jobs,
        detail_threads=req.detail_threads,
        gd_cookie=req.gd_cookie,
        filter_by_keywords=req.filter_by_keywords,
        silent=True,
    )

    jobs = finder.search(
        jobs_output=jobs_out,
        details_output=details_out,
    )

    return [j.to_dict() for j in jobs]


# Rotas

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/search", summary="Busca vagas (resposta síncrona)")
async def search(req: SearchRequest):
    """Dispara uma busca e aguarda o resultado completo antes de responder.Para buscas longas, prefira /search/stream."""
    loop = asyncio.get_event_loop()
    try:
        jobs = await loop.run_in_executor(executor, _run_search, req)
        return {"total": len(jobs), "jobs": jobs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/search/stream", summary="Busca vagas com SSE (eventos em tempo real)")
async def search_stream(req: SearchRequest):

    async def event_generator() -> AsyncGenerator[str, None]:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()

        await pubsub.subscribe(REDIS_EVENTS_CHANNEL, REDIS_DATA_CHANNEL)

        # Dispara a busca em background
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(executor, _run_search, req)

        try:
            yield _sse("connected", {"message": "Busca iniciada"})

            # Retransmite eventos Redis enquanto a busca corre
            while not task.done():
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=0.2,
                )
                if message and message.get("data"):
                    channel = message.get("channel", "")
                    try:
                        data = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        data = {"raw": message["data"]}

                    if channel == REDIS_DATA_CHANNEL:
                        yield _sse("vagas", data)
                    else:
                        yield _sse("event", data)

                await asyncio.sleep(0.05)

            # Resultado final
            try:
                jobs = await task
                yield _sse("done", {"total": len(jobs), "jobs": jobs})
            except Exception as exc:
                yield _sse("error", {"message": str(exc), "traceback": traceback.format_exc()})

        except asyncio.CancelledError:
            yield _sse("cancelled", {"message": "Conexão encerrada pelo cliente"})
        finally:
            await pubsub.unsubscribe()
            await redis_client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/output/{portal}", summary="Lê o último JSON salvo de um portal")
async def get_output(
    portal: str,
    kind: str = Query("detalhadas", description="vagas | detalhadas"),
):
    """Retorna o conteúdo do último arquivo JSON gerado para o portal."""
    path = f"output/{portal}/{kind}.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Arquivo {path} não encontrado.")
    with open(path) as f:
        return JSONResponse(content=json.load(f))


# Helpers


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"