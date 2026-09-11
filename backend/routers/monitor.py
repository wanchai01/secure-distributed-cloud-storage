"""
Monitoring routes (Phase 8): infra-style health checks.

Deliberately public (no JWT required) - health/status endpoints are
conventionally used by load balancers, uptime monitors, and container
orchestrators that can't authenticate. They only report operational
status (up/down, connected/disconnected), never business data -
contrast with /dashboard and /admin/*, which do require auth because
they expose user/file counts and listings.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.database.database import test_connection
from backend.services import node_service

router = APIRouter(prefix="/monitor", tags=["Monitoring"])


class HealthResponse(BaseModel):
    status: str
    database: str
    nodes: dict[str, str]


class NodeDetail(BaseModel):
    node_name: str
    status: str
    total_files: int
    total_size: int


class NodesResponse(BaseModel):
    nodes: list[NodeDetail]


@router.get("/health", response_model=HealthResponse, summary="Overall system health")
def health():
    db_ok = test_connection()
    all_nodes = node_service.get_all_nodes()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        nodes={n["node_name"]: n["status"] for n in all_nodes},
    )


@router.get("/nodes", response_model=NodesResponse, summary="Per-node status detail")
def nodes_status():
    all_nodes = node_service.get_all_nodes()
    return NodesResponse(
        nodes=[
            NodeDetail(
                node_name=n["node_name"],
                status=n["status"],
                total_files=n["total_files"],
                total_size=n["total_size"],
            )
            for n in all_nodes
        ]
    )
