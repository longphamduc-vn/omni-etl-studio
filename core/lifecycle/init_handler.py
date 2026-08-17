# Filepath: core/lifecycle/init_handler.py
# Updated_at: 2026-08-16 23:40:00
# Description: Dynamically loads domain or subfolder __init__.json workflows and populates auth headers.

from typing import Any, Optional
from core.common.logger import log
from core.engine.runner import PipelineRunner
from core.registry.workflow_registry import WorkflowRegistry
from core.storage.context import PipelineContext


class LifecycleHandler:
    """Manages dynamic domain/subfolder initialization workflows."""

    @staticmethod
    def load_domain_session(domain_path: str, registry: WorkflowRegistry) -> Optional[PipelineContext]:
        """Dynamically discovers and executes __init__.json corresponding to active domain subfolder."""
        if not domain_path:
            return None

        # Split domain subfolder path (e.g., 'ems/item' -> ['ems', 'item'])
        parts = [p for p in domain_path.split("/") if p]
        
        init_wf = None
        # Scan subfolder hierarchy backwards to find closest __init__.json
        for i in range(len(parts), 0, -1):
            sub_path = "/".join(parts[:i])
            lookup_key = f"{sub_path}/__init__"
            init_wf = registry.get(lookup_key)
            if init_wf:
                log.info(f"[LIFECYCLE INIT] Found subfolder session init workflow: '{lookup_key}'")
                break

        if not init_wf:
            log.info(f"[LIFECYCLE INIT] No __init__.json found for domain path '{domain_path}'. Skipping session init.")
            return None

        try:
            runner = PipelineRunner(workflow=init_wf)
            ctx = runner.run()

            # Extract token and set auth header dynamically into session
            token_df = ctx.get_dataframe("ds_session_token")
            if token_df is not None and not token_df.empty:
                access_token = token_df.iloc[0].get("access_token", "")
                token_type = token_df.iloc[0].get("token_type", "Bearer")
                
                auth_hdr = token_df.iloc[0].get("auth_header")
                if not auth_hdr:
                    auth_hdr = f"{token_type} {access_token}".strip()

                ctx.session["access_token"] = access_token
                ctx.session["auth_header"] = auth_hdr
                log.info(f"[LIFECYCLE SUCCESS] Domain '{domain_path}' auth session header set to: '{auth_hdr}'")

            return ctx
        except Exception as e:
            log.error(f"[LIFECYCLE ERROR] Failed executing init workflow for '{domain_path}': {str(e)}")
            return None

    @staticmethod
    def handle_event(
        trigger_event: str,
        init_workflow: Any = None,
        existing_context: Optional[PipelineContext] = None
    ) -> Optional[PipelineContext]:
        """Backward compatible helper method."""
        return None