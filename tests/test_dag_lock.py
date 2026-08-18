import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agentdaglock.core import AgentDAGLock, GENESIS_HASH


class TestAgentDAGLock(unittest.TestCase):
    def setUp(self):
        self.lock = AgentDAGLock()

    def test_acyclic_dependencies_commit(self):
        # A -> B -> C (Valid Acyclic Graph)
        ok1, r1 = self.lock.validate_and_claim_dependency('swarm_1', 'agent_A', 'agent_B')
        ok2, r2 = self.lock.validate_and_claim_dependency('swarm_1', 'agent_B', 'agent_C')

        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertFalse(r1.cycle_detected)
        self.assertEqual(r1.status, 'COMMITTED_ACYCLIC_DEPENDENCY_VERIFIED')

        # Verify ledger cryptographic integrity
        is_valid, err = self.lock.ledger.verify_chain_integrity()
        self.assertTrue(is_valid, f'DAG-Lock ledger broken: {err}')

    def test_circular_dependency_deadlock_rejection(self):
        # A -> B -> C -> A (Deadlock Cycle)
        self.lock.validate_and_claim_dependency('swarm_1', 'agent_A', 'agent_B')
        self.lock.validate_and_claim_dependency('swarm_1', 'agent_B', 'agent_C')

        # C -> A attempt creates cycle!
        ok3, r3 = self.lock.validate_and_claim_dependency('swarm_1', 'agent_C', 'agent_A')

        self.assertFalse(ok3)
        self.assertTrue(r3.cycle_detected)
        self.assertEqual(r3.status, 'REJECTED_CIRCULAR_DEPENDENCY_DEADLOCK_PREVENTED')


if __name__ == '__main__':
    unittest.main()
