"""
agentflight.policy
==================
Runtime Agent Policy Firewall & Cassette Security Auditor (`TrajectoryPolicyEngine`).

Evaluates live tool/MCP invocations and recorded trajectories against deterministic
safety, security, and governance policies:
- `PF001`: Explicit actor blocklist / allowlist enforcement
- `PF002`: Destructive or state-mutating tool invocation gate
- `PF003`: SSRF / cloud-metadata / private-network target blocking in tool inputs
- `PF004`: Path-traversal and sensitive host file access blocking
- `PF005`: Destructive SQL command interception (`DROP`, `TRUNCATE`, unguarded `DELETE`)
- `PF006`: Live secret/credential exfiltration prevention (reuses `agentflight.redact`)
- `PF007`: Per-flight state-mutation ceiling enforcement
- Custom Python predicates via `PolicyRule` / `add_rule()`
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from .recorder import FlightRecorder, SpanKind, TrajectorySpan, verify_cassette
from .redact import contains_sensitive_data

PolicyAction = Literal["allow", "warn", "block"]
PolicyMode = Literal["standard", "strict", "read-only"]

MUTATION_ACTOR_RE = re.compile(
    r"(?:^|[._\-/])(delete|remove|drop|destroy|truncate|wipe|rm|unlink|exec|shell|"
    r"run_command|transfer|wire|charge|refund|pay|deploy|publish|write|update|patch|modify|kill)"
    r"(?:$|[._\-/])",
    re.IGNORECASE,
)

SSRF_TARGET_RE = re.compile(
    r"(?:https?://(?:localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|0\.0\.0\.0|"
    r"169\.254\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"\[::1\]|metadata\.google\.internal)\b|"
    r"\b169\.254\.169\.254\b|\bmetadata\.google\.internal\b)",
    re.IGNORECASE,
)

PATH_TRAVERSAL_RE = re.compile(
    r"(?:(?:\.\./){1,}|(?:\.\.\\){1,}|/etc/passwd\b|/etc/shadow\b|"
    r"~?/\.ssh/id_[a-z0-9_]+|(?:/|\\)\.aws[/\\]credentials\b)",
    re.IGNORECASE,
)

DESTRUCTIVE_SQL_RE = re.compile(
    r"(?:\bDROP\s+(?:TABLE|DATABASE|SCHEMA|VIEW)\b|"
    r"\bTRUNCATE\s+(?:TABLE\s+)?[A-Za-z0-9_.\"']+)",
    re.IGNORECASE,
)

UNGUARDED_SQL_DELETE_RE = re.compile(
    r"\bDELETE\s+FROM\s+[A-Za-z0-9_.\"']+\s*(?:;|$)",
    re.IGNORECASE,
)

PolicyPredicate = Callable[[str, Mapping[str, Any], SpanKind], Optional[str]]


class PolicyViolationError(RuntimeError):
    """Raised when `TrajectoryPolicyEngine` blocks an unsafe or unauthorized agent action."""

    def __init__(
        self,
        message: str,
        *,
        rule_id: str,
        actor: str,
        step_index: int = 0,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.actor = actor
        self.step_index = step_index
        self.evidence = evidence or {}


@dataclass(frozen=True)
class PolicyRule:
    """Custom runtime policy rule evaluated against every candidate agent step."""

    rule_id: str
    description: str
    predicate: PolicyPredicate
    severity: Literal["warn", "block"] = "block"


@dataclass
class PolicyViolation:
    """Structured finding emitted when a policy rule matches an agent action."""

    rule_id: str
    severity: Literal["warn", "block"]
    actor: str
    step_index: int
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyDecision:
    """Result returned by `TrajectoryPolicyEngine.evaluate()`."""

    allowed: bool
    action: PolicyAction
    actor: str
    step_index: int
    is_mutation: bool
    violations: List[PolicyViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "actor": self.actor,
            "step_index": self.step_index,
            "is_mutation": self.is_mutation,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclass
class PolicyAuditReport:
    """Offline policy audit report across all spans in a cassette."""

    agent_id: str
    mode: PolicyMode
    steps_scanned: int
    mutation_count: int
    violation_count: int
    block_count: int
    warn_count: int
    passed: bool
    is_hash_chain_valid: bool
    violations: List[PolicyViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "mode": self.mode,
            "steps_scanned": self.steps_scanned,
            "mutation_count": self.mutation_count,
            "violation_count": self.violation_count,
            "block_count": self.block_count,
            "warn_count": self.warn_count,
            "passed": self.passed,
            "is_hash_chain_valid": self.is_hash_chain_valid,
            "violations": [v.to_dict() for v in self.violations],
        }

    def to_markdown(self) -> str:
        """Render a concise Markdown policy audit summary."""
        status_badge = "PASS (CLEAN)" if self.passed else "FAIL (POLICY BLOCKS TRIGGERED)"
        lines = [
            f"# AgentFlight Policy Firewall Audit: `{self.agent_id}`",
            "",
            "| Check | Result |",
            "| :--- | :--- |",
            f"| **Policy Mode** | `{self.mode}` |",
            f"| **Overall Verdict** | `{status_badge}` |",
            f"| **Steps Scanned** | `{self.steps_scanned}` (`{self.mutation_count}` mutations) |",
            f"| **Violations** | `{self.violation_count}` (`{self.block_count}` block, `{self.warn_count}` warn) |",
            f"| **Hash Chain Valid** | `{self.is_hash_chain_valid}` |",
        ]
        if self.violations:
            lines.extend([
                "",
                "| Step | Rule | Severity | Actor | Message |",
                "| :---: | :--- | :---: | :--- | :--- |",
            ])
            for v in self.violations:
                lines.append(
                    f"| {v.step_index} | `{v.rule_id}` | `{v.severity.upper()}` | `{v.actor}` | {v.message} |"
                )
        return "\n".join(lines)


def _iter_strings(value: Any, path: str = "$") -> Iterable[Tuple[str, str]]:
    """Yield `(json_path, string_value)` pairs recursively from nested JSON-like values."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for k, v in value.items():
            yield from _iter_strings(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            yield from _iter_strings(item, f"{path}[{idx}]")


def _default_max_mutations(mode: PolicyMode) -> Optional[int]:
    if mode == "read-only":
        return 0
    if mode == "strict":
        return 5
    return None


def _coerce_cassette_spans(
    cassette: Union[FlightRecorder, Sequence[TrajectorySpan], Mapping[str, Any], str, Path],
) -> Tuple[str, List[TrajectorySpan], bool]:
    """Load spans, `agent_id`, and hash-chain validity from any supported cassette source."""
    if isinstance(cassette, (str, Path)):
        if isinstance(cassette, str) and cassette.lstrip().startswith("{"):
            data = json.loads(cassette)
            return _coerce_cassette_spans(data)
        rec = FlightRecorder.load(cassette, verify=False)
        try:
            chain_ok = bool(verify_cassette(rec))
        except Exception:
            chain_ok = False
        return rec.agent_id, rec.spans, chain_ok

    if isinstance(cassette, FlightRecorder):
        try:
            chain_ok = bool(verify_cassette(cassette))
        except Exception:
            chain_ok = False
        return cassette.agent_id, cassette.spans, chain_ok

    if isinstance(cassette, Mapping):
        data_dict = dict(cassette)
        agent_id = str(data_dict.get("agent_id", "unknown-agent"))
        spans = [
            sp if isinstance(sp, TrajectorySpan) else TrajectorySpan.from_dict(dict(sp))
            for sp in data_dict.get("spans", [])
        ]
        try:
            chain_ok = bool(verify_cassette(data_dict))
        except Exception:
            chain_ok = False
        return agent_id, spans, chain_ok

    spans_list = list(cassette)
    try:
        chain_ok = bool(verify_cassette(spans_list))
    except Exception:
        chain_ok = False
    return "sequence-agent", spans_list, chain_ok


class TrajectoryPolicyEngine:
    """
    Deterministic policy firewall evaluating agent tool/MCP calls and cassettes.
    """

    def __init__(
        self,
        *,
        mode: PolicyMode = "standard",
        max_mutations: Optional[int] = None,
        allowed_actors: Optional[Sequence[str]] = None,
        blocked_actors: Optional[Sequence[str]] = None,
        block_secret_exfiltration: bool = True,
        block_ssrf: bool = True,
        block_path_traversal: bool = True,
        block_destructive_sql: bool = True,
        custom_rules: Optional[Sequence[PolicyRule]] = None,
    ) -> None:
        if mode not in ("standard", "strict", "read-only"):
            raise ValueError(f"Unsupported policy mode: {mode!r}")
        self.mode: PolicyMode = mode
        self.max_mutations: Optional[int] = (
            _default_max_mutations(mode) if max_mutations is None else max_mutations
        )
        self.allowed_actors = frozenset(allowed_actors) if allowed_actors is not None else None
        self.blocked_actors = frozenset(blocked_actors or ())
        self.block_secret_exfiltration = block_secret_exfiltration
        self.block_ssrf = block_ssrf
        self.block_path_traversal = block_path_traversal
        self.block_destructive_sql = block_destructive_sql
        self._custom_rules: List[PolicyRule] = list(custom_rules or ())
        self._steps_evaluated = 0
        self._mutation_count = 0

    @property
    def mutation_count(self) -> int:
        return self._mutation_count

    def reset(self) -> None:
        """Reset per-flight counters (`steps_evaluated`, `mutation_count`)."""
        self._steps_evaluated = 0
        self._mutation_count = 0

    def add_rule(
        self,
        rule_id: str,
        predicate: PolicyPredicate,
        *,
        severity: Literal["warn", "block"] = "block",
        description: str = "",
    ) -> None:
        """Register an additional custom policy rule."""
        self._custom_rules.append(
            PolicyRule(
                rule_id=rule_id,
                description=description or rule_id,
                predicate=predicate,
                severity=severity,
            )
        )

    @staticmethod
    def is_mutating_actor(actor: str) -> bool:
        """Return True if an actor/tool name denotes a state-mutating or destructive operation."""
        return bool(MUTATION_ACTOR_RE.search(actor or ""))

    def _scan_payload_patterns(
        self,
        actor: str,
        payload: Mapping[str, Any],
        step_index: int,
    ) -> List[PolicyViolation]:
        violations: List[PolicyViolation] = []
        for path, text in _iter_strings(payload):
            if self.block_ssrf and SSRF_TARGET_RE.search(text):
                violations.append(
                    PolicyViolation(
                        rule_id="PF003",
                        severity="block",
                        actor=actor,
                        step_index=step_index,
                        message=f"Blocked SSRF/private-network target in `{path}`.",
                        evidence={"path": path},
                    )
                )
            if self.block_path_traversal and PATH_TRAVERSAL_RE.search(text):
                violations.append(
                    PolicyViolation(
                        rule_id="PF004",
                        severity="block",
                        actor=actor,
                        step_index=step_index,
                        message=f"Blocked path traversal or sensitive host path in `{path}`.",
                        evidence={"path": path},
                    )
                )
            if self.block_destructive_sql and (
                DESTRUCTIVE_SQL_RE.search(text) or UNGUARDED_SQL_DELETE_RE.search(text)
            ):
                violations.append(
                    PolicyViolation(
                        rule_id="PF005",
                        severity="block",
                        actor=actor,
                        step_index=step_index,
                        message=f"Blocked destructive SQL statement in `{path}`.",
                        evidence={"path": path},
                    )
                )

        if self.block_secret_exfiltration and contains_sensitive_data(dict(payload)):
            violations.append(
                PolicyViolation(
                    rule_id="PF006",
                    severity="block",
                    actor=actor,
                    step_index=step_index,
                    message="Blocked unredacted credential or API secret in tool arguments.",
                    evidence={"keys": sorted(str(k) for k in payload.keys())},
                )
            )
        return violations

    def evaluate(
        self,
        actor: str,
        input_payload: Optional[Mapping[str, Any]] = None,
        *,
        kind: SpanKind = "tool_call",
        step_index: Optional[int] = None,
        raise_on_block: bool = False,
    ) -> PolicyDecision:
        """
        Evaluate a candidate agent action before execution.
        When `raise_on_block=True`, raises `PolicyViolationError` on the first blocking violation.
        """
        payload: Mapping[str, Any] = input_payload if input_payload is not None else {}
        idx = self._steps_evaluated if step_index is None else step_index
        self._steps_evaluated += 1

        is_mutation = kind in ("tool_call", "mcp_rpc") and self.is_mutating_actor(actor)
        projected_mutations = self._mutation_count + (1 if is_mutation else 0)
        violations: List[PolicyViolation] = []

        # PF001: Explicit actor allowlist / blocklist
        if actor in self.blocked_actors or (
            self.allowed_actors is not None and actor not in self.allowed_actors
        ):
            violations.append(
                PolicyViolation(
                    rule_id="PF001",
                    severity="block",
                    actor=actor,
                    step_index=idx,
                    message=f"Actor '{actor}' is denied by repository policy allowlist/blocklist.",
                    evidence={"actor": actor},
                )
            )

        # PF002 & PF007: Destructive/mutation gates and mutation ceilings
        if is_mutation:
            if self.mode == "read-only":
                violations.append(
                    PolicyViolation(
                        rule_id="PF002",
                        severity="block",
                        actor=actor,
                        step_index=idx,
                        message=f"Mutating actor '{actor}' blocked in read-only policy mode.",
                        evidence={"mode": self.mode},
                    )
                )
            elif self.mode == "strict":
                violations.append(
                    PolicyViolation(
                        rule_id="PF002",
                        severity="warn",
                        actor=actor,
                        step_index=idx,
                        message=f"High-risk mutating actor '{actor}' flagged in strict policy mode.",
                        evidence={"mode": self.mode},
                    )
                )

            if self.max_mutations is not None and projected_mutations > self.max_mutations:
                violations.append(
                    PolicyViolation(
                        rule_id="PF007",
                        severity="block",
                        actor=actor,
                        step_index=idx,
                        message=(
                            f"Mutation budget exceeded at step {idx}: "
                            f"{projected_mutations} mutations > limit {self.max_mutations}."
                        ),
                        evidence={
                            "projected_mutations": projected_mutations,
                            "max_mutations": self.max_mutations,
                        },
                    )
                )

        # PF003..PF006: Argument payload security checks
        violations.extend(self._scan_payload_patterns(actor, payload, idx))

        # Custom predicates
        for rule in self._custom_rules:
            reason = rule.predicate(actor, payload, kind)
            if reason:
                violations.append(
                    PolicyViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        actor=actor,
                        step_index=idx,
                        message=reason,
                        evidence={"rule_description": rule.description},
                    )
                )

        blocking = [v for v in violations if v.severity == "block"]
        if not blocking and is_mutation:
            self._mutation_count = projected_mutations

        action: PolicyAction = "block" if blocking else ("warn" if violations else "allow")
        decision = PolicyDecision(
            allowed=not blocking,
            action=action,
            actor=actor,
            step_index=idx,
            is_mutation=is_mutation,
            violations=violations,
        )

        if blocking and raise_on_block:
            first = blocking[0]
            raise PolicyViolationError(
                first.message,
                rule_id=first.rule_id,
                actor=actor,
                step_index=idx,
                evidence=first.evidence,
            )

        return decision

    def audit_cassette(
        self,
        cassette: Union[FlightRecorder, Sequence[TrajectorySpan], Mapping[str, Any], str, Path],
    ) -> PolicyAuditReport:
        """Scan every recorded span in a cassette non-destructively with a fresh counter pass."""
        agent_id, spans, chain_ok = _coerce_cassette_spans(cassette)
        clone = TrajectoryPolicyEngine(
            mode=self.mode,
            max_mutations=self.max_mutations,
            allowed_actors=sorted(self.allowed_actors) if self.allowed_actors is not None else None,
            blocked_actors=sorted(self.blocked_actors),
            block_secret_exfiltration=self.block_secret_exfiltration,
            block_ssrf=self.block_ssrf,
            block_path_traversal=self.block_path_traversal,
            block_destructive_sql=self.block_destructive_sql,
            custom_rules=self._custom_rules,
        )

        all_violations: List[PolicyViolation] = []
        for span in spans:
            decision = clone.evaluate(
                span.actor,
                span.input_payload,
                kind=span.kind,
                step_index=span.step_index,
                raise_on_block=False,
            )
            all_violations.extend(decision.violations)

        block_count = sum(1 for v in all_violations if v.severity == "block")
        warn_count = sum(1 for v in all_violations if v.severity == "warn")
        return PolicyAuditReport(
            agent_id=agent_id,
            mode=self.mode,
            steps_scanned=len(spans),
            mutation_count=clone.mutation_count,
            violation_count=len(all_violations),
            block_count=block_count,
            warn_count=warn_count,
            passed=(block_count == 0),
            is_hash_chain_valid=chain_ok,
            violations=all_violations,
        )
