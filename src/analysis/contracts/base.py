import dataclasses
from typing import List, Any
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

class ContractMixin:
    """Base mixin to share serialization and common validation logic across contracts."""
    
    def to_dict(self) -> dict:
        """Serialize dataclass to a dictionary."""
        return dataclasses.asdict(self)

    def _validate_required_fields(self, required_fields: List[str]) -> List[str]:
        """Validate that all required fields are present and not empty/None."""
        errors = []
        for field_name in required_fields:
            val = getattr(self, field_name, None)
            if field_name == "data":
                if val is None:
                    errors.append("Field 'data' is required.")
            else:
                if not val:
                    if field_name == "subject":
                        errors.append("Subject is required.")
                    elif field_name == "session_id":
                        errors.append("Session ID is required.")
                    elif field_name == "truth_status":
                        errors.append("Truth status must be specified.")
                    else:
                        errors.append(f"Field '{field_name}' is required.")
        return errors

    def _validate_truth_status(self) -> List[str]:
        """Ensure truth_status matches the required truth-safe value."""
        errors = []
        if not hasattr(self, "truth_status") or not self.truth_status:
            errors.append("Truth status must be specified.")
        elif self.truth_status != TRUTH_SAFE_UNVERIFIED:
            errors.append(f"Truth status must remain '{TRUTH_SAFE_UNVERIFIED}' under Phase 2 doctrine.")
        return errors
