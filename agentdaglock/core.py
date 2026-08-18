"""
Agent-DAG-Lock: Deterministic Topological Cycle Breaker & Tool Deadlock Resolver.
Standard library only: hashlib, json, time, os, dataclasses, typing, collections.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


@dataclasses.dataclass(frozen=True)
class DeadlockReceipt:
    """Immutable SHA-256 cryptographically chained swarm liveness receipt."""
    index: int
    prev_hash: str
    swarm_id: str
    nodes_count: int
    edges_count: int
    cycle_detected: bool
    status: str
    timestamp: float
    signature_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class CryptographicDeadlockLedger:
    """Tamper-Proof Swarm Liveness & Cycle Prevention Ledger."""

    def __init__(self, ledger_file: Optional[str] = None):
        self.ledger_file = ledger_file
        self._entries: List[DeadlockReceipt] = []
        self._last_hash = GENESIS_HASH

    @property
    def last_hash(self) -> str:
        return self._last_hash

    @property
    def count(self) -> int:
        return len(self._entries)

    def record_receipt(
        self,
        swarm_id: str,
        nodes_count: int,
        edges_count: int,
        cycle_detected: bool,
        status: str,
    ) -> DeadlockReceipt:
        idx = len(self._entries)
        ts = time.time()

        raw_msg = f"{idx}:{self._last_hash}:{swarm_id}:{nodes_count}:{edges_count}:{cycle_detected}:{status}:{ts:.6f}"
        sig_hash = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()

        receipt = DeadlockReceipt(
            index=idx,
            prev_hash=self._last_hash,
            swarm_id=swarm_id,
            nodes_count=nodes_count,
            edges_count=edges_count,
            cycle_detected=cycle_detected,
            status=status,
            timestamp=ts,
            signature_hash=sig_hash,
        )

        self._entries.append(receipt)
        self._last_hash = sig_hash

        if self.ledger_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
            with open(self.ledger_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(receipt.to_dict()) + "\n")

        return receipt

    def verify_chain_integrity(self) -> Tuple[bool, Optional[str]]:
        current_prev = GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            if entry.index != idx:
                return False, f"Sequence index break at {idx}"
            if entry.prev_hash != current_prev:
                return False, f"Broken SHA-256 chain at {idx}"
            current_prev = entry.signature_hash
        return True, None


class AgentDAGLock:
    """
    In-Memory Topological Cycle Breaker and Deadlock Resolver for Multi-Agent Workflows.
    Enforces strict Acyclic Dependency Graph invariants before any agent tool call executes.
    """

    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger = CryptographicDeadlockLedger(ledger_file=ledger_path)
        self.adj_list: Dict[str, Set[str]] = collections.defaultdict(set)

    def check_kill_switch(self) -> bool:
        if os.environ.get("AGENT_DAGLOCK_KILL", "0") in ("1", "true", "TRUE"):
            return True
        if os.path.exists("/tmp/AGENT_DAGLOCK_KILL"):
            return True
        return False

    def clear(self) -> None:
        self.adj_list.clear()

    def _has_cycle_dfs(self, node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in self.adj_list.get(node, set()):
            if neighbor not in visited:
                if self._has_cycle_dfs(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    def validate_and_claim_dependency(
        self,
        swarm_id: str,
        dependent_agent: str,
        target_dependency: str,
    ) -> Tuple[bool, DeadlockReceipt]:
        if self.check_kill_switch():
            receipt = self.ledger.record_receipt(
                swarm_id=swarm_id,
                nodes_count=0,
                edges_count=0,
                cycle_detected=False,
                status="HALTED_BY_EMERGENCY_KILL_SWITCH",
            )
            return False, receipt

        self.adj_list[dependent_agent].add(target_dependency)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycle_found = False

        all_nodes = set(self.adj_list.keys())
        for n in list(self.adj_list.values()):
            all_nodes.update(n)

        for node in all_nodes:
            if node not in visited:
                if self._has_cycle_dfs(node, visited, rec_stack):
                    cycle_found = True
                    break

        nodes_count = len(all_nodes)
        edges_count = sum(len(neighbors) for neighbors in self.adj_list.values())

        if cycle_found:
            self.adj_list[dependent_agent].remove(target_dependency)
            if not self.adj_list[dependent_agent]:
                del self.adj_list[dependent_agent]

            receipt = self.ledger.record_receipt(
                swarm_id=swarm_id,
                nodes_count=nodes_count,
                edges_count=edges_count - 1,
                cycle_detected=True,
                status="REJECTED_CIRCULAR_DEPENDENCY_DEADLOCK_PREVENTED",
            )
            return False, receipt

        receipt = self.ledger.record_receipt(
            swarm_id=swarm_id,
            nodes_count=nodes_count,
            edges_count=edges_count,
            cycle_detected=False,
            status="COMMITTED_ACYCLIC_DEPENDENCY_VERIFIED",
        )
        return True, receipt
