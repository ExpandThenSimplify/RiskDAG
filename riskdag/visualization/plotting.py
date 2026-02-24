"""
Visualization tools for risk analysis results.
"""
from typing import Optional, List
import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class RiskVisualizer:
    """
    Create interactive and static visualizations of risk analysis results.
    """
    
    @staticmethod
    def plot_exceedance_curve(
        results,
        confidence_levels: Optional[List[float]] = None,
        show_es: bool = True,
        title: str = "Loss Exceedance Curve",
        interactive: bool = True
    ):
        """
        Plot an exceedance curve showing probability of exceeding loss levels.
        
        Args:
            results: SimulationResults instance
            confidence_levels: List of confidence levels to highlight (e.g., [0.95, 0.99])
            show_es: Whether to show Expected Shortfall markers
            title: Plot title
            interactive: If True, use Plotly for interactive plot; else Matplotlib
        
        Returns:
            Plotly figure (if interactive=True) or Matplotlib figure
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]
        
        # Get exceedance curve data
        loss_levels, exceedance_probs = results.get_exceedance_curve()
        
        if interactive and PLOTLY_AVAILABLE:
            return RiskVisualizer._plot_exceedance_plotly(
                loss_levels, exceedance_probs, results,
                confidence_levels, show_es, title
            )
        elif MATPLOTLIB_AVAILABLE:
            return RiskVisualizer._plot_exceedance_matplotlib(
                loss_levels, exceedance_probs, results,
                confidence_levels, show_es, title
            )
        else:
            raise ImportError("Neither Plotly nor Matplotlib is available")
    
    @staticmethod
    def _plot_exceedance_plotly(
        loss_levels, exceedance_probs, results,
        confidence_levels, show_es, title
    ):
        """Create interactive Plotly exceedance curve."""
        fig = go.Figure()
        
        # Main exceedance curve
        fig.add_trace(go.Scatter(
            x=loss_levels,
            y=exceedance_probs,
            mode='lines',
            name='Exceedance Probability',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='Loss: $%{x:,.0f}<br>Exceedance Prob: %{y:.2%}<extra></extra>'
        ))
        
        # Add VaR and ES markers
        colors = ['#ff7f0e', '#d62728', '#9467bd', '#8c564b']
        for i, conf in enumerate(confidence_levels):
            var = results.get_quantile(conf)
            
            # VaR line
            fig.add_trace(go.Scatter(
                x=[var, var],
                y=[0, 1 - conf],
                mode='lines',
                name=f'VaR {conf:.0%}',
                line=dict(color=colors[i % len(colors)], width=2, dash='dash'),
                hovertemplate=f'VaR {conf:.0%}: $%{{x:,.0f}}<extra></extra>'
            ))
            
            if show_es:
                es = results.expected_shortfall(conf)
                # ES marker
                fig.add_trace(go.Scatter(
                    x=[es],
                    y=[1 - conf],
                    mode='markers',
                    name=f'ES {conf:.0%}',
                    marker=dict(
                        size=12,
                        color=colors[i % len(colors)],
                        symbol='diamond',
                        line=dict(color='white', width=2)
                    ),
                    hovertemplate=f'ES {conf:.0%}: $%{{x:,.0f}}<extra></extra>'
                ))
        
        # Update layout
        fig.update_layout(
            title=dict(text=title, font=dict(size=20)),
            xaxis=dict(
                title='Loss ($)',
                tickformat='$,.0f',
                gridcolor='lightgray',
                showgrid=True
            ),
            yaxis=dict(
                title='Exceedance Probability',
                tickformat='.0%',
                gridcolor='lightgray',
                showgrid=True,
                range=[0, 1]
            ),
            hovermode='x unified',
            plot_bgcolor='white',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="right",
                x=0.99,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="lightgray",
                borderwidth=1
            ),
            height=600,
            margin=dict(l=80, r=80, t=100, b=80)
        )
        
        return fig
    
    @staticmethod
    def _plot_exceedance_matplotlib(
        loss_levels, exceedance_probs, results,
        confidence_levels, show_es, title
    ):
        """Create static Matplotlib exceedance curve."""
        fig, ax = plt.subplots(figsize=(12, 7))
        
        # Main exceedance curve
        ax.plot(loss_levels, exceedance_probs, 'b-', linewidth=2, label='Exceedance Probability')
        
        # Add VaR and ES markers
        colors = ['orange', 'red', 'purple', 'brown']
        for i, conf in enumerate(confidence_levels):
            var = results.get_quantile(conf)
            
            # VaR line
            ax.axvline(var, color=colors[i % len(colors)], linestyle='--', 
                      linewidth=2, label=f'VaR {conf:.0%}: ${var:,.0f}')
            
            if show_es:
                es = results.expected_shortfall(conf)
                ax.plot(es, 1 - conf, 'D', color=colors[i % len(colors)],
                       markersize=10, label=f'ES {conf:.0%}: ${es:,.0f}',
                       markeredgecolor='white', markeredgewidth=2)
        
        ax.set_xlabel('Loss ($)', fontsize=12)
        ax.set_ylabel('Exceedance Probability', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', framealpha=0.9)
        
        # Format y-axis as percentage
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_loss_distribution(
        results,
        bins: int = 50,
        title: str = "Loss Distribution",
        interactive: bool = True
    ):
        """
        Plot histogram of total losses from simulations.
        
        Args:
            results: SimulationResults instance
            bins: Number of histogram bins
            title: Plot title
            interactive: If True, use Plotly; else Matplotlib
        
        Returns:
            Plotly or Matplotlib figure
        """
        if interactive and PLOTLY_AVAILABLE:
            fig = go.Figure()
            
            fig.add_trace(go.Histogram(
                x=results.total_losses,
                nbinsx=bins,
                name='Loss Distribution',
                marker=dict(color='#1f77b4', line=dict(color='white', width=1))
            ))
            
            # Add mean line
            mean_loss = results.total_losses.mean()
            fig.add_vline(
                x=mean_loss,
                line=dict(color='red', dash='dash', width=2),
                annotation_text=f'Mean: ${mean_loss:,.0f}',
                annotation_position="top"
            )
            
            fig.update_layout(
                title=title,
                xaxis_title='Total Loss ($)',
                yaxis_title='Frequency',
                plot_bgcolor='white',
                height=500
            )
            
            return fig
        
        elif MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            ax.hist(results.total_losses, bins=bins, color='#1f77b4', 
                   edgecolor='white', alpha=0.7)
            
            mean_loss = results.total_losses.mean()
            ax.axvline(mean_loss, color='red', linestyle='--', linewidth=2,
                      label=f'Mean: ${mean_loss:,.0f}')
            
            ax.set_xlabel('Total Loss ($)', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return fig
        
        else:
            raise ImportError("Neither Plotly nor Matplotlib is available")
    
    @staticmethod
    def plot_node_failure_rates(
        results,
        top_n: Optional[int] = None,
        title: str = "Node Failure Rates",
        interactive: bool = True
    ):
        """
        Plot failure rates for each node.
        
        Args:
            results: SimulationResults instance
            top_n: Show only top N nodes by failure rate (None = all)
            title: Plot title
            interactive: If True, use Plotly; else Matplotlib
        
        Returns:
            Plotly or Matplotlib figure
        """
        # Calculate failure rates
        node_failures = {}
        for node_id in results.dag.nodes.keys():
            if not results.dag.nodes[node_id].is_latent:
                node_failures[node_id] = results.node_failure_rate(node_id)
        
        # Sort and optionally limit
        sorted_nodes = sorted(node_failures.items(), key=lambda x: x[1], reverse=True)
        if top_n:
            sorted_nodes = sorted_nodes[:top_n]
        
        node_ids = [n[0] for n in sorted_nodes]
        failure_rates = [n[1] for n in sorted_nodes]
        
        if interactive and PLOTLY_AVAILABLE:
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=node_ids,
                x=failure_rates,
                orientation='h',
                marker=dict(color='#2ca02c'),
                text=[f'{rate:.1%}' for rate in failure_rates],
                textposition='outside'
            ))
            
            fig.update_layout(
                title=title,
                xaxis_title='Failure Rate',
                yaxis_title='Node',
                plot_bgcolor='white',
                height=max(400, len(node_ids) * 30),
                xaxis=dict(tickformat='.0%')
            )
            
            return fig
        
        elif MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(10, max(6, len(node_ids) * 0.4)))
            
            ax.barh(node_ids, failure_rates, color='#2ca02c')
            ax.set_xlabel('Failure Rate', fontsize=12)
            ax.set_ylabel('Node', fontsize=12)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='x')
            
            # Format x-axis as percentage
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0%}'))
            
            plt.tight_layout()
            return fig
        
        else:
            raise ImportError("Neither Plotly nor Matplotlib is available")


def plot_exceedance_curve(results, **kwargs):
    """Convenience function to plot exceedance curve."""
    return RiskVisualizer.plot_exceedance_curve(results, **kwargs)


def plot_loss_distribution(results, **kwargs):
    """Convenience function to plot loss distribution."""
    return RiskVisualizer.plot_loss_distribution(results, **kwargs)


def plot_node_failure_rates(results, **kwargs):
    """Convenience function to plot node failure rates."""
    return RiskVisualizer.plot_node_failure_rates(results, **kwargs)
