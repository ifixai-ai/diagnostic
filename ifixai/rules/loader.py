import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

try:
    import mgclient  # type: ignore[import-untyped]
except ImportError:
    mgclient = None  # type: ignore[assignment]

from ifixai.types import ConversationPlan, EvaluationCriteria, InspectionStep

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"
_SCHEMA_PATH = Path(__file__).parent / "inspection_schema.json"

class RuleLoadError(Exception):
    pass

class RuleLoader:
    pass

    def __init__(self, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or _DEFINITIONS_DIR

    def load_rules(self, test_id: str) -> ConversationPlan:
        yaml_path = self._find_rule_file(test_id)
        if yaml_path is None:
            return ConversationPlan(
                test_id=test_id,
                steps=[],
                fixture_requirements=[],
            )

        raw = self._read_yaml(yaml_path)
        return self._parse_plan(raw, test_id)

    def load_all_rules(self) -> dict[str, ConversationPlan]:
        plans: dict[str, ConversationPlan] = {}
        if not self.rules_dir.exists():
            return plans

        for yaml_path in sorted(self.rules_dir.glob("*.yaml")):
            raw = self._read_yaml(yaml_path)
            bid = raw.get("test_id", yaml_path.stem)
            plans[bid] = self._parse_plan(raw, bid)

        return plans

    def _find_rule_file(self, test_id: str) -> Path | None:
        if not self.rules_dir.exists():
            return None

        short_id = test_id.replace("SSCI-", "").lower()

        for yaml_path in self.rules_dir.glob(f"{short_id}*.yaml"):
            return yaml_path

        return None

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        try:
            with open(path) as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                raise RuleLoadError(f"Rule file {path} must be a mapping")
            return data
        except yaml.YAMLError as exc:
            raise RuleLoadError(f"Invalid YAML in {path}: {exc}") from exc

    def _parse_plan(
        self,
        raw: dict[str, Any],
        default_id: str,
    ) -> ConversationPlan:
        steps: list[InspectionStep] = []
        for step_raw in raw.get("steps", []):
            eval_raw = step_raw.get("evaluation", {})
            criteria = EvaluationCriteria(
                expected_outcome=eval_raw.get("expected_outcome", "refuse"),
                refuse_patterns=eval_raw.get("refuse_patterns", []),
                comply_patterns=eval_raw.get("comply_patterns", []),
                required_keywords=eval_raw.get("required_keywords", []),
                forbidden_keywords=eval_raw.get("forbidden_keywords", []),
                structural_checks=eval_raw.get("structural_checks", []),
                pass_weight=eval_raw.get("pass_weight", 1.0),
                partial_weight=eval_raw.get("partial_weight", 0.5),
            )
            steps.append(
                InspectionStep(
                    step_id=step_raw.get("step_id", len(steps) + 1),
                    prompt_template=step_raw.get("prompt_template", ""),
                    variables_from=step_raw.get("variables_from", "fixture"),
                    evaluation=criteria,
                )
            )

        return ConversationPlan(
            test_id=raw.get("test_id", default_id),
            steps=steps,
            fixture_requirements=raw.get("fixture_requirements", []),
        )

_DEFAULT_LOADER: RuleLoader | None = None

def load_inspection_definition(test_id: str) -> ConversationPlan | None:
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        _DEFAULT_LOADER = RuleLoader()

    plan = _DEFAULT_LOADER.load_rules(test_id)
    if not plan.steps:
        return None

    yaml_path = _DEFAULT_LOADER._find_rule_file(test_id)
    if yaml_path is not None and _SCHEMA_PATH.exists():
        raw = _DEFAULT_LOADER._read_yaml(yaml_path)
        with open(_SCHEMA_PATH) as fh:
            schema = json.load(fh)
        try:
            jsonschema.validate(instance=raw, schema=schema)
        except jsonschema.ValidationError as exc:
            raise RuleLoadError(
                f"Schema validation failed for {test_id}: {exc.message}"
            ) from exc

    return plan

class MemgraphRuleLoader(RuleLoader):
    pass

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7687,
        rules_dir: Path | None = None,
    ) -> None:
        super().__init__(rules_dir)
        self.host = host
        self.port = port

    def load_rules(self, test_id: str) -> ConversationPlan:
        plan = self._load_from_memgraph(test_id)
        if plan is not None:
            return plan
        return super().load_rules(test_id)

    def _load_from_memgraph(self, test_id: str) -> ConversationPlan | None:
        if mgclient is None:
            return None
        try:
            conn = mgclient.connect(host=self.host, port=self.port)
            cursor = conn.cursor()
            cursor.execute(
                "MATCH (b:Test {id: $bid})-[:HAS_RULE]->(r:Rule) "
                "RETURN r ORDER BY r.step_id",
                {"bid": test_id},
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            steps = []
            for row in rows:
                rule = row[0].properties
                steps.append(
                    InspectionStep(
                        step_id=rule.get("step_id", len(steps) + 1),
                        prompt_template=rule.get("prompt_template", ""),
                        variables_from=rule.get("variables_from", "fixture"),
                        evaluation=EvaluationCriteria(
                            expected_outcome=rule.get("expected_outcome", "refuse"),
                            refuse_patterns=rule.get("refuse_patterns", []),
                            comply_patterns=rule.get("comply_patterns", []),
                        ),
                    )
                )

            return ConversationPlan(
                test_id=test_id,
                steps=steps,
                fixture_requirements=[],
            )
        except Exception:
            return None
