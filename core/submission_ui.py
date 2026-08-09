"""Спільне помітне підтвердження успішного подання (В3)."""

from __future__ import annotations

from html import escape

import streamlit as st

NOTICE_KEY = "persistent_submission_notice"


def set_submission_notice(*, first_stage_label: str, codes: list[str], repeated: bool = False) -> None:
    st.session_state[NOTICE_KEY] = {
        "first_stage_label": str(first_stage_label or "Координатор").strip(),
        "codes": [str(code).strip() for code in codes if str(code).strip()],
        "repeated": bool(repeated),
    }


def render_submission_notice(*, dismissible: bool = True, consume: bool = False) -> None:
    """Render the shared success notice without forcing a second page rerun.

    ``dismissible=False`` removes the legacy «Продовжити роботу» button.
    ``consume=True`` shows the notice once at its requested location and clears
    it immediately from session state.  For the dismissible variant a
    placeholder is reserved before the button; if the user dismisses the
    notice during the current Streamlit event run, the placeholder stays empty
    and the already-dismissed banner is not painted again.
    """
    notice = st.session_state.get(NOTICE_KEY)
    if not isinstance(notice, dict):
        return

    stage = escape(str(notice.get("first_stage_label") or "Координатор"))
    codes = [str(code) for code in notice.get("codes") or []]
    code_text = escape(", ".join(codes[:8]) + ("…" if len(codes) > 8 else ""))
    heading = "Заявку повторно подано" if notice.get("repeated") else "Заявку подано"
    detail = f" Вона очікує на розгляд: {stage}."
    if len(codes) > 1:
        heading = "Заявки повторно подано" if notice.get("repeated") else "Заявки подано"
        detail = f" Вони очікують на розгляд: {stage}."
    codes_html = f'<div style="margin-top:7px;font-size:13px;">Коди: {code_text}</div>' if code_text else ""
    banner = f"""
        <div style="background:#ecfdf3;border:2px solid #22c55e;border-left:8px solid #16a34a;
                    border-radius:14px;padding:18px 22px;margin:14px 0 18px 0;
                    box-shadow:0 6px 18px rgba(22,163,74,.12);color:#14532d;">
            <div style="font-size:20px;font-weight:900;">✅ {heading}.</div>
            <div style="font-size:15px;font-weight:650;margin-top:4px;">{detail}</div>
            {codes_html}
        </div>
    """

    if consume:
        st.markdown(banner, unsafe_allow_html=True)
        st.session_state.pop(NOTICE_KEY, None)
        return

    if not dismissible:
        st.markdown(banner, unsafe_allow_html=True)
        return

    banner_slot = st.empty()
    dismissed = st.button("Продовжити роботу", key="dismiss_submission_notice", type="primary")
    if dismissed:
        st.session_state.pop(NOTICE_KEY, None)
        return
    banner_slot.markdown(banner, unsafe_allow_html=True)
