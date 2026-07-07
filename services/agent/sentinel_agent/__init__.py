"""Silent-Drift Sentinel agent: a LangGraph state machine that turns a drift
signal into a durable, catalogued root-cause on the model.

Five nodes: Detect -> Traverse -> Root-Cause -> Identify Owner -> Write-Back.
The LLM reasons (root-cause narrative only); deterministic code executes every
DataHub write, so the demo cannot wobble.
"""
