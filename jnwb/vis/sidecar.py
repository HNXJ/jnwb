"""
jnwb.vis.sidecar -- Epistemic argument object serialization and schema enforcement.

Validates and writes the machine-readable sidecar (*_argument.json) that accompanies every
figure jnwb.vis exports. It holds eight fields:
1. QUESTION: Explicit hypothesis or scientific question addressed.
2. DATA: Underlying empirical dataset, recording modality, sample counts, and QC filters.
3. ESTIMAND: Mathematical definition of the plotted metric.
4. INFERENCE UNIT: Statistical unit of replication (e.g. sessions, animals, units).
5. RESULT: Quantitative findings with exact effect sizes, test statistics, and p-values.
6. LICENSED CLAIM: Specific scientific inferences strictly warranted by the evidence.
7. BARRED CLAIM: Specific over-interpretations or unsupported inferences explicitly prohibited.
8. SOURCE ARTIFACTS: Canonical source file paths, hashes, or script locations.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union


@dataclass
class EpistemicArgumentObject:
    """Canonical 8-field epistemic argument object for scientific figures."""

    QUESTION: str
    DATA: str
    ESTIMAND: str
    INFERENCE_UNIT: str
    RESULT: str
    LICENSED_CLAIM: str
    BARRED_CLAIM: str
    SOURCE_ARTIFACTS: List[str] = field(default_factory=list)
    METADATA: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate that all required string fields are non-empty
        str_fields = {
            "QUESTION": self.QUESTION,
            "DATA": self.DATA,
            "ESTIMAND": self.ESTIMAND,
            "INFERENCE UNIT": self.INFERENCE_UNIT,
            "RESULT": self.RESULT,
            "LICENSED CLAIM": self.LICENSED_CLAIM,
            "BARRED CLAIM": self.BARRED_CLAIM,
        }
        for name, val in str_fields.items():
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"EpistemicArgumentObject: '{name}' must be a non-empty string.")

        if not isinstance(self.SOURCE_ARTIFACTS, (list, tuple)) or len(self.SOURCE_ARTIFACTS) == 0:
            raise ValueError("EpistemicArgumentObject: 'SOURCE ARTIFACTS' must be a non-empty list of paths/hashes.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to canonical dictionary format."""
        d = {
            "QUESTION": self.QUESTION.strip(),
            "DATA": self.DATA.strip(),
            "ESTIMAND": self.ESTIMAND.strip(),
            "INFERENCE UNIT": self.INFERENCE_UNIT.strip(),
            "RESULT": self.RESULT.strip(),
            "LICENSED CLAIM": self.LICENSED_CLAIM.strip(),
            "BARRED CLAIM": self.BARRED_CLAIM.strip(),
            "SOURCE ARTIFACTS": [str(a).strip() for a in self.SOURCE_ARTIFACTS],
        }
        if self.METADATA:
            d["METADATA"] = self.METADATA
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, filepath: Union[str, Path]) -> Path:
        """Save to JSON file on disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> EpistemicArgumentObject:
        """Construct from dictionary, supporting both underscored and spaced keys."""
        q = d.get("QUESTION", "")
        data = d.get("DATA", "")
        estimand = d.get("ESTIMAND", "")
        inf_unit = d.get("INFERENCE UNIT", d.get("INFERENCE_UNIT", ""))
        res = d.get("RESULT", "")
        lic_claim = d.get("LICENSED CLAIM", d.get("LICENSED_CLAIM", ""))
        bar_claim = d.get("BARRED CLAIM", d.get("BARRED_CLAIM", ""))
        src = d.get("SOURCE ARTIFACTS", d.get("SOURCE_ARTIFACTS", []))
        meta = d.get("METADATA", {})

        return cls(
            QUESTION=q,
            DATA=data,
            ESTIMAND=estimand,
            INFERENCE_UNIT=inf_unit,
            RESULT=res,
            LICENSED_CLAIM=lic_claim,
            BARRED_CLAIM=bar_claim,
            SOURCE_ARTIFACTS=list(src),
            METADATA=meta,
        )

    @classmethod
    def from_json(cls, json_str: str) -> EpistemicArgumentObject:
        """Parse from JSON string."""
        d = json.loads(json_str)
        return cls.from_dict(d)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> EpistemicArgumentObject:
        """Load from JSON file on disk."""
        path = Path(filepath)
        return cls.from_json(path.read_text(encoding="utf-8"))


def serialize_argument_sidecar(
    output_path: Union[str, Path],
    argument_data: Union[Dict[str, Any], EpistemicArgumentObject],
) -> Path:
    """Helper to validate and write an epistemic argument sidecar JSON."""
    if isinstance(argument_data, EpistemicArgumentObject):
        obj = argument_data
    else:
        obj = EpistemicArgumentObject.from_dict(argument_data)
    return obj.save(output_path)
