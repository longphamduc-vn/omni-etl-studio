# Filepath: ui/components/retry_modal.py
# Updated_at: 2026-08-16 23:59:00
# Description: Retry panel component supporting PAUSED_WAITING_RETRY status.

from typing import Callable, Any
import streamlit as st


class RetryPanelComponent:
    """Renders manual action panel when pipeline is paused or waiting for retry."""

    @staticmethod
    def render(context: Any, on_retry: Callable[[str], None], on_skip: Callable[[str], None]) -> None:
        exec_status = getattr(context, "exec_status", None)

        # 🎯 BỔ SUNG PAUSED_WAITING_RETRY VÀO ĐIỀU KIỆN
        if exec_status not in ["PAUSED", "PAUSED_WAITING_RETRY", "FAILED"]:
            return

        st.warning("⚠️ **Pipeline Execution Paused / Awaiting Manual Action**")

        step_states = getattr(context, "step_states", {})
        paused_step_id = None
        error_msg = ""

        for s_id, s_state in step_states.items():
            status_val = getattr(s_state, "status", None)
            if status_val in ["failed", "paused", "PAUSED", "PAUSED_WAITING_RETRY"]:
                paused_step_id = s_id
                error_msg = getattr(s_state, "error_message", "Unknown error")
                break

        if not paused_step_id:
            paused_step_id = "step1_search_products"

        st.error(f"**Paused at Step:** `{paused_step_id}`\n\n**Error:** {error_msg}")

        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button(f"🔄 RETRY STEP ({paused_step_id})", type="primary", width="stretch"):
                on_retry(paused_step_id)

        with col_skip:
            if st.button(f"⏭️ SKIP STEP ({paused_step_id})", type="secondary", width="stretch"):
                on_skip(paused_step_id)