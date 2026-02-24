"""
Time scale conversion utilities for probability adjustment.
"""
from enum import Enum
from typing import Union
import math


class TimeScale(Enum):
    """Supported time scales for probability specification."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


# Conversion factors to hours (as base unit)
TIME_SCALE_TO_HOURS = {
    TimeScale.MINUTE: 1/60,
    TimeScale.HOUR: 1,
    TimeScale.DAY: 24,
    TimeScale.WEEK: 24 * 7,
    TimeScale.MONTH: 24 * 30,  # Approximate
    TimeScale.YEAR: 24 * 365,
}


class TimeConverter:
    """
    Converts failure probabilities between different time scales.
    
    Uses the exponential decay model: p(t) = 1 - exp(-λt)
    where λ is the failure rate.
    """
    
    @staticmethod
    def convert_probability(
        p_fail: float,
        from_scale: Union[str, TimeScale],
        to_scale: Union[str, TimeScale]
    ) -> float:
        """
        Convert probability from one time scale to another.
        
        Args:
            p_fail: Probability of failure in the source time scale
            from_scale: Source time scale
            to_scale: Target time scale
        
        Returns:
            Converted probability in target time scale
        
        Examples:
            >>> # Convert 1% daily failure prob to hourly
            >>> TimeConverter.convert_probability(0.01, 'day', 'hour')
            0.00042...
        """
        if isinstance(from_scale, str):
            from_scale = TimeScale(from_scale)
        if isinstance(to_scale, str):
            to_scale = TimeScale(to_scale)
        
        # Handle edge cases
        if p_fail == 0:
            return 0.0
        if p_fail >= 1:
            return 1.0
        
        # Get time ratios in hours
        from_hours = TIME_SCALE_TO_HOURS[from_scale]
        to_hours = TIME_SCALE_TO_HOURS[to_scale]
        
        # Calculate failure rate λ from source probability
        # p = 1 - exp(-λt) => λ = -ln(1-p)/t
        failure_rate = -math.log(1 - p_fail) / from_hours
        
        # Calculate probability in target time scale
        # p_new = 1 - exp(-λ * t_new)
        p_converted = 1 - math.exp(-failure_rate * to_hours)
        
        return p_converted
    
    @staticmethod
    def adjust_node_probability(
        node,
        dag_time_scale: Union[str, TimeScale],
        user_time_scale: Union[str, TimeScale]
    ):
        """
        Adjust a node's probability to match the DAG's time scale.
        
        Args:
            node: RiskNode or LatentRiskNode instance
            dag_time_scale: Time scale of DAG execution (e.g., 'hour' for hourly DAG)
            user_time_scale: Time scale user specified probability in
        """
        if node.p_fail > 0:
            node.p_fail = TimeConverter.convert_probability(
                node.p_fail,
                from_scale=user_time_scale,
                to_scale=dag_time_scale
            )


def convert_prob(
    p_fail: float,
    from_scale: str,
    to_scale: str
) -> float:
    """
    Convenience function for probability conversion.
    
    Args:
        p_fail: Probability in source time scale
        from_scale: Source time scale ('minute', 'hour', 'day', 'week', 'month', 'year')
        to_scale: Target time scale
    
    Returns:
        Converted probability
    
    Examples:
        >>> convert_prob(0.05, 'day', 'hour')  # 5% per day to hourly
        0.00213...
    """
    return TimeConverter.convert_probability(p_fail, from_scale, to_scale)
