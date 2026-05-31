"""Measure real Gemini token usage/cost for one screenshot analysis call."""
import base64
import glob
import sys

sys.path.insert(0, ".")
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI

from app.core.config import settings
from app.services.vision_llm import _SYSTEM

# Gemini 2.5 Flash list price (USD per 1M tokens) — verify against current Google pricing.
IN_PER_M, OUT_PER_M = 0.30, 2.50

img_path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("verify/samples/**/*.jpeg", recursive=True))[0]
data = open(img_path, "rb").read()
uri = f"data:image/jpeg;base64,{base64.b64encode(data).decode()}"
msgs = [
    SystemMessage(content=_SYSTEM),
    HumanMessage(content=[
        {"type": "text", "text": "Analyze this profile screenshot. Return JSON only."},
        {"type": "image_url", "image_url": {"url": uri}},
    ]),
]


def run(label, **kw):
    model = ChatGoogleGenerativeAI(model=settings.gemini_model, temperature=0,
                                   google_api_key=settings.google_api_key or None, **kw)
    r = model.invoke(msgs)
    u = r.usage_metadata or {}
    it, ot, tot = u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("total_tokens", 0)
    billed_out = max(ot, tot - it)  # thinking tokens are billed as output
    cost = it / 1e6 * IN_PER_M + billed_out / 1e6 * OUT_PER_M
    print(f"[{label}] in={it} visible_out={ot} total={tot} billed_out~={billed_out}")
    print(f"   ${cost:.5f}/img  =  ${cost*1000:.2f}/1k  =  ${cost*1_000_000:,.0f}/1M")


print(f"image: {img_path} ({len(data)//1024} KB)\n")
run("default (thinking on)")
try:
    run("thinking OFF", thinking_budget=0)
except Exception as e:
    print(f"[thinking OFF] not supported via this param: {e}")
