from fastapi import APIRouter, Request

from models import SessionStatusResponse, SubmitOrderRequest, SubmitOrderResponse
from services import order_service

router = APIRouter(tags=["orders"])


@router.get("/{unique_link}", response_model=SessionStatusResponse)
def get_session_status(unique_link: str):
    return order_service.get_session_status(unique_link)


@router.post("/{unique_link}/submit", response_model=SubmitOrderResponse)
def submit_order(unique_link: str, body: SubmitOrderRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    return order_service.submit_order(
        unique_link=unique_link,
        member_name=body.member_name,
        pizza_ids=body.pizza_ids,
        client_ip=client_ip,
    )
