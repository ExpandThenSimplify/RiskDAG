"""
Core node classes for RiskDAG modeling.
"""
from typing import Optional, Dict, List, Tuple
from scipy import stats
import numpy as np


# Global registry for nodes created within a DAG context
_NODE_REGISTRY: Dict[str, Tuple['RiskNode', Optional[str]]] = {}


class RiskNode:
    """
    A node in a risk graph representing a task or component that can fail.
    
    Attributes:
        node_id: Unique identifier for the node
        p_fail: Probability of failure
        loss_dist: Scipy distribution representing loss if failure occurs
        is_latent: Whether this is a latent risk node
        downstream_nodes: List of nodes that depend on this one
        latent_risks: Dict mapping latent risk nodes to their impact on this node
    """
    
    def __init__(
        self, 
        node_id: str, 
        p_fail: float = 0.0, 
        loss_dist=None,
        is_latent: bool = False,
        user_time_scale: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.node_id = node_id
        self.p_fail = p_fail
        self.loss_dist = loss_dist if loss_dist is not None else stats.uniform(0, 0)
        self.is_latent = is_latent
        self.downstream_nodes: List['RiskNode'] = []
        self.latent_risks: Dict['LatentRiskNode', float] = {}
        self.metadata: Dict = metadata or {}
        
        # Auto-register with active DAG context if it exists
        self._register_with_dag(user_time_scale)
    
    def _register_with_dag(self, user_time_scale: Optional[str] = None):
        """Register this node with the currently active DAG context."""
        # Import here to avoid circular dependency
        from .graph import RiskDAG
        
        current_dag = RiskDAG.get_current()
        if current_dag is not None:
            # Register with the global registry
            _NODE_REGISTRY[self.node_id] = (self, user_time_scale)
        
    def __rshift__(self, other: 'RiskNode') -> 'RiskNode':
        """
        Define dependency using >> operator.
        A >> B means if A fails, B also fails.
        """
        if other not in self.downstream_nodes:
            self.downstream_nodes.append(other)
        return other
    
    def sample_loss(self) -> float:
        """Sample a loss value from the distribution."""
        return self.loss_dist.rvs()
    
    def __repr__(self):
        return f"RiskNode('{self.node_id}', p_fail={self.p_fail:.4f})"


class ContagionPair:
    """
    Helper class to enable the syntax: LatentA @ NodeB | prob
    This is created by LatentA @ NodeB, then | prob sets the probability.
    Works for both LatentRiskNode and RiskNode targets.
    """
    def __init__(self, source: 'LatentRiskNode', target: 'RiskNode'):
        self.source = source
        self.target = target
    
    def __or__(self, probability: float) -> 'RiskNode':
        """Set the contagion probability."""
        if self.target.is_latent:
            # Latent to latent contagion
            self.source.contagion_risks[self.target] = probability
        else:
            # Latent to task contagion
            if self.target not in self.source.affected_nodes:
                self.source.affected_nodes.append(self.target)
            self.source.task_contagion_probs[self.target] = probability
            self.target.latent_risks[self.source] = probability
        return self.target


class LatentRiskNode(RiskNode):
    """
    A latent risk node representing systemic risks like infrastructure failures,
    cyber attacks, or external dependencies.
    
    Supports contagion modeling via the @ operator.
    """
    
    def __init__(
        self, 
        node_id: str, 
        p_fail: float = 0.0, 
        loss_dist=None,
        user_time_scale: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        super().__init__(node_id, p_fail, loss_dist, is_latent=True, user_time_scale=user_time_scale, metadata=metadata)
        self.contagion_risks: Dict['LatentRiskNode', float] = {}
        self.affected_nodes: List[RiskNode] = []
        self.task_contagion_probs: Dict[RiskNode, float] = {}  # For @ operator with tasks
    
    def __matmul__(self, other):
        """
        Define contagion risk using @ operator.
        
        Works with both LatentRiskNode and regular RiskNode:
        - LatentA @ LatentB | 0.6: If A triggers, B has 60% chance of triggering
        - LatentA @ TaskB | 0.7: If A triggers, TaskB has 70% chance of failing
        
        Usage: 
            cloud @ db | 0.6        # Latent to latent
            cloud @ task | 0.7      # Latent to task
            cloud @ (db, 0.6)       # Alternative tuple syntax
        """
        if isinstance(other, RiskNode):
            # Create ContagionPair to enable | operator
            return ContagionPair(self, other)
        elif isinstance(other, tuple) and len(other) == 2:
            # Direct tuple syntax: latent @ (node, prob)
            target, contagion_prob = other
            if isinstance(target, RiskNode):
                if target.is_latent:
                    # Latent to latent contagion
                    self.contagion_risks[target] = contagion_prob
                else:
                    # Latent to task contagion
                    if target not in self.affected_nodes:
                        self.affected_nodes.append(target)
                    self.task_contagion_probs[target] = contagion_prob
                    target.latent_risks[self] = contagion_prob
                return target
        raise ValueError("Use @ operator with RiskNode or tuple: latent @ node | prob")
    
    def __or__(self, probability: float) -> Tuple['LatentRiskNode', float]:
        """
        Allow syntax: LatentA @ LatentB | 0.6
        The | operator creates a tuple for the @ operator to consume.
        """
        return (self, probability)
    
    def __rshift__(self, other) -> 'RiskNode':
        """
        Override >> to track which regular nodes are affected by this latent risk.
        
        latent >> task means: if latent triggers, task always fails (deterministic)
        """
        result = super().__rshift__(other)
        if isinstance(other, RiskNode) and not other.is_latent:
            if other not in self.affected_nodes:
                self.affected_nodes.append(other)
            # Store None to indicate deterministic cascade (not probabilistic)
            other.latent_risks[self] = None
        return result
    
    def __repr__(self):
        return f"LatentRiskNode('{self.node_id}', p_fail={self.p_fail:.4f})"


def create_latent_risk(
    node_id: str,
    p_fail: float = 0.0,
    loss_dist=None,
    user_time_scale: Optional[str] = None,
    **kwargs
) -> LatentRiskNode:
    """
    Factory function to create latent risk nodes.
    
    Args:
        node_id: Unique identifier
        p_fail: Base failure probability
        loss_dist: Scipy distribution for losses
        user_time_scale: Time scale user specified (e.g., 'day', 'month')
        **kwargs: Additional parameters for future extension
    
    Returns:
        LatentRiskNode instance
    """
    return LatentRiskNode(node_id, p_fail, loss_dist, user_time_scale=user_time_scale)
