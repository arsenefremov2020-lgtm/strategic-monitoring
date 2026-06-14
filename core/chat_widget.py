"""Floating bird chat widget for the three approved approval pages."""

from __future__ import annotations

import json
from typing import Literal

import streamlit as st
import streamlit.components.v1 as components

from core.config import ALLOWED_CHAT_PAGES
from core.db import get_supabase_client
from core.errors import log_exception

_CHANNELS = ["coordinator", "responsible", "group"]


def _load_messages() -> dict[str, list[dict[str, str]]]:
    """Load the latest chat messages for all widget channels."""
    client = get_supabase_client()
    result: dict[str, list[dict[str, str]]] = {}
    for channel in _CHANNELS:
        try:
            response = (
                client.table("chat_messages")
                .select("*")
                .eq("channel", channel)
                .order("created_at", desc=False)
                .limit(80)
                .execute()
            )
            result[channel] = response.data or []
        except Exception as exc:
            log_exception(f"load chat messages: {channel}", exc)
            result[channel] = []
    return result


def _safe_messages_for_js(messages: list[dict[str, str]]) -> str:
    """Serialize messages to a safe JSON list for the frontend widget."""
    safe = []
    for item in messages:
        safe.append(
            {
                "sender": str(item.get("sender", "")),
                "text": str(item.get("text", "")),
                "ts": str(item.get("created_at", ""))[:16].replace("T", " "),
            }
        )
    return json.dumps(safe, ensure_ascii=False)


def render_bird_chat(page_name: str, sender: str) -> None:
    """Render the bird chat only on the allowed pages, independent of filters."""
    if page_name not in ALLOWED_CHAT_PAGES:
        return

    messages = _load_messages()
    supabase_url = json.dumps(st.secrets["SUPABASE_URL"])
    supabase_key = json.dumps(st.secrets["SUPABASE_KEY"])
    sender_js = json.dumps(sender, ensure_ascii=False)

    st.markdown(
        """
        <style>
        div[data-testid="stCustomComponentV1"] {
            width: 0 !important; height: 0 !important; min-height: 0 !important;
            margin: 0 !important; padding: 0 !important; overflow: hidden !important;
        }
        div[data-testid="stCustomComponentV1"] iframe {
            width: 0 !important; height: 0 !important; min-height: 0 !important;
            border: 0 !important; opacity: 0 !important; pointer-events: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    html = f"""<!DOCTYPE html>
<html lang=\"uk\"><head><meta charset=\"utf-8\"></head><body>
<script>
(function(){{
  const SU = {supabase_url};
  const SK = {supabase_key};
  const ME = {sender_js};
  const cache = {{
    coordinator: {_safe_messages_for_js(messages.get('coordinator', []))},
    responsible: {_safe_messages_for_js(messages.get('responsible', []))},
    group: {_safe_messages_for_js(messages.get('group', []))}
  }};
  const labels = {{coordinator:'📋 Координатор', responsible:'👤 ССП', group:'👥 Груп'}};
  let cur = 'coordinator';
  let poll = null;
  const doc = window.parent.document;

  const oldRoot = doc.getElementById('bird-chat-root');
  if (oldRoot) oldRoot.remove();
  const oldStyle = doc.getElementById('bird-chat-style');
  if (oldStyle) oldStyle.remove();

  const style = doc.createElement('style');
  style.id = 'bird-chat-style';
  style.textContent = `
#bird-chat-root {{ position: fixed !important; inset: 0 !important; z-index: 2147483647 !important; pointer-events: none !important; font-family: Helvetica Neue, Arial, sans-serif !important; }}
#bird-chat-root * {{ box-sizing: border-box !important; }}
#bird-fab {{ pointer-events: auto !important; position: fixed !important; bottom: 92px !important; right: 96px !important; width: 60px !important; height: 60px !important; border-radius: 50% !important; background: linear-gradient(135deg,#1e40af,#3b82f6) !important; box-shadow: 0 8px 28px rgba(37,99,235,.5) !important; cursor: pointer !important; display: flex !important; align-items: center !important; justify-content: center !important; border: 3px solid #fff !important; transition: transform .2s, box-shadow .2s !important; user-select: none !important; }}
#bird-fab:hover {{ transform: scale(1.1) !important; box-shadow: 0 12px 36px rgba(37,99,235,.6) !important; }}
#bird-fab svg {{ width: 36px !important; height: 36px !important; }}
#bird-chat {{ pointer-events: auto !important; position: fixed !important; bottom: 164px !important; right: 96px !important; width: 370px !important; max-height: 500px !important; background: #fff !important; border: 1px solid #d8dee9 !important; border-radius: 20px !important; box-shadow: 0 20px 60px rgba(15,23,42,.2) !important; display: none !important; flex-direction: column !important; overflow: hidden !important; }}
#bird-chat.open {{ display: flex !important; }}
#bch {{ background: linear-gradient(135deg,#1e40af,#3b82f6) !important; color: #fff !important; padding: 12px 16px !important; font-weight: 900 !important; font-size: 14px !important; display: flex !important; align-items: center !important; justify-content: space-between !important; }}
#bcx {{ cursor: pointer !important; font-size: 18px !important; opacity: .75 !important; padding: 2px 6px !important; border-radius: 4px !important; }}
#bcx:hover {{ opacity: 1 !important; background: rgba(255,255,255,.2) !important; }}
#bctabs {{ display: flex !important; border-bottom: 1px solid #e2e8f0 !important; background: #f8fafc !important; }}
.bctab {{ flex: 1 !important; text-align: center !important; padding: 9px 4px !important; font-size: 11px !important; font-weight: 700 !important; color: #64748b !important; cursor: pointer !important; border-bottom: 2px solid transparent !important; white-space: nowrap !important; }}
.bctab.active {{ color: #1e40af !important; border-bottom-color: #3b82f6 !important; background: #fff !important; }}
#bcmsgs {{ flex: 1 !important; overflow-y: auto !important; padding: 12px !important; display: flex !important; flex-direction: column !important; gap: 8px !important; background: #f8fafc !important; min-height: 260px !important; max-height: 300px !important; }}
.bmw {{ display: flex !important; flex-direction: column !important; }} .bmw.me {{ align-items: flex-end !important; }} .bmw.other {{ align-items: flex-start !important; }}
.bmr {{ display: flex !important; align-items: flex-end !important; gap: 7px !important; }} .bmw.me .bmr {{ flex-direction: row-reverse !important; }}
.bav {{ width: 27px !important; height: 27px !important; border-radius: 50% !important; display: flex !important; align-items: center !important; justify-content: center !important; font-size: 11px !important; font-weight: 900 !important; color: #fff !important; flex-shrink: 0 !important; background:#3b82f6 !important; }}
.bbl {{ max-width: 74% !important; padding: 8px 12px !important; border-radius: 14px !important; font-size: 13px !important; line-height: 1.45 !important; word-break: break-word !important; }}
.bmw.me .bbl {{ background: linear-gradient(135deg,#1e40af,#3b82f6) !important; color: #fff !important; border-bottom-right-radius: 4px !important; }}
.bmw.other .bbl {{ background: #fff !important; border: 1px solid #e2e8f0 !important; color: #1e293b !important; border-bottom-left-radius: 4px !important; box-shadow: 0 1px 4px rgba(0,0,0,.06) !important; }}
.bmt {{ font-size: 10px !important; color: #94a3b8 !important; margin-top: 3px !important; }} .bmw.me .bmt {{ text-align: right !important; }}
.bemp {{ color: #94a3b8 !important; font-size: 13px !important; text-align: center !important; margin: auto !important; padding: 24px !important; }}
#bcinp {{ display: flex !important; gap: 8px !important; padding: 10px 12px !important; border-top: 1px solid #e2e8f0 !important; background: #fff !important; }}
#bcinp input {{ flex: 1 !important; border: 1.5px solid #bfdbfe !important; border-radius: 10px !important; padding: 8px 12px !important; font-size: 13px !important; outline: none !important; background: #f0f9ff !important; font-family: inherit !important; }}
#bcinp input:focus {{ border-color: #3b82f6 !important; background: #fff !important; }}
#bcinp button {{ background: linear-gradient(135deg,#1e40af,#3b82f6) !important; color: #fff !important; border: none !important; border-radius: 10px !important; padding: 8px 14px !important; font-size: 16px !important; font-weight: 700 !important; cursor: pointer !important; }}
@media (max-width:700px) {{ #bird-fab {{ right:20px !important; bottom:82px !important; }} #bird-chat {{ right:14px !important; bottom:154px !important; width:calc(100vw - 28px) !important; }} }}
`;
  doc.head.appendChild(style);

  const root = doc.createElement('div');
  root.id = 'bird-chat-root';
  root.innerHTML = `
<div id=\"bird-fab\" title=\"Чат\">
  <svg viewBox=\"0 0 64 64\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"><ellipse cx=\"32\" cy=\"38\" rx=\"16\" ry=\"13\" fill=\"#60a5fa\"/><circle cx=\"32\" cy=\"22\" r=\"11\" fill=\"#3b82f6\"/><circle cx=\"28\" cy=\"20\" r=\"3\" fill=\"white\"/><circle cx=\"36\" cy=\"20\" r=\"3\" fill=\"white\"/><circle cx=\"28.8\" cy=\"20\" r=\"1.4\" fill=\"#1e3a8a\"/><circle cx=\"36.8\" cy=\"20\" r=\"1.4\" fill=\"#1e3a8a\"/><path d=\"M30 25 L32 29 L34 25 Q32 23 30 25Z\" fill=\"#fbbf24\"/><ellipse cx=\"17\" cy=\"36\" rx=\"7\" ry=\"10\" fill=\"#2563eb\" transform=\"rotate(-20 17 36)\"/><ellipse cx=\"47\" cy=\"36\" rx=\"7\" ry=\"10\" fill=\"#2563eb\" transform=\"rotate(20 47 36)\"/><path d=\"M24 49 Q32 56 40 49 Q36 52 32 51 Q28 52 24 49Z\" fill=\"#1d4ed8\"/></svg>
</div>
<div id=\"bird-chat\"><div id=\"bch\"><span>🐦 Чат</span><span id=\"bcx\">✕</span></div><div id=\"bctabs\"><div class=\"bctab active\" data-ch=\"coordinator\">📋 Координатор</div><div class=\"bctab\" data-ch=\"responsible\">👤 ССП</div><div class=\"bctab\" data-ch=\"group\">👥 Груп</div></div><div id=\"bcmsgs\"></div><div id=\"bcinp\"><input id=\"bci\" type=\"text\" placeholder=\"Напишіть повідомлення...\"/><button id=\"bcsend\">➤</button></div></div>`;
  doc.body.appendChild(root);

  const $ = (sel) => root.querySelector(sel);
  const all = (sel) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');
  function render(msgs) {{
    const box = $('#bcmsgs');
    if (!msgs || !msgs.length) {{ box.innerHTML = '<div class=\"bemp\">Повідомлень поки немає.<br>Напишіть першим 👇</div>'; return; }}
    box.innerHTML = msgs.slice(-60).map((m) => {{
      const me = m.sender === ME;
      const letter = m.sender === 'Координатор' ? '⚙' : (m.sender || 'В').slice(0,1);
      return `<div class=\"bmw ${{me ? 'me' : 'other'}}\"><div class=\"bmr\"><div class=\"bav\">${{esc(letter)}}</div><div class=\"bbl\">${{esc(m.text)}}</div></div><div class=\"bmt\">${{esc(m.sender)}} · ${{esc(m.ts)}}</div></div>`;
    }}).join('');
    box.scrollTop = box.scrollHeight;
  }}
  function fetchMessages() {{
    fetch(SU + '/rest/v1/chat_messages?channel=eq.' + encodeURIComponent(cur) + '&order=created_at.asc&limit=80', {{headers:{{apikey:SK, Authorization:'Bearer '+SK}}}})
      .then(r => r.json()).then(d => {{ cache[cur] = d.map(x => ({{sender:x.sender, text:x.text, ts:(x.created_at||'').slice(0,16).replace('T',' ')}})); render(cache[cur]); }}).catch(() => {{}});
  }}
  function startPoll() {{ if (poll) clearInterval(poll); poll = setInterval(fetchMessages, 8000); }}
  function stopPoll() {{ if (poll) {{ clearInterval(poll); poll = null; }} }}
  function toggle() {{ const w = $('#bird-chat'); const open = w.classList.toggle('open'); if (open) {{ render(cache[cur]); startPoll(); setTimeout(() => $('#bci').focus(), 100); }} else {{ stopPoll(); }} }}
  function send() {{
    const inp = $('#bci'); const txt = inp.value.trim(); if (!txt) return;
    inp.value = ''; inp.disabled = true;
    fetch(SU + '/rest/v1/chat_messages', {{method:'POST', headers:{{apikey:SK, Authorization:'Bearer '+SK, 'Content-Type':'application/json', Prefer:'return=minimal'}}, body:JSON.stringify({{channel:cur, sender:ME, text:txt}})}})
      .then(fetchMessages).catch(e => alert('Помилка: ' + e.message)).finally(() => {{ inp.disabled = false; inp.focus(); }});
  }}
  $('#bird-fab').addEventListener('click', toggle);
  $('#bcx').addEventListener('click', toggle);
  $('#bcsend').addEventListener('click', send);
  $('#bci').addEventListener('keydown', e => {{ if (e.key === 'Enter') send(); }});
  all('.bctab').forEach(t => t.addEventListener('click', () => {{ cur = t.dataset.ch; all('.bctab').forEach(x => x.classList.toggle('active', x.dataset.ch === cur)); render(cache[cur]); fetchMessages(); }}));
  render(cache[cur]);
}})();
</script></body></html>"""

    components.html(html, height=0, scrolling=False)
