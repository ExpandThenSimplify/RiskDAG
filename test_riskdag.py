"""
Basic tests for RiskDAG package.

Run with: pytest tests/
"""

#import pytest
import numpy as np
from scipy import stats

from riskdag import (
    RiskNode, 
    LatentRiskNode,
    RiskDAG,
    TimeConverter,
    TimeScale,
    convert_prob
)


class TestRiskNode:
    """Test RiskNode functionality."""
    
    def test_node_creation(self):
        """Test creating a basic risk node."""
        node = RiskNode('test_node', p_fail=0.05, loss_dist=stats.norm(100, 10))
        assert node.node_id == 'test_node'
        assert node.p_fail == 0.05
        assert not node.is_latent
    
    def test_dependency_operator(self):
        """Test >> operator for dependencies."""
        node_a = RiskNode('A', p_fail=0.01)
        node_b = RiskNode('B', p_fail=0.02)
        
        node_a >> node_b
        
        assert node_b in node_a.downstream_nodes
    
    def test_chained_dependencies(self):
        """Test chaining dependencies."""
        a = RiskNode('A', p_fail=0.01)
        b = RiskNode('B', p_fail=0.02)
        c = RiskNode('C', p_fail=0.03)
        
        a >> b >> c
        
        assert b in a.downstream_nodes
        assert c in b.downstream_nodes


class TestLatentRiskNode:
    """Test LatentRiskNode functionality."""
    
    def test_latent_node_creation(self):
        """Test creating a latent risk node."""
        node = LatentRiskNode('cloud', p_fail=0.01, loss_dist=stats.norm(1000, 100))
        assert node.node_id == 'cloud'
        assert node.is_latent
    
    def test_contagion_operator(self):
        """Test @ operator for contagion."""
        cloud = LatentRiskNode('cloud', p_fail=0.01)
        db = LatentRiskNode('db', p_fail=0.02)
        
        cloud @ db | 0.6
        
        assert db in cloud.contagion_risks
        assert cloud.contagion_risks[db] == 0.6
    
    def test_latent_affecting_regular(self):
        """Test latent risk affecting regular node."""
        latent = LatentRiskNode('infrastructure', p_fail=0.01)
        task = RiskNode('task', p_fail=0.05)
        
        latent >> task
        
        assert latent in task.latent_risks


class TestTimeConverter:
    """Test time scale conversion."""
    
    def test_same_scale_conversion(self):
        """Test converting within same scale."""
        result = convert_prob(0.05, 'hour', 'hour')
        assert abs(result - 0.05) < 1e-10
    
    def test_day_to_hour_conversion(self):
        """Test daily to hourly conversion."""
        # 5% daily should be about 0.21% hourly
        result = convert_prob(0.05, 'day', 'hour')
        assert 0.002 < result < 0.003
    
    def test_year_to_day_conversion(self):
        """Test yearly to daily conversion."""
        result = convert_prob(0.10, 'year', 'day')
        assert 0.0002 < result < 0.0004
    
    def test_zero_probability(self):
        """Test conversion of zero probability."""
        result = convert_prob(0.0, 'day', 'hour')
        assert result == 0.0


class TestRiskDAG:
    """Test RiskDAG functionality."""
    
    def test_dag_creation(self):
        """Test creating a RiskDAG."""
        dag = RiskDAG('test_dag', time_scale='hour')
        assert dag.dag_id == 'test_dag'
        assert dag.time_scale == TimeScale.HOUR
    
    def test_add_nodes(self):
        """Test adding nodes to DAG."""
        dag = RiskDAG('test_dag')
        node = RiskNode('task', p_fail=0.05, loss_dist=stats.norm(100, 10))
        dag.add_node(node)
        
        assert 'task' in dag.nodes
        assert dag.nodes['task'] == node
    
    def test_time_scale_adjustment(self):
        """Test automatic time scale adjustment."""
        dag = RiskDAG('test_dag', time_scale='hour')
        node = RiskNode('task', p_fail=0.05)  # 5% daily
        
        dag.add_node(node, user_time_scale='day')
        
        # Should be converted to hourly
        assert node.p_fail < 0.05
        assert node.p_fail > 0.001
    
    def test_graph_building(self):
        """Test building graph from dependencies."""
        dag = RiskDAG('test_dag')
        
        a = RiskNode('A', p_fail=0.01)
        b = RiskNode('B', p_fail=0.02)
        c = RiskNode('C', p_fail=0.03)
        
        a >> b >> c
        
        dag.add_nodes([a, b, c])
        dag.build_graph()
        
        assert dag.graph.has_edge('A', 'B')
        assert dag.graph.has_edge('B', 'C')
    
    def test_monte_carlo_simulation(self):
        """Test running Monte Carlo simulation."""
        dag = RiskDAG('test_dag')
        
        a = RiskNode('A', p_fail=0.1, loss_dist=stats.norm(100, 10))
        b = RiskNode('B', p_fail=0.2, loss_dist=stats.norm(200, 20))
        
        a >> b
        
        dag.add_nodes([a, b])
        dag.build_graph()
        
        results = dag.run_monte_carlo(n_simulations=100, seed=42)
        
        assert results.n_simulations == 100
        assert len(results.total_losses) == 100
        assert results.total_losses.min() >= 0
    
    def test_simulation_with_latent_risks(self):
        """Test simulation with latent risks."""
        dag = RiskDAG('test_dag')
        
        latent = LatentRiskNode('infra', p_fail=0.1, loss_dist=stats.norm(1000, 100))
        task = RiskNode('task', p_fail=0.05, loss_dist=stats.norm(100, 10))
        
        latent >> task
        
        dag.add_nodes([latent, task])
        dag.build_graph()
        
        results = dag.run_monte_carlo(n_simulations=100, seed=42)
        
        # Task should fail more often due to latent risk
        task_failure_rate = results.node_failure_rate('task')
        assert task_failure_rate > 0.05


class TestSimulationResults:
    """Test simulation results analysis."""
    
    @pytest.fixture
    def sample_results(self):
        """Create sample results for testing."""
        dag = RiskDAG('test_dag')
        node = RiskNode('task', p_fail=0.1, loss_dist=stats.norm(100, 10))
        dag.add_node(node)
        dag.build_graph()
        return dag.run_monte_carlo(n_simulations=1000, seed=42)
    
    def test_quantile_calculation(self, sample_results):
        """Test quantile calculation."""
        q95 = sample_results.get_quantile(0.95)
        assert q95 > 0
        assert q95 < sample_results.total_losses.max()
    
    def test_expected_shortfall(self, sample_results):
        """Test expected shortfall calculation."""
        es = sample_results.expected_shortfall(0.95)
        var = sample_results.get_quantile(0.95)
        
        # ES should be greater than or equal to VaR
        assert es >= var
    
    def test_exceedance_curve(self, sample_results):
        """Test exceedance curve generation."""
        losses, probs = sample_results.get_exceedance_curve()
        
        assert len(losses) > 0
        assert len(losses) == len(probs)
        assert all(0 <= p <= 1 for p in probs)
        # Exceedance probabilities should be non-increasing
        assert all(probs[i] >= probs[i+1] for i in range(len(probs)-1))
    
    def test_summary_statistics(self, sample_results):
        """Test summary statistics."""
        stats = sample_results.summary_statistics()
        
        assert 'mean_loss' in stats
        assert 'median_loss' in stats
        assert 'var_95' in stats
        assert 'es_95' in stats
        assert stats['mean_loss'] >= 0
        assert stats['var_95'] >= stats['median_loss']


def test_full_workflow():
    """Test complete workflow from node creation to analysis."""
    # Create nodes
    cloud = LatentRiskNode('cloud', p_fail=0.01, loss_dist=stats.norm(5000, 500))
    db = LatentRiskNode('db', p_fail=0.02, loss_dist=stats.norm(3000, 300))
    
    extract = RiskNode('extract', p_fail=0.01, loss_dist=stats.norm(100, 10))
    transform = RiskNode('transform', p_fail=0.05, loss_dist=stats.norm(200, 20))
    
    # Define relationships
    cloud @ db | 0.6
    db >> extract >> transform
    
    # Create DAG
    dag = RiskDAG('etl', time_scale='hour')
    dag.add_node(cloud, user_time_scale='day')
    dag.add_node(db, user_time_scale='day')
    dag.add_nodes([extract, transform])
    dag.build_graph()
    
    # Run simulation
    results = dag.run_monte_carlo(n_simulations=100, seed=42)
    
    # Verify results
    assert results.n_simulations == 100
    assert results.total_losses.mean() > 0
    assert results.get_quantile(0.95) > results.get_quantile(0.50)
    assert results.expected_shortfall(0.95) >= results.get_quantile(0.95)


def test_context_manager():
    """Test context manager pattern for automatic node registration."""
    with RiskDAG('context_test', time_scale='hour') as dag:
        # Create nodes within context
        cloud = LatentRiskNode(
            'cloud', 
            p_fail=0.01, 
            loss_dist=stats.norm(5000, 500),
            user_time_scale='day'
        )
        db = LatentRiskNode(
            'db',
            p_fail=0.02,
            loss_dist=stats.norm(3000, 300),
            user_time_scale='day'
        )
        task = RiskNode('task', p_fail=0.05, loss_dist=stats.norm(100, 10))
        
        # Define relationships
        cloud @ db | 0.6
        db >> task
    
    # Nodes should be auto-registered
    assert len(dag.nodes) == 3
    assert 'cloud' in dag.nodes
    assert 'db' in dag.nodes
    assert 'task' in dag.nodes
    assert len(dag.latent_risks) == 2
    
    # Graph should be auto-built
    assert dag.graph.has_edge('db', 'task')
    
    # Should be able to run simulation
    results = dag.run_monte_carlo(n_simulations=100, seed=42)
    assert results.n_simulations == 100


def test_discover_from_nodes():
    """Test auto-discovery from root nodes."""
    # Create nodes without context
    cloud = LatentRiskNode('cloud', p_fail=0.01, loss_dist=stats.norm(5000, 500))
    db = LatentRiskNode('db', p_fail=0.02, loss_dist=stats.norm(3000, 300))
    task1 = RiskNode('task1', p_fail=0.05, loss_dist=stats.norm(100, 10))
    task2 = RiskNode('task2', p_fail=0.03, loss_dist=stats.norm(50, 5))
    
    # Define relationships
    cloud @ db | 0.6
    db >> task1 >> task2
    
    # Create DAG and discover from root
    dag = RiskDAG('discovery_test', time_scale='hour')
    dag.discover_from_nodes([cloud])
    
    # Should have found all connected nodes
    assert len(dag.nodes) == 4
    assert 'cloud' in dag.nodes
    assert 'db' in dag.nodes
    assert 'task1' in dag.nodes
    assert 'task2' in dag.nodes


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
