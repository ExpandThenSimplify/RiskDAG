"""
RiskDAG Example: Simplest Possible Pattern (Auto-Build)


"""

try:
    from airflow import DAG
    from airflow.providers.standard.operators.empty import EmptyOperator
    from airflow.models import DagBag
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False

from datetime import datetime
from scipy import stats
from riskdag import create_risk_dag_from_airflow, LatentRiskNode, RiskDAG, RiskNode, GraphVisualizer


def main():
    print("=" * 70)
    print("Simplest Possible Pattern - Auto-Build")
    print("=" * 70)
    print()
    
    # -------------------------------------------------------------------------
    # Pattern 1: Airflow Integration (No Manual build_graph!)
    # -------------------------------------------------------------------------
    print("Pattern 1: Airflow Integration")
    print("-" * 70)
    
    if AIRFLOW_AVAILABLE:
        # Use 'schedule' parameter for Airflow 2.4+, 'schedule_interval' for older versions
        try:
            dag = DAG('etl', start_date=datetime(2024, 1, 1), schedule='@hourly')
        except TypeError:
            # Fallback for Airflow < 2.4
            dag = DAG('etl', start_date=datetime(2024, 1, 1), schedule_interval='@hourly')
        with dag:
            extract = EmptyOperator(task_id='extract')
            transform = EmptyOperator(task_id='transform')
            load = EmptyOperator(task_id='load')
            extract >> transform >> load
        
        annotations = {
            'extract': {'p_fail': 0.01, 'loss_dist': stats.norm(500, 100)},
            'transform': {'p_fail': 0.05, 'loss_dist': stats.norm(1000, 200)},
            'load': {'p_fail': 0.02, 'loss_dist': stats.norm(800, 150)}
        }
        
        risk_dag = create_risk_dag_from_airflow(dag, annotations, time_scale='hour')
    else:
        risk_dag = RiskDAG('etl', time_scale='hour')
        extract = RiskNode('extract', p_fail=0.01, loss_dist=stats.norm(500, 100))
        transform = RiskNode('transform', p_fail=0.05, loss_dist=stats.norm(1000, 200))
        load = RiskNode('load', p_fail=0.02, loss_dist=stats.norm(800, 150))
        extract >> transform >> load
        risk_dag.add_nodes([extract, transform, load])
    
    # Create and link latent risks
    cloud = LatentRiskNode('cloud', p_fail=0.01, loss_dist=stats.norm(5000, 1000))
    db = LatentRiskNode('db', p_fail=0.02, loss_dist=stats.norm(10000, 2000))
    
    cloud @ db | 0.6
    cloud >> risk_dag.nodes['extract']
    db >> risk_dag.nodes['extract']
    
    # NO build_graph() needed - just run simulation!
    results = risk_dag.run_monte_carlo(1000, seed=42)
    
    print(f"✓ Simulation complete (auto-built graph with {len(risk_dag.nodes)} nodes)")
    print(f"  95% VaR: ${results.get_quantile(0.95):,.2f}")
    print()
    
    # Export visualization
    GraphVisualizer.export_to_html(risk_dag, 'pattern1_airflow_dag.html', 
                                       title='Pattern 1: Airflow Integration')
    print(f"✓ Exported visualization to: pattern1_airflow_dag.html")
    print()
    
    # -------------------------------------------------------------------------
    # Pattern 2: Context Manager (Auto-Build on Exit)
    # -------------------------------------------------------------------------
    print("Pattern 2: Context Manager")
    print("-" * 70)
    
    with RiskDAG('pipeline', time_scale='hour') as dag:
        cloud = LatentRiskNode('cloud', p_fail=0.01, 
                             loss_dist=stats.norm(5000, 1000),
                             user_time_scale='day')
        extract = RiskNode('extract', p_fail=0.01,
                           loss_dist=stats.norm(500, 100))
        
        cloud >> extract
        # Auto-builds on exit!
    
    # Just run!
    results = dag.run_monte_carlo(1000, seed=42)
    
    print(f"✓ Simulation complete (auto-built on context exit)")
    print(f"  95% VaR: ${results.get_quantile(0.95):,.2f}")
    print()
    
    # Export visualization
    GraphVisualizer.export_to_html(dag, 'pattern2_context_manager.html',
                                       title='Pattern 2: Context Manager')
    print(f"✓ Exported visualization to: pattern2_context_manager.html")
    print()
    
    # -------------------------------------------------------------------------
    # Pattern 3: Pure Python (Auto-Build on Simulation)
    # -------------------------------------------------------------------------
    print("Pattern 3: Pure Python")
    print("-" * 70)
    
    dag = RiskDAG('simple', time_scale='hour')
    
    task_a = RiskNode('A', p_fail=0.05, loss_dist=stats.norm(100, 10))
    task_b = RiskNode('B', p_fail=0.05, loss_dist=stats.norm(200, 20))
    
    task_a >> task_b
    
    dag.add_nodes([task_a, task_b])
    
    # NO build_graph() - just run!
    results = dag.run_monte_carlo(1000, seed=42)
    
    print(f"✓ Simulation complete (auto-built before simulation)")
    print(f"  95% VaR: ${results.get_quantile(0.95):,.2f}")
    print()
    
    # Export visualization
    GraphVisualizer.export_to_html(dag, 'pattern3_pure_python.html',
                                       title='Pattern 3: Pure Python')
    print(f"✓ Exported visualization to: pattern3_pure_python.html")
    print()
    
    # -------------------------------------------------------------------------
    # Pattern 4: Import from DagBag (Real Airflow DAGs)
    # -------------------------------------------------------------------------
    print("Pattern 4: Import from DagBag")
    print("-" * 70)
    
    if AIRFLOW_AVAILABLE:
        # Create a sample DAG to demonstrate DagBag loading
        # In production, you'd point this to your actual dags_folder
        
        # First, create a sample DAG file
        sample_dag_code = '''
from airflow import DAG
from airflow.providers.standard.operators.empty import EmptyOperator
from datetime import datetime

try:
    dag = DAG(
        'sample_production_dag',
        start_date=datetime(2024, 1, 1),
        schedule='@daily',
        catchup=False,
        tags=['production', 'sample']
    )
except TypeError:
    dag = DAG(
        'sample_production_dag',
        start_date=datetime(2024, 1, 1),
        schedule_interval='@daily',
        catchup=False,
        tags=['production', 'sample']
    )

with dag:
    extract = EmptyOperator(task_id='extract_data')
    transform = EmptyOperator(task_id='transform_data')
    load = EmptyOperator(task_id='load_data')
    validate = EmptyOperator(task_id='validate_data')
    
    extract >> transform >> load >> validate
'''
        
        # Write sample DAG to a temporary file
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            dag_file = os.path.join(tmp_dir, 'sample_dag.py')
            with open(dag_file, 'w') as f:
                f.write(sample_dag_code)
            
            # Load DAG using DagBag
            print(f"Loading DAGs from: {tmp_dir}")
            dagbag = DagBag(dag_folder=tmp_dir, include_examples=False)
            
            if dagbag.import_errors:
                print(f" Import errors: {dagbag.import_errors}")
            
            # Get the DAG
            airflow_dag = dagbag.get_dag('sample_production_dag')
            
            if airflow_dag:
                print(f"✓ Loaded DAG: {airflow_dag.dag_id}")
                print(f"  Tasks: {len(airflow_dag.tasks)}")
                print(f"  Task IDs: {[t.task_id for t in airflow_dag.tasks]}")
                print()
                
                # Annotate with risk parameters
                annotations = {
                    'extract_data': {
                        'p_fail': 0.01,
                        'loss_dist': stats.norm(500, 100)
                    },
                    'transform_data': {
                        'p_fail': 0.05,
                        'loss_dist': stats.norm(1000, 200)
                    },
                    'load_data': {
                        'p_fail': 0.02,
                        'loss_dist': stats.norm(800, 150)
                    },
                    'validate_data': {
                        'p_fail': 0.03,
                        'loss_dist': stats.norm(600, 120)
                    }
                }
                
                # Create RiskDAG from the imported Airflow DAG
                risk_dag = create_risk_dag_from_airflow(
                    airflow_dag, 
                    annotations, 
                    time_scale='day'
                )
                
                # Add latent risks
                cloud = LatentRiskNode(
                    'cloud_provider',
                    p_fail=0.005,
                    loss_dist=stats.norm(10000, 2000),
                    user_time_scale='month'
                )
                
                # Link latent risk to tasks
                cloud >> risk_dag.nodes['extract_data']
                cloud >> risk_dag.nodes['load_data']
                
                # Run simulation
                results = risk_dag.run_monte_carlo(1000, seed=42)
                
                print(f"✓ Simulation complete (loaded from DagBag)")
                print(f"  95% VaR: ${results.get_quantile(0.95):,.2f}")
                print()
                
                # Export visualization
                GraphVisualizer.export_to_html(
                    risk_dag, 
                    'pattern4_dagbag_import.html',
                    title='Pattern 4: DagBag Import'
                )
                print(f"✓ Exported visualization to: pattern4_dagbag_import.html")
                print()
            else:
                print("⚠️  Could not load DAG from DagBag")
                print()
    else:
        print("⚠️  Airflow not available - skipping DagBag example")
        print()
    print()


if __name__ == '__main__':
    main()
