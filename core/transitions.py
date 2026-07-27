"""Atomic monitoring transitions implemented by PostgreSQL RPC functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.db import get_supabase_client


@dataclass(slots=True)
class TransitionResult:
    success: bool
    code: str
    message: str
    data: dict[str, Any]


class TransitionRejected(RuntimeError):
    """A database transition was rejected because the state changed or is invalid."""

    def __init__(self, code: str, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


def actor_payload(user: dict | None, fallback_role: str = "system") -> dict[str, str]:
    user = user or {}
    email = str(user.get("email") or "").strip().lower()
    name = str(user.get("full_name") or user.get("name") or email).strip()
    role = str(user.get("role") or fallback_role).strip()
    return {"email": email, "name": name, "role": role}


def _normalise_rpc_data(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        if len(raw) == 1 and isinstance(raw[0], dict):
            return raw[0]
        return {"items": raw}
    return {"value": raw}


def _call(function_name: str, params: dict[str, Any]) -> TransitionResult:
    response = get_supabase_client().rpc(function_name, params).execute()
    data = _normalise_rpc_data(getattr(response, "data", None))
    success = bool(data.get("success"))
    code = str(data.get("code") or ("ok" if success else "transition_failed"))
    message = str(data.get("message") or "")
    result = TransitionResult(success=success, code=code, message=message, data=data)
    if not success:
        raise TransitionRejected(code, message or "Перехід відхилено базою даних.", data)
    return result


def approve_request_step(*, request_id: int, expected_status: str,
                         expected_chain_stage: int, new_status: str,
                         new_chain_stage: int, approval_chain: str | None,
                         comment: str, action: str, user: dict,
                         created_by: str) -> TransitionResult:
    return _call("transition_approve_request_step", {
        "p_request_id": int(request_id),
        "p_expected_status": expected_status,
        "p_expected_chain_stage": int(expected_chain_stage),
        "p_new_status": new_status,
        "p_new_chain_stage": int(new_chain_stage),
        "p_approval_chain": approval_chain,
        "p_comment": comment,
        "p_action": action,
        "p_actor": actor_payload(user),
        "p_created_by": created_by,
    })


def return_request(*, request_id: int, expected_status: str,
                   expected_chain_stage: int, new_status: str,
                   new_chain_stage: int, comment: str, action: str,
                   user: dict, created_by: str) -> TransitionResult:
    return _call("transition_return_request", {
        "p_request_id": int(request_id),
        "p_expected_status": expected_status,
        "p_expected_chain_stage": int(expected_chain_stage),
        "p_new_status": new_status,
        "p_new_chain_stage": int(new_chain_stage),
        "p_comment": comment,
        "p_action": action,
        "p_actor": actor_payload(user),
        "p_created_by": created_by,
    })


def resubmit_head_edit_to_final_coordinator(
    *,
    request_id: int,
    expected_updated_at: str,
    expected_status: str,
    expected_chain_stage: int,
    existing_coordinator_stage: int,
    final_coordinator_stage: int,
    approval_chain: str,
    scheme_label: str,
    payload: dict[str, Any],
    action: str,
    user: dict,
    created_by_before: str,
    created_by_after: str,
) -> TransitionResult:
    """Атомарно редагує дані керівником ССП і робить координатора фінальним."""
    return _call("transition_resubmit_head_edit_final_coordinator", {
        "p_request_id": int(request_id),
        "p_expected_updated_at": expected_updated_at,
        "p_expected_status": expected_status,
        "p_expected_chain_stage": int(expected_chain_stage),
        "p_existing_coordinator_stage": int(existing_coordinator_stage),
        "p_final_coordinator_stage": int(final_coordinator_stage),
        "p_approval_chain": approval_chain,
        "p_scheme_label": scheme_label,
        "p_payload": payload,
        "p_action": action,
        "p_actor": actor_payload(user),
        "p_created_by_before": created_by_before,
        "p_created_by_after": created_by_after,
    })


def withdraw_request(*, request_id: int, expected_status: str,
                     expected_chain_stage: int, comment: str,
                     user: dict) -> TransitionResult:
    return _call("transition_withdraw_request", {
        "p_request_id": int(request_id),
        "p_expected_status": expected_status,
        "p_expected_chain_stage": int(expected_chain_stage),
        "p_comment": comment,
        "p_actor": actor_payload(user),
    })


def create_closeout(*, payload: dict[str, Any], user: dict) -> TransitionResult:
    return _call("transition_create_closeout", {
        "p_payload": payload,
        "p_actor": actor_payload(user),
    })


def decide_closeout(*, closeout_id: int, expected_status: str,
                    new_status: str, decision_comment: str,
                    head_email: str, user: dict) -> TransitionResult:
    return _call("transition_decide_closeout", {
        "p_closeout_id": int(closeout_id),
        "p_expected_status": expected_status,
        "p_new_status": new_status,
        "p_decision_comment": decision_comment,
        "p_head_email": head_email,
        "p_actor": actor_payload(user),
    })


def set_final_locked(*, request_id: int, expected_status: str,
                     comment: str, action: str, user: dict) -> TransitionResult:
    return _call("transition_set_final_locked", {
        "p_request_id": int(request_id),
        "p_expected_status": expected_status,
        "p_comment": comment,
        "p_action": action,
        "p_actor": actor_payload(user),
    })


def correct_locked_request(*, request_id: int, updates: dict[str, Any],
                           reason: str, user: dict) -> TransitionResult:
    return _call("transition_correct_locked_request", {
        "p_request_id": int(request_id),
        "p_updates": updates,
        "p_reason": reason,
        "p_actor": actor_payload(user),
    })


def submit_request(*, payload: dict[str, Any], action: str,
                   user: dict, created_by: str,
                   draft_email: str = "", draft_key: str = "") -> TransitionResult:
    """Атомарно створює заявку, першу версію та запис журналу."""
    return _call("transition_submit_request", {
        "p_payload": payload,
        "p_action": action,
        "p_actor": actor_payload(user),
        "p_created_by": created_by,
        "p_draft_email": draft_email,
        "p_draft_key": draft_key,
    })


def resubmit_request(*, request_id: int, expected_updated_at: str,
                     expected_status: str, expected_chain_stage: int,
                     target_chain_stage: int, payload: dict[str, Any], mode: str, action: str,
                     user: dict, created_by_before: str,
                     created_by_after: str,
                     draft_email: str = "", draft_key: str = "") -> TransitionResult:
    """Атомарно повторно подає або редагує заявку з optimistic locking."""
    return _call("transition_resubmit_request", {
        "p_request_id": int(request_id),
        "p_expected_updated_at": expected_updated_at,
        "p_expected_status": expected_status,
        "p_expected_chain_stage": int(expected_chain_stage),
        "p_target_chain_stage": int(target_chain_stage),
        "p_payload": payload,
        "p_mode": mode,
        "p_action": action,
        "p_actor": actor_payload(user),
        "p_created_by_before": created_by_before,
        "p_created_by_after": created_by_after,
        "p_draft_email": draft_email,
        "p_draft_key": draft_key,
    })
