"""
RiskDAG Example: @ vs >> for Latent Risk to Task Relationships

This example demonstrates the difference between:
- latent >> task: Deterministic cascade (if latent triggers, task ALWAYS fails)
- latent @ task | prob: Probabilistic contagion (if latent triggers, task has prob% chance of failing)

Use cases:
- >> for hard dependencies (e.g., database down → extract ALWAYS fails)
- @ for partial dependencies (e.g., network issues → load has 70% chance of failing)
"""

from riskdag import RiskNode, LatentRiskNode, RiskDAG
from scipy import stats


def main():
    print("=" * 70)
    print("Example: @ vs >> for Latent Risk Relationships")
    print("=" * 70)
    print()
    
    # -------------------------------------------------------------------------
    # Scenario 1: Deterministic Cascade (>>)
    # -------------------------------------------------------------------------
    print("Scenario 1: Deterministic Cascade (>>)")
    print("-" * 70)
    
    with RiskDAG('deterministic_example', time_scale='hour') as dag1:
        # Database is critical - if it's down, extract ALWAYS fails
        db = LatentRiskNode(
            'database',
            p_fail=0.02,  # 2% daily
            loss_dist=stats.norm(10000, 2000),
            user_time_scale='day'
        )
        
        extract = RiskNode(
            'extract',
            p_fail=0.01,  # 1% independent failure
            loss_dist=stats.norm(500, 100)
        )
        
        # >> means: if DB fails, extract ALWAYS fails (100% deterministic)
        db >> extract
    
    results1 = dag1.run_monte_carlo(n_simulations=10000, seed=42)
    
    db_trigger_rate = results1.node_failure_rate('database')
    extract_failure_rate = results1.node_failure_rate('extract')
    
    print(f"Database trigger rate:      {db_trigger_rate:.2%}")
    print(f"Extract failure rate:       {extract_failure_rate:.2%}")
    print(f"Extract independent fail:   1.00%")
    print()
    print("Analysis:")
    print(f"  • Database triggers {db_trigger_rate:.2%} of the time")
    print(f"  • When DB triggers, extract ALWAYS fails (deterministic)")
    print(f"  • Extract also has 1% independent failure")
    print(f"  • Total extract failures ≈ {db_trigger_rate:.2%} + 1% = {extract_failure_rate:.2%}")
    print()
    
    # -------------------------------------------------------------------------
    # Scenario 2: Probabilistic Contagion (@)
    # -------------------------------------------------------------------------
    print("Scenario 2: Probabilistic Contagion (@)")
    print("-" * 70)
    
    with RiskDAG('probabilistic_example', time_scale='hour') as dag2:
        # Network issues are less critical - they might affect load, but not always
        network = LatentRiskNode(
            'network',
            p_fail=0.015,  # 1.5% daily
            loss_dist=stats.norm(5000, 1000),
            user_time_scale='day'
        )
        
        load = RiskNode(
            'load',
            p_fail=0.01,  # 1% independent failure
            loss_dist=stats.norm(800, 150)
        )
        
        # @ means: if network fails, load has 70% chance of failing
        network @ load | 0.7
    
    results2 = dag2.run_monte_carlo(n_simulations=10000, seed=42)
    
    network_trigger_rate = results2.node_failure_rate('network')
    load_failure_rate = results2.node_failure_rate('load')
    
    print(f"Network trigger rate:       {network_trigger_rate:.2%}")
    print(f"Load failure rate:          {load_failure_rate:.2%}")
    print(f"Load independent fail:      1.00%")
    print()
    print("Analysis:")
    print(f"  • Network triggers {network_trigger_rate:.2%} of the time")
    print(f"  • When network triggers, load has 70% chance of failing")
    print(f"  • Load also has 1% independent failure")
    print(f"  • Total load failures ≈ ({network_trigger_rate:.2%} × 70%) + 1% = {load_failure_rate:.2%}")
    print()
    
    # -------------------------------------------------------------------------
    # Scenario 3: Mixed (Both >> and @)
    # -------------------------------------------------------------------------
    print("Scenario 3: Mixed Deterministic and Probabilistic")
    print("-" * 70)
    
    with RiskDAG('mixed_example', time_scale='hour') as dag3:
        # Critical infrastructure
        db = LatentRiskNode(
            'database',
            p_fail=0.02,  # 2% daily
            loss_dist=stats.norm(10000, 2000),
            user_time_scale='day'
        )
        
        # Less critical infrastructure
        network = LatentRiskNode(
            'network',
            p_fail=0.015,  # 1.5% daily
            loss_dist=stats.norm(5000, 1000),
            user_time_scale='day'
        )
        
        extract = RiskNode(
            'extract',
            p_fail=0.01,
            loss_dist=stats.norm(500, 100)
        )
        
        transform = RiskNode(
            'transform',
            p_fail=0.05,
            loss_dist=stats.norm(1000, 200)
        )
        
        load = RiskNode(
            'load',
            p_fail=0.02,
            loss_dist=stats.norm(800, 150)
        )
        
        # Database is critical - deterministic cascade
        db >> extract  # If DB down, extract ALWAYS fails
        
        # Network issues are less critical - probabilistic
        network @ load | 0.7  # If network issues, load has 70% chance of failing
        
        # Task dependencies
        extract >> transform >> load
    
    results3 = dag3.run_monte_carlo(n_simulations=10000, seed=42)
    
    print("\nFailure Rates:")
    for node_id in ['extract', 'transform', 'load']:
        rate = results3.node_failure_rate(node_id)
        print(f"  {node_id:15s} {rate:6.2%}")
    
    print()
    print("Analysis:")
    print("  • Extract: Affected by DB (deterministic) + independent failures")
    print("  • Transform: Cascades from extract + independent failures")
    print("  • Load: Affected by network (70% prob) + cascade + independent")
    print()
    
 

if __name__ == '__main__':
    main()
