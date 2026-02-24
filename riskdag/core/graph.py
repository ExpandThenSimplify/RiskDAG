"""
Main RiskDAG class for building and managing risk graphs.
"""
from typing import List, Dict, Set, Optional, Union
import networkx as nx
from scipy import stats
import numpy as np

from .nodes import RiskNode, LatentRiskNode
from .time_conversion import TimeConverter, TimeScale


class RiskDAG:
    """
    A directed acyclic graph for risk modeling.
    
    Manages risk nodes, latent risks, dependencies, and contagion effects.
    
    Can be used as a context manager for automatic node registration:
    
        with RiskDAG('pipeline', time_scale='hour') as dag:
            cloud = LatentRiskNode('cloud', p_fail=0.01)
            db = LatentRiskNode('db', p_fail=0.02)
            extract = RiskNode('extract', p_fail=0.05)
            
            cloud @ db | 0.6
            db >> extract
            # Nodes automatically registered!
    """
    
    _current_dag = None  # Class variable to track active DAG context
    
    def __init__(self, dag_id: str, time_scale: Union[str, TimeScale] = TimeScale.HOUR):
        """
        Initialize a RiskDAG.
        
        Args:
            dag_id: Unique identifier for this risk DAG
            time_scale: Time scale for the DAG (how often it runs)
        """
        self.dag_id = dag_id
        self.time_scale = TimeScale(time_scale) if isinstance(time_scale, str) else time_scale
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, RiskNode] = {}
        self.latent_risks: Dict[str, LatentRiskNode] = {}
        self._user_time_scales: Dict[str, TimeScale] = {}  # Track user-specified time scales
    
    def __enter__(self):
        """Enter context manager - set this as the active DAG."""
        RiskDAG._current_dag = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - auto-discover and build graph."""
        RiskDAG._current_dag = None
        if exc_type is None:
            # Auto-discover all nodes that were created in this context
            self._auto_discover_nodes()
            self.build_graph()
        return False
    
    @classmethod
    def get_current(cls) -> Optional['RiskDAG']:
        """Get the currently active DAG context."""
        return cls._current_dag
    
    def _auto_discover_nodes(self):
        """
        Auto-discover all nodes by crawling the global node registry.
        This is called automatically when exiting a context manager.
        """
        # Get all nodes from the global registry
        from .nodes import _NODE_REGISTRY
        
        for node_id, (node, user_time_scale) in _NODE_REGISTRY.items():
            if node_id not in self.nodes:
                self.add_node(node, user_time_scale=user_time_scale)
        
        # Clear the registry after importing
        _NODE_REGISTRY.clear()
    
    def discover_from_nodes(self, root_nodes: List[RiskNode]):
        """
        Auto-discover all connected nodes starting from root nodes.
        
        Args:
            root_nodes: Starting nodes to crawl from
        """
        visited = set()
        to_visit = list(root_nodes)
        
        while to_visit:
            node = to_visit.pop()
            if node.node_id in visited:
                continue
            
            visited.add(node.node_id)
            
            # Add this node
            if node.node_id not in self.nodes:
                self.add_node(node)
            
            # Add downstream nodes
            for downstream in node.downstream_nodes:
                if downstream.node_id not in visited:
                    to_visit.append(downstream)
            
            # Add contagion targets for latent risks
            if isinstance(node, LatentRiskNode):
                for target in node.contagion_risks.keys():
                    if target.node_id not in visited:
                        to_visit.append(target)
                
                # Add affected nodes
                for affected in node.affected_nodes:
                    if affected.node_id not in visited:
                        to_visit.append(affected)
        
        # Build the graph after discovery
        self.build_graph()
    
    def extend_with_latent_risks(self, latent_risks: List[LatentRiskNode], 
                                  user_time_scale: Optional[str] = None):
        """
        Extend an existing RiskDAG with additional latent risks.
        
        **DEPRECATED**: This method is optional. Just use >> or @ operators to link
        latent risks to tasks, then call build_graph(). It will auto-discover them.
        
        New pattern (simpler):
            >>> cloud >> risk_dag.nodes['extract']
            >>> risk_dag.build_graph()  # Auto-discovers cloud latent risk node
        
        Old pattern (still works):
            >>> cloud >> risk_dag.nodes['extract']
            >>> risk_dag.extend_with_latent_risks([cloud], user_time_scale='day')
        
        Args:
            latent_risks: List of LatentRiskNode instances
            user_time_scale: Optional time scale for the latent risks
        """
        for latent in latent_risks:
            if latent.node_id not in self.nodes:
                self.add_node(latent, user_time_scale=user_time_scale)
        
        # Rebuild graph to incorporate new nodes and their connections
        self.build_graph()
        self._user_time_scales: Dict[str, TimeScale] = {}  # Track user-specified time scales
        
    def add_node(
        self, 
        node: RiskNode,
        user_time_scale: Optional[Union[str, TimeScale]] = None
    ):
        """
        Add a node to the risk DAG.
        
        Args:
            node: RiskNode or LatentRiskNode instance
            user_time_scale: Time scale the user specified p_fail in (if different from DAG scale)
        """
        # Adjust probability if user specified a different time scale
        if user_time_scale is not None:
            TimeConverter.adjust_node_probability(node, self.time_scale, user_time_scale)
        
        self.nodes[node.node_id] = node
        self.graph.add_node(node.node_id, node=node)
        
        if node.is_latent:
            self.latent_risks[node.node_id] = node
    
    def add_nodes(self, nodes: List[RiskNode], user_time_scale: Optional[str] = None):
        """Add multiple nodes at once."""
        for node in nodes:
            self.add_node(node, user_time_scale)
    
    def build_graph(self):
        """
        Build the graph structure from node dependencies.
        Automatically discovers and adds any connected nodes that aren't already in the DAG.
        Call this after all nodes are added and >> operators have been used.
        """
        # Auto-discover any nodes connected via >> or @ that aren't in self.nodes yet
        discovered_nodes = set()
        
        # Check all existing nodes for connections to undiscovered nodes
        for node_id, node in list(self.nodes.items()):
            # Check downstream connections
            for downstream in node.downstream_nodes:
                if downstream.node_id not in self.nodes:
                    discovered_nodes.add(downstream)
            
            # Check latent risk connections for regular nodes
            if not node.is_latent:
                for latent in node.latent_risks.keys():
                    if latent.node_id not in self.nodes:
                        discovered_nodes.add(latent)
            
            # Check contagion and affected nodes for latent risks
            if node.is_latent:
                for target in node.contagion_risks.keys():
                    if target.node_id not in self.nodes:
                        discovered_nodes.add(target)
                for affected in node.affected_nodes:
                    if affected.node_id not in self.nodes:
                        discovered_nodes.add(affected)
        
        # Add discovered nodes
        for node in discovered_nodes:
            # For latent risks, try to infer time scale from existing latent risks
            if node.is_latent:
                # Use 'day' as default time scale for auto-discovered latent risks
                self.add_node(node, user_time_scale='day')
            else:
                self.add_node(node)
        
        # Add edges from node dependencies
        for node_id, node in self.nodes.items():
            # Add downstream edges (from >> operator)
            for downstream in node.downstream_nodes:
                if downstream.node_id in self.nodes:
                    self.graph.add_edge(node_id, downstream.node_id)
            
            # Add contagion edges (from @ operator)
            if node.is_latent:
                # Latent to latent contagion
                for target in node.contagion_risks.keys():
                    if target.node_id in self.nodes:
                        self.graph.add_edge(node_id, target.node_id)
                
                # Latent to task contagion
                if hasattr(node, 'task_contagion_probs'):
                    for target in node.task_contagion_probs.keys():
                        if target.node_id in self.nodes:
                            self.graph.add_edge(node_id, target.node_id)
        
        # Verify DAG property
        if not nx.is_directed_acyclic_graph(self.graph):
            raise ValueError("Graph contains cycles! RiskDAG must be acyclic.")
    
    def get_node(self, node_id: str) -> Optional[RiskNode]:
        """Retrieve a node by ID."""
        return self.nodes.get(node_id)
    
    def get_ancestors(self, node_id: str) -> Set[str]:
        """Get all nodes that this node depends on (upstream)."""
        return nx.ancestors(self.graph, node_id)
    
    def get_descendants(self, node_id: str) -> Set[str]:
        """Get all nodes that depend on this node (downstream)."""
        return nx.descendants(self.graph, node_id)
    
    def simulate_single_run(self, rng: np.random.Generator) -> Dict[str, Dict]:
        """
        Run a single Monte Carlo simulation.
        
        Returns:
            Dictionary with simulation results for each node
        """
        results = {}
        failed_nodes = set()
        triggered_latents = set()
        
        # First, determine which latent risks are triggered
        for latent_id, latent in self.latent_risks.items():
            if rng.random() < latent.p_fail:
                triggered_latents.add(latent_id)
        
        # Apply contagion effects between latent risks
        for source_id in list(triggered_latents):
            source = self.latent_risks[source_id]
            for target, contagion_prob in source.contagion_risks.items():
                # If source triggered, target's probability increases
                if target.node_id not in triggered_latents:
                    if rng.random() < contagion_prob:
                        triggered_latents.add(target.node_id)
        
        # Process nodes in topological order
        topo_order = list(nx.topological_sort(self.graph))
        
        for node_id in topo_order:
            node = self.nodes[node_id]
            
            # Skip if this is a latent risk (already processed)
            if node.is_latent:
                failed = node_id in triggered_latents
                loss = node.sample_loss() if failed else 0.0
                results[node_id] = {
                    'failed': failed,
                    'loss': loss,
                    'failure_cause': 'latent_trigger' if failed else None
                }
                if failed:
                    failed_nodes.add(node_id)
                continue
            
            # Check if any upstream nodes failed (cascade failure)
            upstream_failed = False
            for ancestor in self.get_ancestors(node_id):
                if ancestor in failed_nodes:
                    upstream_failed = True
                    break
            
            # Check if any associated latent risks triggered
            latent_triggered = False
            latent_trigger_prob = 0.0  # Track highest contagion probability
            
            for latent_risk, contagion_prob in node.latent_risks.items():
                if latent_risk.node_id in triggered_latents:
                    if contagion_prob is not None:
                        # Probabilistic contagion: latent @ task | prob
                        # Use the contagion probability
                        latent_trigger_prob = max(latent_trigger_prob, contagion_prob)
                    else:
                        # Deterministic cascade: latent >> task
                        # Always triggers
                        latent_triggered = True
                        break
            
            # If we have probabilistic contagion, test it
            if not latent_triggered and latent_trigger_prob > 0:
                latent_triggered = rng.random() < latent_trigger_prob
            
            # Determine if node fails
            if upstream_failed or latent_triggered:
                failed = True
                cause = 'cascade' if upstream_failed else 'latent_risk'
            else:
                failed = rng.random() < node.p_fail
                cause = 'independent' if failed else None
            
            # Calculate loss
            loss = node.sample_loss() if failed else 0.0
            
            results[node_id] = {
                'failed': failed,
                'loss': loss,
                'failure_cause': cause
            }
            
            if failed:
                failed_nodes.add(node_id)
        
        return results
    
    def run_monte_carlo(
        self, 
        n_simulations: int = 1000,
        seed: Optional[int] = None
    ) -> 'SimulationResults':
        """
        Run Monte Carlo simulations.
        
        Automatically builds/rebuilds the graph before simulation if needed.
        
        Args:
            n_simulations: Number of simulation runs
            seed: Random seed for reproducibility
        
        Returns:
            SimulationResults object with analysis
        """
        # Auto-build graph if it hasn't been built or if new nodes were added
        # This allows users to skip calling build_graph() manually
        self.build_graph()
        
        rng = np.random.default_rng(seed)
        
        all_runs = []
        total_losses = []
        
        for i in range(n_simulations):
            run_result = self.simulate_single_run(rng)
            all_runs.append(run_result)
            
            # Calculate total loss for this run
            total_loss = sum(result['loss'] for result in run_result.values())
            total_losses.append(total_loss)
        
        return SimulationResults(
            dag=self,
            runs=all_runs,
            total_losses=np.array(total_losses),
            n_simulations=n_simulations
        )
    
    def __repr__(self):
        return f"RiskDAG('{self.dag_id}', nodes={len(self.nodes)}, latent={len(self.latent_risks)})"


class SimulationResults:
    """Container for Monte Carlo simulation results."""
    
    def __init__(
        self, 
        dag: RiskDAG,
        runs: List[Dict],
        total_losses: np.ndarray,
        n_simulations: int
    ):
        self.dag = dag
        self.runs = runs
        self.total_losses = total_losses
        self.n_simulations = n_simulations
        
        # Sort losses for quantile calculations
        self.sorted_losses = np.sort(total_losses)
    
    def get_quantile(self, q: float) -> float:
        """
        Get loss at a specific quantile.
        
        Args:
            q: Quantile (0 to 1, e.g., 0.95 for 95th percentile)
        """
        return np.quantile(self.total_losses, q)
    
    def expected_shortfall(self, confidence: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (Conditional VaR) at given confidence level.
        
        Args:
            confidence: Confidence level (e.g., 0.95 for 95% ES)
        
        Returns:
            Expected loss given that loss exceeds the VaR threshold
        """
        var = self.get_quantile(confidence)
        # Expected shortfall is the mean of losses exceeding VaR
        exceedances = self.total_losses[self.total_losses >= var]
        return exceedances.mean() if len(exceedances) > 0 else 0.0
    
    def get_exceedance_curve(self) -> tuple:
        """
        Generate exceedance curve data.
        
        Returns:
            Tuple of (loss_levels, exceedance_probabilities)
        """
        # Unique sorted loss values
        unique_losses = np.unique(self.sorted_losses)
        
        # For each loss level, calculate probability of exceeding it
        exceedance_probs = np.array([
            np.mean(self.total_losses >= loss) for loss in unique_losses
        ])
        
        return unique_losses, exceedance_probs
    
    def node_failure_rate(self, node_id: str) -> float:
        """Calculate failure rate for a specific node."""
        failures = sum(1 for run in self.runs if run.get(node_id, {}).get('failed', False))
        return failures / self.n_simulations
    
    def summary_statistics(self) -> Dict:
        """Get summary statistics of simulation results."""
        return {
            'n_simulations': self.n_simulations,
            'mean_loss': self.total_losses.mean(),
            'median_loss': np.median(self.total_losses),
            'std_loss': self.total_losses.std(),
            'min_loss': self.total_losses.min(),
            'max_loss': self.total_losses.max(),
            'var_95': self.get_quantile(0.95),
            'var_99': self.get_quantile(0.99),
            'es_95': self.expected_shortfall(0.95),
            'es_99': self.expected_shortfall(0.99),
        }
    
    def __repr__(self):
        stats = self.summary_statistics()
        return (f"SimulationResults(n={self.n_simulations}, "
                f"mean_loss={stats['mean_loss']:.2f}, "
                f"VaR95={stats['var_95']:.2f}, "
                f"ES95={stats['es_95']:.2f})")
