import json
from pathlib import Path
from typing import Dict, Optional
from config.settings import settings
from core.common.exceptions import WorkflowValidationError
from core.common.schemas import WorkflowConfig
from core.registry.validator import WorkflowValidator
from core.common.logger import log


class WorkflowRegistry:
    """Master catalog registry loader managing declarative JSON workflow configurations."""

    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or (settings.WORKFLOWS_DIR / "catalog.json")
        self._registry: Dict[str, Path] = {}
        self._load_catalog()

    def _load_catalog(self):
        """Scans catalog.json and registers all workflow configuration paths."""
        if not self.catalog_path.exists():
            log.warning(f"Catalog file not found at {self.catalog_path}. Initializing empty registry.")
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                catalog_data = json.load(f)

            workflows = catalog_data.get("workflows", {})
            for w_id, rel_path in workflows.items():
                full_path = settings.WORKFLOWS_DIR / rel_path
                self._registry[w_id] = full_path

            log.info(f"Registered {len(self._registry)} workflows from catalog.")

        except Exception as e:
            raise WorkflowValidationError(f"Failed to initialize WorkflowRegistry: {str(e)}")

    def get_workflow(self, workflow_id: str) -> WorkflowConfig:
        """Fetches and validates a registered workflow by its ID."""
        if workflow_id not in self._registry:
            raise WorkflowValidationError(f"Workflow ID '{workflow_id}' is not registered in catalog.")

        file_path = self._registry[workflow_id]
        return WorkflowValidator.validate_file(str(file_path))

    def register_workflow_path(self, workflow_id: str, path: Path):
        """Manually registers or overrides a workflow path at runtime."""
        self._registry[workflow_id] = path