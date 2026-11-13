"""Мини-клиент MCP редактора Unreal для проверок из терминала."""
import json, re, sys, urllib.request
U = "http://127.0.0.1:8001/mcp"
H = {"content-type": "application/json", "accept": "application/json,text/event-stream"}
_sid = None
_id = 0
def _post(body):
    global _sid
    h = dict(H)
    if _sid: h["Mcp-Session-Id"] = _sid
    r = urllib.request.urlopen(urllib.request.Request(U, json.dumps(body).encode(), h), timeout=120)
    raw = r.read().decode()
    _sid = r.headers.get("Mcp-Session-Id") or _sid
    return json.loads(raw) if raw.strip() else None
def connect():
    _post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}})
    try: _post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    except Exception: pass
def mcp(name, args):
    global _id
    if _sid is None:
        connect()   # соединение по первому вызову: импорт работает и без открытого редактора
    _id += 1
    d = _post({"jsonrpc": "2.0", "id": _id, "method": "tools/call", "params": {"name": name, "arguments": args}})
    if "error" in d: return "RPC ERROR " + json.dumps(d["error"], ensure_ascii=False)
    r = d["result"]
    return ("TOOL ERROR " if r.get("isError") else "") + "\n".join(c.get("text", "") for c in r.get("content", []))
def describe(toolset): return mcp("describe_toolset", {"toolset_name": toolset})
def tool(toolset, name, args): return mcp("call_tool", {"toolset_name": toolset, "tool_name": name, "arguments": args})
