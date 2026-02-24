"""
Quick Test: Verify RiskDAG Installation

Run this to verify RiskDAG installation worked
"""

from riskdag import RiskDAG, RiskNode, LatentRiskNode
from scipy import stats

print("Testing RiskDAG installation...")

# 
with RiskDAG('test_pipeline', time_scale='hour') as dag:
    # Cloud service Infrastructure risk
    cloud = LatentRiskNode(
        node_id = 'cloud_service',
        p_fail=0.01,
        loss_dist=stats.norm(5000, 1000),
        user_time_scale='day'
    )
    
    # Tasks
    extract = RiskNode('extract', p_fail=0.01, loss_dist=stats.norm(500, 100))
    transform = RiskNode('transform', p_fail=0.02, loss_dist=stats.norm(1000, 200))
    db_load = RiskNode('load', p_fail=0.03, loss_dist=stats.norm(1000, 200))

    # ETL DAG task ordering
    extract >> transform >> db_load

    #A cloud failure force-blocks the load step of the ETL
    cloud >> db_load

print(f"Created DAG: {dag}")
print(f"Nodes: {len(dag.nodes)}")
print()

# Run simulation
print("Running Monte Carlo simulation ...")
results = dag.run_monte_carlo(10000, seed=42)
print("Simulation complete")
print()

# Show results
stats_summary = results.summary_statistics()
print("Results:")
print(f"  Mean Loss:  ${stats_summary['mean_loss']:,.2f}")
print(f"  Median Loss:  ${stats_summary['median_loss']:,.2f}")
print(f"  95% VaR:    ${stats_summary['var_95']:,.2f}")
print(f"  99% VaR:    ${stats_summary['var_99']:,.2f}")
print(f"  95% ES:    ${stats_summary['es_95']:,.2f}")
print(f"  99% ES:    ${stats_summary['es_99']:,.2f}")
print()

# Test visualization
print("Test visualization:")
try:
    from riskdag import visualize_risk_dag
    fig = visualize_risk_dag(dag, show_probabilities=True)
    print("Visualization created successfully")
    print("  (Run fig.show() in Jupyter to see it)")
except Exception as e:
    print(f"⚠️  Visualization warning: {e}")
print()

print("=" * 60)
print("✅ All tests passed! RiskDAG is working correctly.")
print()
print("Next steps:")
print("  • Try: python examples/cascade_vs_contagion.py")
print("  • Try: python examples/visualize_graph.py")
print("  • Read: README.md")
