"""
agentflight.assertions
======================
Declarative Behavioral Trajectory Contracts & CI/Pytest Assertions (`FlightContract`).

Allows developers and CI pipelines to assert behavioral invariants over recorded or
replayed AI agent trajectories:
- `must_call(actor, min_calls=1, max_calls=None)`
- `must_not_call(actor)`
- `must_follow_order(actors)` (ordered subsequence check)
- `max_steps(limit)`, `max_cost_usd(limit)`, `max_tokens(limit)`
- `max_total_latency_ms(limit)`, `max_step_latency_ms(limit)`
- `max_error_rate(ratio)`, `zero_errors()`
- `require_valid_hash_chain()`, `require_no_secret_leaks()`
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .policy import _coerce_cassette_spans
from .recorder import FlightRecorder, TrajectorySpan
from .redact import contains_sensitive_data


@dataclass
class RuleResult:
    """Evaluation outcome for a single behavioral contract rule."""

    rule_name: str
    passed: bool
    expected: str
    actual: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContractReport:
    """Aggregate pass/fail evaluation report for a `FlightContract`."""

    contract_name: str
    agent_id: str
    passed: bool
    score: float
    total_rules: int
    passed_rules: int
    failed_rules: int
    steps_evaluated: int
    results: List[RuleResult] = field(default_factory=list)

    def assert_passed(self) -> "ContractReport":
        """Raise `AssertionError` with failed rule details if any contract rule failed."""
        if not self.passed:
            failures = [f"- {r.rule_name}: {r.message}" for r in self.results if not r.passed]
            raise AssertionError(
                f"FlightContract '{self.contract_name}' failed for agent '{self.agent_id}':\n"
                + "\n".join(failures)
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_name": self.contract_name,
            "agent_id": self.agent_id,
            "passed": self.passed,
            "score": self.score,
            "total_rules": self.total_rules,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "steps_evaluated": self.steps_evaluated,
            "results": [r.to_dict() for r in self.results],
        }

    def to_markdown(self) -> str:
        """Render a Markdown behavioral contract report."""
        verdict = "PASS" if self.passed else "FAIL"
        lines = [
            f"# AgentFlight Behavioral Contract: `{self.contract_name}`",
            "",
            f"**Agent:** `{self.agent_id}` | **Verdict:** `{verdict}` | "
            f"**Score:** `{self.score:.1f}/100` ({self.passed_rules}/{self.total_rules} rules passed)",
            "",
            "| Rule | Status | Expected | Actual |",
            "| :--- | :---: | :--- | :--- |",
        ]
        for r in self.results:
            status_cell = "PASS" if r.passed else "FAIL"
            lines.append(f"| `{r.rule_name}` | {status_cell} | {r.expected} | {r.actual} |")
        return "\n".join(lines)


class FlightContract:
    """
    Fluent and JSON-serializable behavioral contract for AI agent trajectories.
    """

    def __init__(self, name: str = "default-flight-contract") -> None:
        self.name = name
        self._must_call: Dict[str, Dict[str, Optional[int]]] = {}
        self._must_not_call: List[str] = []
        self._order_sequences: List[List[str]] = []
        self._max_steps: Optional[int] = None
        self._max_cost_usd: Optional[float] = None
        self._max_tokens: Optional[int] = None
        self._max_total_latency_ms: Optional[float] = None
        self._max_step_latency_ms: Optional[float] = None
        self._max_error_rate: Optional[float] = None
        self._require_valid_hash_chain: bool = True
        self._require_no_secret_leaks: bool = False

    def must_call(
        self,
        actor: str,
        *,
        min_calls: int = 1,
        max_calls: Optional[int] = None,
    ) -> "FlightContract":
        """Require `actor` to be invoked within `[min_calls, max_calls]`."""
        self._must_call[actor] = {"min_calls": int(min_calls), "max_calls": max_calls}
        return self

    def must_not_call(self, actor: str) -> "FlightContract":
        """Forbid any invocation of `actor` during the trajectory."""
        if actor not in self._must_not_call:
            self._must_not_call.append(actor)
        return self

    def must_follow_order(self, actors: Sequence[str]) -> "FlightContract":
        """Require actors to appear as an ordered subsequence in the trajectory."""
        seq = [str(a) for a in actors if str(a)]
        if seq:
            self._order_sequences.append(seq)
        return self

    def max_steps(self, limit: int) -> "FlightContract":
        """Require total trajectory steps <= `limit`."""
        self._max_steps = int(limit)
        return self

    def max_cost_usd(self, limit: float) -> "FlightContract":
        """Require cumulative USD cost <= `limit`."""
        self._max_cost_usd = float(limit)
        return self

    def max_tokens(self, limit: int) -> "FlightContract":
        """Require total tokens (prompt + completion) <= `limit`."""
        self._max_tokens = int(limit)
        return self

    def max_total_latency_ms(self, limit: float) -> "FlightContract":
        """Require total cumulative latency_ms <= `limit`."""
        self._max_total_latency_ms = float(limit)
        return self

    def max_step_latency_ms(self, limit: float) -> "FlightContract":
        """Require every individual step's latency_ms <= `limit`."""
        self._max_step_latency_ms = float(limit)
        return self

    def max_error_rate(self, ratio: float) -> "FlightContract":
        """Require `(error_steps / total_steps) <= ratio` (e.g. 0.0 to 1.0)."""
        self._max_error_rate = float(ratio)
        return self

    def zero_errors(self) -> "FlightContract":
        """Shortcut for `max_error_rate(0.0)`."""
        return self.max_error_rate(0.0)

    def require_valid_hash_chain(self, enabled: bool = True) -> "FlightContract":
        """Assert cassette cryptographic SHA-256 chain integrity."""
        self._require_valid_hash_chain = bool(enabled)
        return self

    def require_no_secret_leaks(self, enabled: bool = True) -> "FlightContract":
        """Assert no recorded span payloads contain unredacted credentials/secrets."""
        self._require_no_secret_leaks = bool(enabled)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize contract rules to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "must_call": dict(self._must_call),
            "must_not_call": list(self._must_not_call),
            "must_follow_order": [list(s) for s in self._order_sequences],
            "max_steps": self._max_steps,
            "max_cost_usd": self._max_cost_usd,
            "max_tokens": self._max_tokens,
            "max_total_latency_ms": self._max_total_latency_ms,
            "max_step_latency_ms": self._max_step_latency_ms,
            "max_error_rate": self._max_error_rate,
            "require_valid_hash_chain": self._require_valid_hash_chain,
            "require_no_secret_leaks": self._require_no_secret_leaks,
        }

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> "FlightContract":
        """Construct a `FlightContract` from a dictionary or JSON specification."""
        contract = cls(name=str(spec.get("name", "custom-flight-contract")))
        raw_must_call = spec.get("must_call") or {}
        if isinstance(raw_must_call, Mapping):
            for actor, bounds in raw_must_call.items():
                if isinstance(bounds, Mapping):
                    contract.must_call(
                        str(actor),
                        min_calls=int(bounds.get("min_calls", 1)),
                        max_calls=int(bounds["max_calls"]) if bounds.get("max_calls") is not None else None,
                    )
                elif isinstance(bounds, int):
                    contract.must_call(str(actor), min_calls=bounds)
                else:
                    contract.must_call(str(actor))
        elif isinstance(raw_must_call, Sequence) and not isinstance(raw_must_call, str):
            for actor in raw_must_call:
                contract.must_call(str(actor))

        for actor in spec.get("must_not_call") or ():
            contract.must_not_call(str(actor))

        raw_orders = spec.get("must_follow_order") or ()
        if isinstance(raw_orders, Sequence) and raw_orders:
            if isinstance(raw_orders[0], str):
                contract.must_follow_order([str(x) for x in raw_orders])
            else:
                for seq in raw_orders:
                    contract.must_follow_order([str(x) for x in seq])

        if spec.get("max_steps") is not None:
            contract.max_steps(int(spec["max_steps"]))
        if spec.get("max_cost_usd") is not None:
            contract.max_cost_usd(float(spec["max_cost_usd"]))
        if spec.get("max_tokens") is not None:
            contract.max_tokens(int(spec["max_tokens"]))
        if spec.get("max_total_latency_ms") is not None:
            contract.max_total_latency_ms(float(spec["max_total_latency_ms"]))
        if spec.get("max_step_latency_ms") is not None:
            contract.max_step_latency_ms(float(spec["max_step_latency_ms"]))
        if spec.get("max_error_rate") is not None:
            contract.max_error_rate(float(spec["max_error_rate"]))
        elif spec.get("zero_errors"):
            contract.zero_errors()
        if "require_valid_hash_chain" in spec:
            contract.require_valid_hash_chain(bool(spec["require_valid_hash_chain"]))
        if spec.get("require_no_secret_leaks"):
            contract.require_no_secret_leaks(True)
        return contract

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "FlightContract":
        """Load a `FlightContract` specification from a JSON file."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError(f"Contract file '{path}' must contain a JSON object.")
        return cls.from_dict(raw)

    def evaluate(
        self,
        cassette: Union[FlightRecorder, Sequence[TrajectorySpan], Mapping[str, Any], str, Path],
    ) -> ContractReport:
        """Evaluate every rule in this contract against the target trajectory cassette."""
        agent_id, spans, chain_ok = _coerce_cassette_spans(cassette)
        results: List[RuleResult] = []
        actors = [sp.actor for sp in spans]

        if self._require_valid_hash_chain:
            results.append(
                RuleResult(
                    rule_name="hash_chain_integrity",
                    passed=chain_ok,
                    expected="SHA-256 chain valid",
                    actual="valid" if chain_ok else "invalid/corrupted",
                    message=(
                        "Cassette SHA-256 chain verified."
                        if chain_ok
                        else "Cassette SHA-256 hash chain failed verification."
                    ),
                )
            )

        if self._require_no_secret_leaks:
            leaking_steps = [
                sp.step_index
                for sp in spans
                if contains_sensitive_data(sp.input_payload) or contains_sensitive_data(sp.output_payload)
            ]
            ok = not leaking_steps
            results.append(
                RuleResult(
                    rule_name="no_secret_leaks",
                    passed=ok,
                    expected="0 steps with unredacted credentials",
                    actual=f"{len(leaking_steps)} leaking steps",
                    message=(
                        "No unredacted secrets found."
                        if ok
                        else f"Found unredacted secrets at step(s): {leaking_steps}."
                    ),
                )
            )

        for actor, bounds in self._must_call.items():
            count = sum(1 for a in actors if a == actor)
            min_c = bounds.get("min_calls") or 1
            max_c = bounds.get("max_calls")
            ok = count >= min_c and (max_c is None or count <= max_c)
            expected_str = f">={min_c}" if max_c is None else f"{min_c}..{max_c}"
            results.append(
                RuleResult(
                    rule_name=f"must_call:{actor}",
                    passed=ok,
                    expected=f"{expected_str} call(s)",
                    actual=f"{count} call(s)",
                    message=(
                        f"Actor '{actor}' called {count} time(s)."
                        if ok
                        else f"Actor '{actor}' called {count} time(s), expected {expected_str}."
                    ),
                )
            )

        for actor in self._must_not_call:
            count = sum(1 for a in actors if a == actor)
            ok = count == 0
            results.append(
                RuleResult(
                    rule_name=f"must_not_call:{actor}",
                    passed=ok,
                    expected="0 calls",
                    actual=f"{count} call(s)",
                    message=(
                        f"Forbidden actor '{actor}' was never called."
                        if ok
                        else f"Forbidden actor '{actor}' was invoked {count} time(s)."
                    ),
                )
            )

        for seq in self._order_sequences:
            pos = 0
            for actor in actors:
                if pos < len(seq) and actor == seq[pos]:
                    pos += 1
            ok = pos == len(seq)
            results.append(
                RuleResult(
                    rule_name=f"order:{'->'.join(seq)}",
                    passed=ok,
                    expected=" -> ".join(seq),
                    actual="matched" if ok else f"stopped before '{seq[pos]}'",
                    message=(
                        f"Subsequence {' -> '.join(seq)} satisfied."
                        if ok
                        else f"Expected ordered actors {' -> '.join(seq)}, failed to observe '{seq[pos]}' in order."
                    ),
                )
            )

        if self._max_steps is not None:
            actual_steps = len(spans)
            ok = actual_steps <= self._max_steps
            results.append(
                RuleResult(
                    rule_name="max_steps",
                    passed=ok,
                    expected=f"<= {self._max_steps}",
                    actual=str(actual_steps),
                    message=(
                        f"Step count {actual_steps} within limit {self._max_steps}."
                        if ok
                        else f"Step count {actual_steps} exceeded limit {self._max_steps}."
                    ),
                )
            )

        if self._max_cost_usd is not None:
            total_cost = round(sum(sp.cost_usd for sp in spans), 8)
            ok = total_cost <= self._max_cost_usd
            results.append(
                RuleResult(
                    rule_name="max_cost_usd",
                    passed=ok,
                    expected=f"<= ${self._max_cost_usd:.4f}",
                    actual=f"${total_cost:.4f}",
                    message=(
                        f"Cost ${total_cost:.4f} within budget ${self._max_cost_usd:.4f}."
                        if ok
                        else f"Cost ${total_cost:.4f} exceeded budget ${self._max_cost_usd:.4f}."
                    ),
                )
            )

        if self._max_tokens is not None:
            total_tok = sum(sp.prompt_tokens + sp.completion_tokens for sp in spans)
            ok = total_tok <= self._max_tokens
            results.append(
                RuleResult(
                    rule_name="max_tokens",
                    passed=ok,
                    expected=f"<= {self._max_tokens}",
                    actual=str(total_tok),
                    message=(
                        f"Tokens {total_tok} within cap {self._max_tokens}."
                        if ok
                        else f"Tokens {total_tok} exceeded cap {self._max_tokens}."
                    ),
                )
            )

        if self._max_total_latency_ms is not None:
            total_lat = round(sum(sp.latency_ms for sp in spans), 2)
            ok = total_lat <= self._max_total_latency_ms
            results.append(
                RuleResult(
                    rule_name="max_total_latency_ms",
                    passed=ok,
                    expected=f"<= {self._max_total_latency_ms:.1f} ms",
                    actual=f"{total_lat:.1f} ms",
                    message=(
                        f"Total latency {total_lat:.1f} ms within SLA."
                        if ok
                        else f"Total latency {total_lat:.1f} ms exceeded SLA {self._max_total_latency_ms:.1f} ms."
                    ),
                )
            )

        if self._max_step_latency_ms is not None:
            worst = max((sp.latency_ms for sp in spans), default=0.0)
            ok = worst <= self._max_step_latency_ms
            results.append(
                RuleResult(
                    rule_name="max_step_latency_ms",
                    passed=ok,
                    expected=f"<= {self._max_step_latency_ms:.1f} ms",
                    actual=f"{worst:.1f} ms max",
                    message=(
                        f"Max single-step latency {worst:.1f} ms within SLA."
                        if ok
                        else f"Step latency {worst:.1f} ms exceeded SLA {self._max_step_latency_ms:.1f} ms."
                    ),
                )
            )

        if self._max_error_rate is not None:
            err_count = sum(1 for sp in spans if sp.status == "error")
            rate = round(err_count / len(spans), 6) if spans else 0.0
            ok = rate <= self._max_error_rate
            results.append(
                RuleResult(
                    rule_name="max_error_rate",
                    passed=ok,
                    expected=f"<= {self._max_error_rate:.2%}",
                    actual=f"{rate:.2%} ({err_count}/{len(spans)})",
                    message=(
                        f"Error rate {rate:.2%} within tolerance."
                        if ok
                        else f"Error rate {rate:.2%} exceeded max {self._max_error_rate:.2%}."
                    ),
                )
            )

        total_rules = len(results)
        passed_rules = sum(1 for r in results if r.passed)
        failed_rules = total_rules - passed_rules
        score = round((passed_rules / total_rules) * 100.0, 2) if total_rules else 100.0

        return ContractReport(
            contract_name=self.name,
            agent_id=agent_id,
            passed=(failed_rules == 0),
            score=score,
            total_rules=total_rules,
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            steps_evaluated=len(spans),
            results=results,
        )


def assert_trajectory(
    cassette: Union[FlightRecorder, Sequence[TrajectorySpan], Mapping[str, Any], str, Path],
    contract: Union[FlightContract, Mapping[str, Any]],
) -> ContractReport:
    """Evaluate `contract` against `cassette`, raise `AssertionError` on failure, and return the report."""
    compiled = contract if isinstance(contract, FlightContract) else FlightContract.from_dict(contract)
    return compiled.evaluate(cassette).assert_passed()
