"""
RiskDAG: Enterprise Risk Modeling for Airflow DAGs and Latent Risks

A Python library for quantifying and analyzing operational risks in data pipelines
and enterprise systems. Built for risk managers, insurance experts, and cyber risk
quantification professionals.

Key Features:
- Model failure probabilities and loss distributions for DAG tasks
- Define latent risks (infrastructure, cyber, external dependencies)
- Time scale conversion for different execution frequencies
- Contagion modeling between risks
- Monte Carlo simulation 
- Interactive exceedance curves and Expected Shortfall metrics
- Seamless integration with existing Airflow DAGs

Example:
    >>> from riskdag import RiskNode, LatentRiskNode, RiskDAG
    >>> from scipy import stats
    >>> 
    >>> # Use context manager for automatic node registration
    >>> with RiskDAG('etl_pipeline', time_scale='hour') as dag:
    ...     # Define latent risks
    ...     cloud = LatentRiskNode('cloud', p_fail=0.01, 
    ...                          loss_dist=stats.norm(500, 100),
    ...                          user_time_scale='day')
    ...     db = LatentRiskNode('db_failure', p_fail=0.02,
    ...                         loss_dist=stats.norm(1000, 200),
    ...                         user_time_scale='day')
    ...     
    ...     # Contagion: if cloud fails, DB has 60% chance of failing too
    ...     cloud @ db | 0.6
    ...     
    ...     # Define regular tasks
    ...     extract = RiskNode('extract', p_fail=0.01, 
    ...                        loss_dist=stats.norm(50, 10))
    ...     transform = RiskNode('transform', p_fail=0.05,
    ...                          loss_dist=stats.norm(100, 20))
    ...     
    ...     # Build dependency graph
    ...     db >> extract >> transform
    ...     
    ...     # Graph is automatically built when exiting context!
    >>> 
    >>> # Run simulation
    >>> results = dag.run_monte_carlo(n_simulations=1000)
    >>> print(results.summary_statistics())
    >>> 
    >>> # Visualize
    >>> from riskdag.visualization import plot_exceedance_curve
    >>> fig = plot_exceedance_curve(results)
    >>> fig.show()
"""

__version__ = '0.1.0'

from .core import (
    RiskNode,
    LatentRiskNode,
    create_latent_risk,
    RiskDAG,
    SimulationResults,
    TimeConverter,
    TimeScale,
    convert_prob,
)

from .ingestion import (
    from_airflow_dag,
    create_risk_dag_from_airflow,
    AirflowRiskAnnotator,
)

from .visualization import (
    RiskVisualizer,
    plot_exceedance_curve,
    plot_loss_distribution,
    plot_node_failure_rates,
    visualize_risk_dag,
    GraphVisualizer,  
)

__all__ = [
    # Core classes
    'RiskNode',
    'LatentRiskNode',
    'create_latent_risk',
    'RiskDAG',
    'SimulationResults',
    
    # Time conversion
    'TimeConverter',
    'TimeScale',
    'convert_prob',
    
    # Airflow integration
    'from_airflow_dag',
    'create_risk_dag_from_airflow',
    'AirflowRiskAnnotator',
    
    # Visualization
    'RiskVisualizer',
    'plot_exceedance_curve',
    'plot_loss_distribution',
    'plot_node_failure_rates',
    'visualize_risk_dag',
    'GraphVisualizer',  # ← ONLY ADDITION: Added to exports
]
