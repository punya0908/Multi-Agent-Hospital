import re
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from backend.config.settings import settings
from backend.schemas.workflow_state import SafetyAssessment


class SafetyRuleService:
    def __init__(self, rules_path: Optional[Path] = None) -> None:
        self.rules_path = rules_path or settings.SAFETY_RULES_PATH
        with open(self.rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.negation_prefixes: List[str] = [
            p.lower() for p in data.get("negation_prefixes", [])
        ]
        self.urgent_keywords: List[Dict[str, str]] = data.get("urgent_keywords", [])
        self.uncertain_keywords: List[Dict[str, str]] = data.get("uncertain_keywords", [])

    def _is_negated(self, text_lower: str, match_start: int) -> bool:
        clause_start = max(
            (text_lower.rfind(sep, 0, match_start) for sep in (",", ".", ";", "!", "?")),
            default=-1,
        ) + 1
        preceding_in_clause = text_lower[clause_start:match_start]

        for prefix in self.negation_prefixes:
            pattern = rf"(?:^|\s){re.escape(prefix)}$"
            if re.search(pattern, preceding_in_clause):
                return True
        return False

    def _find_unnegated_matches(
        self, text_lower: str, rules: List[Dict[str, str]]
    ) -> List[str]:
        matched_rule_ids: List[str] = []
        for rule in rules:
            rule_id = rule["rule_id"]
            keyword = rule["keyword"].lower().strip()
            pattern = rf"\b{re.escape(keyword)}\b"

            for match in re.finditer(pattern, text_lower):
                if not self._is_negated(text_lower, match.start()):
                    if rule_id not in matched_rule_ids:
                        matched_rule_ids.append(rule_id)
                    break
        return matched_rule_ids

    def evaluate(self, text: str) -> SafetyAssessment:
        normalized_text = re.sub(r"\s+", " ", text.lower()).strip()

        urgent_matches = self._find_unnegated_matches(
            normalized_text, self.urgent_keywords
        )
        if urgent_matches:
            return SafetyAssessment(
                status="URGENT",
                matched_rules=urgent_matches,
                advisory_message=(
                    "Potential urgent red-flag phrase detected. Please seek immediate "
                    "emergency medical care or call your local emergency number right away."
                ),
                requires_immediate_care=True,
            )

        uncertain_matches = self._find_unnegated_matches(
            normalized_text, self.uncertain_keywords
        )
        if uncertain_matches:
            return SafetyAssessment(
                status="UNCERTAIN",
                matched_rules=uncertain_matches,
                advisory_message=(
                    "Your description includes ambiguous or potentially concerning symptoms. "
                    "Please speak with a healthcare professional or triage nurse promptly."
                ),
                requires_immediate_care=False,
            )

        return SafetyAssessment(
            status="CLEAR",
            matched_rules=[],
            advisory_message="No urgent red-flag keywords detected in intake description.",
            requires_immediate_care=False,
        )