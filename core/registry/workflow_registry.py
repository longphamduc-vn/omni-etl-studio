# Filepath: core/registry/workflow_registry.py
# Updated_at: 2026-08-16 23:25:00
# Description: Registry assigning domain_path and preserving workflow_name metadata.

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.common.logger import log
from core.common.schemas import WorkflowConfig


class WorkflowRegistry:
    """Registry discovering and indexing workflows based entirely on physical directory layout."""

    def __init__(self, root_dir: str = "workflows"):
        self.root_dir = Path(root_dir)
        self._workflows: Dict[str, WorkflowConfig] = {}
        self.reload()

    def reload(self) -> None:
        """Scans workflows/ folder and derives domain_path strictly from physical file directory."""
        self._workflows.clear()
        if not self.root_dir.exists():
            log.warning(f"[REGISTRY WARNING] Root workflow directory '{self.root_dir}' missing.")
            return

        for json_file in self.root_dir.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Tự động tính domain_path từ thư mục chứa
                rel_path = json_file.relative_to(self.root_dir)
                parent_dir = str(rel_path.parent).replace("\\", "/")
                computed_domain = "general" if parent_dir == "." else parent_dir

                data["domain_path"] = computed_domain
                wf = WorkflowConfig(**data)

                if wf.workflow_type == "init" or wf.workflow_id.endswith("__init__"):
                    full_key = f"{wf.domain_path}/__init__".strip("/")
                else:
                    full_key = f"{wf.domain_path}/{wf.workflow_id}".strip("/")

                self._workflows[full_key] = wf
                log.info(f"[PHYSICAL INDEX] {rel_path} -> domain_path: '{wf.domain_path}' | name: '{wf.workflow_name}'")
            except Exception as e:
                log.error(f"[REGISTRY ERROR] Failed loading '{json_file}': {str(e)}")

    def get(self, key: str) -> Optional[WorkflowConfig]:
        """Retrieves a workflow by full key or workflow_id."""
        if not key:
            return None

        if key in self._workflows:
            return self._workflows[key]

        for full_key, wf in self._workflows.items():
            if wf.workflow_id == key or full_key.endswith(f"/{key}"):
                return wf

        return None

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowConfig]:
        return self.get(workflow_id)

    def list_tree(self) -> Dict[str, Any]:
        """Builds directory hierarchy matching physical folder layout."""
        tree: Dict[str, Any] = {}
        for key, wf in self._workflows.items():
            if wf.workflow_type == "init" or wf.workflow_id.endswith("__init__"):
                continue

            folder_parts = [p for p in wf.domain_path.split("/") if p and p != "."]
            curr = tree
            for part in folder_parts:
                curr = curr.setdefault(part, {})

            curr.setdefault("__workflows__", []).append(wf)
        return tree

    def list_workflows_grouped(self) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for key, wf in self._workflows.items():
            if wf.workflow_type == "init" or wf.workflow_id.endswith("__init__"):
                continue
            cat = wf.domain_path or "general"
            grouped.setdefault(cat, []).append(wf.workflow_id)
        return grouped