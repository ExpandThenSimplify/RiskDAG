"""Airflow DAG ingestion utilities."""

from .airflow_adapter import (
    from_airflow_dag,
    create_risk_dag_from_airflow,
    AirflowRiskAnnotator
)

__all__ = [
    'from_airflow_dag',
    'create_risk_dag_from_airflow',
    'AirflowRiskAnnotator',
]
