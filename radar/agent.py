"""A bounded tool-using agent. Published prose is rendered from validated facts."""
import os
from typing import TypedDict

NEXT_STEPS = {
    "collect_history":"Accumulate more matched observations before forecasting.",
    "inspect_coverage":"Check missing markets, seller fields and query coverage.",
    "verify_supplier":"Verify supplier cost and fulfilment before a commercial decision.",
    "review_model":"Compare validation and test error against the recent-mean baseline.",
}


def facts_for(snapshot):
    facts = {}
    for group in snapshot["groups"]:
        if not group["sample_products"]:
            continue
        key = group["country"] + ":" + group["niche"]
        growth = "unavailable" if group["growth7"] is None else f'{group["growth7"]:.1%}'
        facts[key] = {
            "id":key,"country":group["country"],"niche":group["niche"],
            "text":f'{group["country_name"]} / {group["label"]}: {group["sample_products"]} sampled products; matched-panel growth {growth}; confidence {group["confidence"]}.',
            "metrics":group,
        }
    return facts


def report(snapshot, config, *, enabled=True, client=None, on_attempt=None):
    facts = facts_for(snapshot)
    result = {"state":"rule_based","calls":0,"evidence_ids":list(facts)[:6],
              "next_steps":["collect_history","inspect_coverage"],"trace":[]}
    if not enabled or not facts:
        result["reason"] = "disabled" if not enabled else "no_observations"
    elif not os.environ.get("GEMINI_API_KEY") and client is None:
        result["reason"] = "missing_gemini_key"
    elif os.environ.get("GEMINI_FREE_TIER_ONLY", "").lower() != "true" and client is None:
        result["reason"] = "free_tier_confirmation_missing"
    else:
        try:
            from google import genai
            from google.genai import types
            from langgraph.graph import StateGraph, START, END
            client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                http_options=types.HttpOptions(timeout=30000,retry_options=types.HttpRetryOptions(attempts=1)))
            declarations = [
                {"name":"query_metrics","description":"Read observed country/niche evidence.","parameters":{"type":"OBJECT","properties":{"country":{"type":"STRING"}}}},
                {"name":"compare_markets","description":"Compare one niche across observed markets.","parameters":{"type":"OBJECT","properties":{"niche":{"type":"STRING"}},"required":["niche"]}},
                {"name":"inspect_trends","description":"Inspect recent observed trend points.","parameters":{"type":"OBJECT","properties":{"country":{"type":"STRING"}},"required":["country"]}},
                {"name":"finalize_report","description":"Select verified evidence IDs and next steps for the report.","parameters":{"type":"OBJECT","properties":{
                    "evidence_ids":{"type":"ARRAY","items":{"type":"STRING"}},
                    "next_steps":{"type":"ARRAY","items":{"type":"STRING","enum":list(NEXT_STEPS)}}},"required":["evidence_ids","next_steps"]}},
            ]
            class State(TypedDict):
                contents:list
                calls:int
                done:bool
                selected:list
                steps:list
                trace:list

            def research(state):
                state["calls"] += 1
                result["calls"] = state["calls"]
                if on_attempt:
                    on_attempt(state["calls"])
                response = client.models.generate_content(model=config["agent"]["model"], contents=state["contents"],
                    config=types.GenerateContentConfig(temperature=0,max_output_tokens=1200,
                        system_instruction="You are a sampled-market research agent. First inspect tools. Finalize using ONLY evidence IDs returned by tools. Never claim a blue ocean, real sales, brand incubation or efficiency gains. Do not include free-text financial claims. Data are incomplete. Maximum five model turns.",
                        tools=[types.Tool(function_declarations=declarations)]))
                if not response.candidates or not response.candidates[0].content:
                    return state
                content = response.candidates[0].content
                state["contents"].append(content)
                responses = []
                for part in (content.parts or [])[:10]:
                    fc = part.function_call
                    if not fc:
                        continue
                    args = dict(fc.args or {})
                    payload = {"error":"unknown_tool"}
                    if fc.name in {"query_metrics","compare_markets"}:
                        payload = {"evidence":[f for f in facts.values() if
                            (not args.get("country") or f["country"] == args["country"]) and
                            (not args.get("niche") or f["niche"] == args["niche"])]}
                    elif fc.name == "inspect_trends":
                        payload = {"points":[p for p in snapshot["trends"] if p["country"] == args.get("country")][-42:]}
                    elif fc.name == "finalize_report":
                        selected, steps = args.get("evidence_ids",[]), args.get("next_steps",[])
                        if isinstance(selected,list) and selected and all(isinstance(i,str) and i in facts for i in selected) and isinstance(steps,list) and all(isinstance(s,str) and s in NEXT_STEPS for s in steps):
                            state.update(done=True,selected=list(dict.fromkeys(selected))[:6],steps=list(dict.fromkeys(steps))[:4])
                            payload = {"accepted":True}
                        else:
                            payload = {"error":"invalid_evidence_or_step"}
                    state["trace"].append({"turn":state["calls"],"tool":fc.name,"accepted":payload.get("accepted")})
                    responses.append(types.Part.from_function_response(name=fc.name,response=payload))
                if responses:
                    state["contents"].append(types.Content(role="user",parts=responses))
                return state

            graph = StateGraph(State)
            graph.add_node("research",research)
            graph.add_edge(START,"research")
            graph.add_conditional_edges("research",lambda s: END if s["done"] or s["calls"] >= config["agent"]["max_calls"] else "research")
            end = graph.compile().invoke({"contents":[types.Content(role="user",parts=[types.Part.from_text(text="Inspect current metrics, compare markets, then finalize the evidence report.")])],
                "calls":0,"done":False,"selected":[],"steps":[],"trace":[]},config={"recursion_limit":12})
            result.update(calls=end["calls"],trace=end["trace"])
            if end["done"]:
                result.update(state="agent_completed",evidence_ids=end["selected"],next_steps=end["steps"])
            else:
                result["reason"] = "model_turn_limit"
        except Exception as error:
            # Do not log SDK exceptions: request URLs may contain credentials.
            result["reason"] = "agent_unavailable:" + type(error).__name__
    header = "SYNTHETIC DEMONSTRATION — NOT MARKET EVIDENCE\n\n" if snapshot["synthetic"] else ""
    lines = [header+"# Daily evidence brief",f'Agent state: {result["state"]}.',
             "This report describes sampled public counters, not actual orders or whole-market opportunity.",""]
    lines += [f'- [{key}] {facts[key]["text"]}' for key in result["evidence_ids"]]
    if not facts:
        lines += ["No real observations have been collected. Configure the collector before interpreting this dashboard."]
    lines += ["", "Next checks:"] + ["- "+NEXT_STEPS[key] for key in result["next_steps"]]
    return result, "\n".join(lines)+"\n"
