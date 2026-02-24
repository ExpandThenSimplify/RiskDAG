"""
RiskDAG Example: Graph Visualization with Exports

"""

from riskdag import (
    RiskDAG, 
    RiskNode, 
    LatentRiskNode, 
    visualize_risk_dag
)
from riskdag.visualization.graph_viz import GraphVisualizer
from scipy import stats


def create_example_dag():
    """Create an example RiskDAG for visualization."""
    
    with RiskDAG('etl_pipeline', time_scale='hour') as dag:
        # Latent infrastructure risks
        cloud = LatentRiskNode(
            'cloud_service_outage',
            p_fail=0.01,
            loss_dist=stats.norm(loc=5000, scale=1000),
            user_time_scale='day'
        )
        
        database = LatentRiskNode(
            'db_failure',
            p_fail=0.02,
            loss_dist=stats.norm(loc=10000, scale=2000),
            user_time_scale='day'
        )
        
        network = LatentRiskNode(
            'network_issues',
            p_fail=0.015,
            loss_dist=stats.norm(loc=3000, scale=500),
            user_time_scale='day'
        )
        
        cyber = LatentRiskNode(
            'cyber_attack',
            p_fail=0.005,
            loss_dist=stats.norm(loc=50000, scale=10000),
            user_time_scale='month'
        )
        
        # ETL tasks
        extract_customers = RiskNode(
            'extract_customers',
            p_fail=0.01,
            loss_dist=stats.norm(loc=500, scale=100)
        )
        
        extract_orders = RiskNode(
            'extract_orders',
            p_fail=0.015,
            loss_dist=stats.norm(loc=600, scale=120)
        )
        
        transform = RiskNode(
            'transform',
            p_fail=0.05,
            loss_dist=stats.norm(loc=1000, scale=200)
        )
        
        validate = RiskNode(
            'validate',
            p_fail=0.02,
            loss_dist=stats.norm(loc=1500, scale=300)
        )
        
        load = RiskNode(
            'load',
            p_fail=0.02,
            loss_dist=stats.norm(loc=800, scale=150)
        )
        
        # Contagion between latent risks
        cloud @ database | 0.7       # cloud outage affects database
        cloud @ network | 0.5        # cloud outage affects network
        cyber @ cloud | 0.4            # Cyber attack affects cloud
        cyber @ database | 0.5       # Cyber attack affects database
        
        # Latent risks to tasks
        database >> extract_customers  # DB down → extract ALWAYS fails
        database >> extract_orders     # DB down → extract ALWAYS fails
        network @ load | 0.7           # Network issues → 70% chance load fails
        cyber >> validate              # Cyber attack → validate fails
        
        # Task dependencies
        extract_customers >> transform
        extract_orders >> transform
        transform >> validate >> load
    
    return dag


def main():
    """Run the visualization example with exports."""
    print("=" * 70)
    print("RiskDAG Visualization & Export Example")
    print("=" * 70)
    print()
    
    # Create example DAG
    print("Creating example RiskDAG...")
    dag = create_example_dag()
    print(f"Created {dag}")
    print(f"Tasks: {sum(1 for n in dag.nodes.values() if not n.is_latent)}")
    print(f"Latent risks: {len(dag.latent_risks)}")
    print()
    
    # ========================================================================
    # HTML Export 
    # ========================================================================
    print("=" * 70)
    print("HTML Export")
    print("=" * 70)
    print()
    
    print("Creating HTML (standalone, no server needed)...")
    graph_html = GraphVisualizer.export_to_html(
        dag,
        filename='risk_dag_export.html',
        title="ETL Pipeline Risk Visualization",
        layout='dagre',
        show_probabilities=True,
        height='800px'
    )
    



if __name__ == '__main__':
    main()
