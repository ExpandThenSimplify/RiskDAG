"""
Adapter for importing Airflow DAGs into RiskDAG.
"""
from typing import Dict, Optional, TYPE_CHECKING
import networkx as nx

if TYPE_CHECKING:
    from airflow import DAG
    from airflow.models import BaseOperator

from ..core.graph import RiskDAG
from ..core.nodes import RiskNode


def from_airflow_dag(
    airflow_dag: 'DAG',
    dag_id: Optional[str] = None,
    time_scale: str = 'hour'
) -> nx.DiGraph:
    """
    Convert an Airflow DAG into a NetworkX graph.
    This is a thin one-way adapter that extracts topology only.
    
    Args:
        airflow_dag: Airflow DAG instance
        dag_id: Optional ID for the resulting graph (defaults to airflow_dag.dag_id)
        time_scale: Time scale for risk modeling
    
    Returns:
        NetworkX DiGraph with task topology
    
    Example:
        >>> from airflow import DAG
        >>> from datetime import datetime
        >>> 
        >>> dag = DAG('example', start_date=datetime(2024, 1, 1))
        >>> # ... define tasks ...
        >>> 
        >>> graph = from_airflow_dag(dag)
    """
    G = nx.DiGraph()
    G.graph['dag_id'] = dag_id or airflow_dag.dag_id
    G.graph['time_scale'] = time_scale
    
    # Add nodes from tasks
    for task in airflow_dag.tasks:
        G.add_node(task.task_id, task=task)
    
    # Add edges from dependencies
    for task in airflow_dag.tasks:
        for downstream in task.downstream_list:
            G.add_edge(task.task_id, downstream.task_id)
    
    return G


def create_risk_dag_from_airflow(
    airflow_dag: 'DAG',
    risk_annotations: Optional[Dict[str, Dict]] = None,
    time_scale: str = 'hour',
    dag_id: Optional[str] = None
) -> RiskDAG:
    """
    Create a RiskDAG from an Airflow DAG with risk annotations.
    
    Args:
        airflow_dag: Airflow DAG instance
        risk_annotations: Dict mapping task_id to risk parameters
            Example: {
                'task_1': {'p_fail': 0.01, 'loss_dist': stats.norm(100, 10)},
                'task_2': {'p_fail': 0.05, 'loss_dist': stats.norm(500, 50)}
            }
        time_scale: Time scale for the DAG
        dag_id: Optional custom ID (defaults to airflow_dag.dag_id + '_risk')
    
    Returns:
        RiskDAG instance with nodes populated from Airflow tasks
    
    Example:
        >>> from scipy import stats
        >>> 
        >>> annotations = {
        ...     'extract': {'p_fail': 0.01, 'loss_dist': stats.norm(100, 20)},
        ...     'transform': {'p_fail': 0.02, 'loss_dist': stats.norm(200, 30)}
        ... }
        >>> 
        >>> risk_dag = create_risk_dag_from_airflow(airflow_dag, annotations)
    """
    risk_annotations = risk_annotations or {}
    
    # Create RiskDAG
    risk_dag_id = dag_id or f"{airflow_dag.dag_id}_risk"
    risk_dag = RiskDAG(risk_dag_id, time_scale=time_scale)
    
    # Create RiskNode for each task
    task_to_node = {}
    for task in airflow_dag.tasks:
        task_id = task.task_id
        
        # Get risk parameters from annotations
        annotation = risk_annotations.get(task_id, {})
        p_fail = annotation.get('p_fail', 0.0)
        loss_dist = annotation.get('loss_dist', None)
        
        # Create node
        node = RiskNode(task_id, p_fail=p_fail, loss_dist=loss_dist)
        task_to_node[task_id] = node
        risk_dag.add_node(node)
    
    # Build dependencies using >> operator
    for task in airflow_dag.tasks:
        source_node = task_to_node[task.task_id]
        for downstream in task.downstream_list:
            target_node = task_to_node[downstream.task_id]
            source_node >> target_node
    
    # Build the graph
    risk_dag.build_graph()
    
    return risk_dag


class AirflowRiskAnnotator:
    """
    Helper class to annotate Airflow tasks with risk parameters.
    """
    
    def __init__(self):
        self.annotations: Dict[str, Dict] = {}
    
    def annotate(
        self, 
        task_id: str,
        p_fail: float,
        loss_dist,
        time_scale: Optional[str] = None
    ):
        """
        Annotate a task with risk parameters.
        
        Args:
            task_id: Task identifier
            p_fail: Failure probability
            loss_dist: Scipy distribution for losses
            time_scale: Optional time scale specification
        """
        self.annotations[task_id] = {
            'p_fail': p_fail,
            'loss_dist': loss_dist
        }
        if time_scale:
            self.annotations[task_id]['time_scale'] = time_scale
    
    def get_annotations(self) -> Dict[str, Dict]:
        """Get all annotations."""
        return self.annotations
