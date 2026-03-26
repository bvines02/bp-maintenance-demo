from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from analysis import (
    get_duty_standby_opportunities,
    get_deferral_opportunities,
    get_deferral_summary_by_task,
    get_cost_summary,
)
import anthropic
import os
import json

router = APIRouter(prefix="/chat", tags=["chat"])

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def build_context(db: Session) -> str:
    cost = get_cost_summary(db)
    ds_opps = get_duty_standby_opportunities(db)[:5]
    def_opps = get_deferral_opportunities(db)[:5]
    def_summary = get_deferral_summary_by_task(db)[:10]

    context = f"""
You are an expert maintenance optimisation analyst for offshore oil and gas platforms.
You have access to the maintenance database for Alpha Platform.

PLATFORM SUMMARY:
- Total assets: {cost['total_assets']}
- Duty/standby pairs: {cost['duty_standby_pairs']}
- Total work orders (2019-2024): {cost['total_work_orders']}
- Total PPM cost: £{cost['ppm_cost']:,.0f}
- Total statutory cost: £{cost['statutory_cost']:,.0f}
- Total corrective cost: £{cost['corrective_cost']:,.0f}
- Identified potential annual savings: £{cost['total_potential_annual_saving']:,.0f}

TOP DUTY/STANDBY OPTIMISATION OPPORTUNITIES:
{json.dumps(ds_opps, indent=2)}

TOP DEFERRAL PATTERN OPPORTUNITIES:
{json.dumps(def_opps, indent=2)}

FLEET-WIDE DEFERRAL SUMMARY (tasks deferred >14 days):
{json.dumps(def_summary, indent=2)}

Your role is to:
1. Answer questions about the maintenance data
2. Help the user test hypotheses (e.g., "should standby pumps have the same interval as duty pumps?")
3. Identify and quantify optimisation opportunities
4. Provide reasoned, risk-aware recommendations
5. Always consider the impact on availability, reliability, and safety

When analysing hypotheses, use the data provided to support or challenge the hypothesis with evidence.
Be concise and use tables or bullet points where appropriate.
Always qualify recommendations with risk considerations.
"""
    return context


@router.post("/")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    system_prompt = build_context(db)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )

    return {"response": response.content[0].text}
