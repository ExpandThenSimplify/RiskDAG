"""
Interactive exceedance curve with DAG snapshot visualization.

Click on the curve to see the exact DAG state for that simulation,
with failed nodes highlighted and costs shown.
"""
from typing import Optional, Dict, List, Tuple
import numpy as np
import json
import threading
import time
import networkx as nx

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import ipycytoscape
    from ipycytoscape import Node, Edge
    CYTOSCAPE_AVAILABLE = True
except ImportError:
    CYTOSCAPE_AVAILABLE = False
    Node = None
    Edge = None

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML
    WIDGETS_AVAILABLE = True
except ImportError:
    WIDGETS_AVAILABLE = False


class InteractiveExceedanceDashboard:
    """
    Interactive dashboard with exceedance curve and DAG snapshots.
    
    Features:
    - Click on exceedance curve to see DAG state
    - Failed nodes highlighted in red
    - ES 95% region highlighted
    - Draggable node layout persists across snapshots
    """
    
    def __init__(self, risk_dag, results, es_percentile=0.95):
        """
        Initialize dashboard.
        
        Args:
            risk_dag: RiskDAG instance
            results: SimulationResults from run_monte_carlo
            es_percentile: Percentile for Expected Shortfall (default 0.95)
        """
        self.risk_dag = risk_dag
        self.results = results
        self.es_percentile = es_percentile
        
        # Calculate ES threshold
        self.es_threshold = np.percentile(results.total_losses, es_percentile * 100)
        
        # Store current layout (persists across snapshots)
        self.current_layout = {}
        
        # Store widgets
        self.output_widget = None
        self.dag_output = None
        self.stats_output = None
        self.es_contributors_output = None
        self.failure_patterns_output = None
        self.root_cause_partition_output = None
        
    def create_dashboard(self):
        """Create the interactive dashboard."""
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly required. Install: pip install plotly")
        if not WIDGETS_AVAILABLE:
            raise ImportError("ipywidgets required. Install: pip install ipywidgets")
        
        # Create main layout
        self.output_widget = widgets.Output()
        
        # Create dag_output with explicit no-scroll layout
        self.dag_output = widgets.Output(
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none'
            )
        )
        
        # Create stats panel output (updates per simulation)
        self.stats_output = widgets.Output(
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none'
            )
        )
        
        # Create ES contributors panel (static, shown once)
        self.es_contributors_output = widgets.Output(
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none'
            )
        )
        
        # Create failure patterns panel (static, shown once)
        self.failure_patterns_output = widgets.Output(
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none'
            )
        )
        
        # Create root cause partition panel (static, shown once)
        self.root_cause_partition_output = widgets.Output(
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none'
            )
        )
        
        # Create exceedance curve with FigureWidget for interactivity
        fig_widget = self._create_interactive_exceedance_curve()
        
        # Create simulation selector
        self.sim_slider = widgets.IntSlider(
            value=0,
            min=0,
            max=len(self.results.total_losses) - 1,
            step=1,
            description='Simulation:',
            continuous_update=False,
            layout=widgets.Layout(width='600px')
        )
        
        # Create loss display
        self.loss_label = widgets.HTML(
            value=f"<b>Loss:</b> ${self.results.total_losses[0]:,.0f}"
        )
        
        # Wire up slider to update DAG
        def on_slider_change(change):
            sim_idx = change['new']
            self.loss_label.value = f"<b>Loss:</b> ${self.results.total_losses[sim_idx]:,.0f}"
            self.show_simulation(sim_idx)
        
        self.sim_slider.observe(on_slider_change, names='value')
        
        # Create quick access buttons
        sorted_indices = np.argsort(self.results.total_losses)[::-1]
        
        median_idx = sorted_indices[len(sorted_indices) // 2]
        p95_idx = sorted_indices[int(len(sorted_indices) * 0.05)]
        p99_idx = sorted_indices[int(len(sorted_indices) * 0.01)]
        worst_idx = sorted_indices[0]
        
        btn_median = widgets.Button(description='Median', button_style='info')
        btn_p95 = widgets.Button(description='95th %ile', button_style='warning')
        btn_p99 = widgets.Button(description='99th %ile', button_style='danger')
        btn_worst = widgets.Button(description='Worst Case', button_style='danger')
        
        def show_median(b):
            self.sim_slider.value = median_idx
        def show_p95(b):
            self.sim_slider.value = p95_idx
        def show_p99(b):
            self.sim_slider.value = p99_idx
        def show_worst(b):
            self.sim_slider.value = worst_idx
        
        btn_median.on_click(show_median)
        btn_p95.on_click(show_p95)
        btn_p99.on_click(show_p99)
        btn_worst.on_click(show_worst)
        
        # Add Save Layout button
        btn_save_layout = widgets.Button(
            description='Save Layout',
            button_style='success',
            tooltip='Save current node arrangement to persist across simulations'
        )
        
        def save_layout_click(b):
            self.save_current_layout()
            # Update button to show success
            btn_save_layout.description = 'Layout Saved'
            import threading
            def reset_button():
                time.sleep(2)
                btn_save_layout.description = 'Save Layout'
            threading.Thread(target=reset_button, daemon=True).start()
        
        btn_save_layout.on_click(save_layout_click)
        
        quick_buttons = widgets.HBox(
            [
                widgets.Label('Quick Select:'),
                btn_median, btn_p95, btn_p99, btn_worst,
                widgets.Label('  Layout:'),
                btn_save_layout
            ],
            layout=widgets.Layout(
                width='100%',
                display='flex',
                flex_flow='row wrap',
                align_items='center'
            )
        )
        
        # Create instruction text
        instructions = widgets.HTML(
            value="<style>"
                  ".widget-vbox, .widget-output, .jp-OutputArea-output { "
                  "overflow: visible !important; "
                  "height: auto !important; "
                  "max-height: none !important; "
                  "}"
                  "</style>"
                  "<h3>Interactive Risk Dashboard</h3>"
                  "<p>Use the <b>slider below</b> or <b>click buttons</b> to explore different simulations.</p>"
                  "<ul>"
                  "<li><b>Red nodes</b> = Failed in this simulation</li>"
                  "<li><b>Red edges</b> = Failure propagation path</li>"
                  "<li><b>Node labels</b> = Cost impact</li>"
                  "<li><b>Pink region on curve</b> = ES 95% tail</li>"
                  "</ul>"
                  "<p><i>Drag nodes to rearrange, then click <b>Save Layout</b> to persist the arrangement!</i></p>"
        )
        
        # Create ES summary
        es_summary = self._create_es_summary()
        
        # Controls section
        controls = widgets.VBox([
            widgets.HBox([self.sim_slider, self.loss_label]),
            quick_buttons
        ])
        
        # Layout - stats panel sits beside the exceedance curve
        top_panel = widgets.HBox(
            [fig_widget, self.stats_output],
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                align_items='flex-start'
            )
        )
        
        main_layout = widgets.VBox(
            [
                instructions,
                es_summary,
                top_panel,
                controls,
                self.dag_output,
                self.es_contributors_output,
                self.failure_patterns_output,
                self.root_cause_partition_output
            ],
            layout=widgets.Layout(
                overflow='visible',
                height='auto',
                max_height='none',
                width='100%'
            )
        )
        
        # Show initial simulation
        self.show_simulation(0)
        
        # Populate ES contributors panel
        self._update_es_contributors_panel()
        
        # Populate failure patterns panel
        self._update_failure_patterns_panel()
        
        # Populate root cause partition panel
        self._update_root_cause_partition_panel()
        
        # Store for export capability
        self.main_widget = main_layout
        
        return main_layout
    
    def _create_interactive_exceedance_curve(self):
        """Create interactive exceedance curve with FigureWidget."""
        # Sort losses (high to low for exceedance)
        sorted_losses = np.sort(self.results.total_losses)[::-1]
        n = len(sorted_losses)
        
        # Calculate exceedance probabilities
        exceedance_probs = np.arange(1, n + 1) / n
        
        # Find ES region
        es_mask = sorted_losses >= self.es_threshold
        
        # Create FigureWidget for interactivity
        fig = go.FigureWidget()
        
        # Add ES region (pink background) - now as vertical band
        es_losses = sorted_losses[es_mask]
        es_probs = exceedance_probs[es_mask]
        
        if len(es_losses) > 0:
            # Add shaded region between min and max ES loss
            fig.add_trace(go.Scatter(
                x=[es_losses.min(), es_losses.max(), es_losses.max(), es_losses.min(), es_losses.min()],
                y=[0, 0, 1, 1, 0],
                fill='toself',
                fillcolor='rgba(255, 182, 193, 0.3)',
                line=dict(width=0),
                showlegend=True,
                name=f'ES {self.es_percentile*100:.0f}% Tail',
                hoverinfo='skip'
            ))
        
        # Add main curve - FLIPPED AXES: x=loss, y=probability
        scatter = go.Scatter(
            x=sorted_losses,
            y=exceedance_probs,
            mode='lines+markers',
            marker=dict(size=4, opacity=0.3),
            line=dict(color='#1f77b4', width=3),
            name='Exceedance Curve',
            hovertemplate=(
                '<b>Loss:</b> $%{x:,.0f}<br>'
                '<b>Probability:</b> %{y:.2%}<br>'
                '<extra></extra>'
            )
        )
        fig.add_trace(scatter)
        
        # Add ES threshold line (vertical)
        fig.add_vline(
            x=self.es_threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"ES {self.es_percentile*100:.0f}%<br>${self.es_threshold:,.0f}",
            annotation_position="top"
        )
        
        # Add VaR markers
        var_95 = np.percentile(self.results.total_losses, 95)
        var_99 = np.percentile(self.results.total_losses, 99)
        
        # Find probabilities for VaR points
        var_95_prob = np.sum(self.results.total_losses >= var_95) / len(self.results.total_losses)
        var_99_prob = np.sum(self.results.total_losses >= var_99) / len(self.results.total_losses)
        
        fig.add_trace(go.Scatter(
            x=[var_95, var_99],
            y=[var_95_prob, var_99_prob],
            mode='markers',
            marker=dict(size=12, color='red', symbol='diamond'),
            name='VaR Levels',
            text=[f'VaR 95%: ${var_95:,.0f}', f'VaR 99%: ${var_99:,.0f}'],
            hoverinfo='text'
        ))
        
        # Update layout - FLIPPED AXES
        fig.update_layout(
            title='Interactive Risk Exceedance Curve',
            xaxis_title='Loss ($)',
            yaxis_title='Probability of Exceedance',
            hovermode='closest',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5
            )
        )
        
        fig.update_xaxes(tickformat='$,.0f')
        fig.update_yaxes(tickformat='.0%')
        
        # Add click handler
        def on_click(trace, points, selector):
            if points.point_inds:
                idx = points.point_inds[0]
                # Map from sorted index to original index
                sorted_indices = np.argsort(self.results.total_losses)[::-1]
                sim_idx = sorted_indices[idx]
                
                # Update slider
                if hasattr(self, 'sim_slider'):
                    self.sim_slider.value = sim_idx
        
        # Attach click handler to the main curve (trace index 1)
        if len(fig.data) > 1:
            fig.data[1].on_click(on_click)
        
        return fig
    
    def _create_exceedance_curve(self):
        """Create static exceedance curve (legacy method)."""
        # Just call the interactive version
        return self._create_interactive_exceedance_curve()
    
    def _create_es_summary(self):
        """Create ES summary statistics widget."""
        # Calculate ES
        es_losses = self.results.total_losses[
            self.results.total_losses >= self.es_threshold
        ]
        es_mean = np.mean(es_losses)
        
        # Calculate node contributions to ES
        es_indices = np.where(self.results.total_losses >= self.es_threshold)[0]
        
        node_contributions = {}
        for node_id in self.risk_dag.nodes.keys():
            node_losses_in_es = []
            for idx in es_indices:
                sim_result = self.results.runs[idx]
                if node_id in sim_result and sim_result[node_id]['failed']:
                    node_losses_in_es.append(sim_result[node_id]['loss'])
            
            if node_losses_in_es:
                node_contributions[node_id] = {
                    'mean': np.mean(node_losses_in_es),
                    'total': np.sum(node_losses_in_es),
                    'frequency': len(node_losses_in_es) / len(es_indices)
                }
        
        # Sort by total contribution
        sorted_contributions = sorted(
            node_contributions.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )[:5]
        
        # Create HTML summary
        html = f"""
        <div style='background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 10px 0;'>
            <h4>Expected Shortfall (ES) at {self.es_percentile*100:.0f}%</h4>
            <p><b>ES Threshold:</b> ${self.es_threshold:,.0f}</p>
            <p><b>ES Mean:</b> ${es_mean:,.0f}</p>
            <p><b>Number of scenarios in tail:</b> {len(es_losses)}</p>
            
            <h5>Top 5 Contributors to ES:</h5>
            <table style='width: 100%;'>
                <tr style='background-color: #d0d0d0;'>
                    <th>Node</th>
                    <th>Avg Loss in ES</th>
                    <th>Failure Rate in ES</th>
                </tr>
        """
        
        for node_id, contrib in sorted_contributions:
            html += f"""
                <tr>
                    <td><b>{node_id}</b></td>
                    <td>${contrib['mean']:,.0f}</td>
                    <td>{contrib['frequency']*100:.1f}%</td>
                </tr>
            """
        
        html += """
            </table>
        </div>
        """
        
        return widgets.HTML(value=html)
    
    def _update_es_contributors_panel(self):
        """Update the ES contributors panel with ranked node contributions (direct + indirect)."""
        if not self.es_contributors_output:
            return
        
        # Calculate ES and tail metrics
        tail_mask = self.results.total_losses >= self.es_threshold
        tail_indices = np.where(tail_mask)[0]
        n_tail = len(tail_indices)
        n_total = len(self.results.total_losses)
        es_value = np.mean(self.results.total_losses[tail_mask])
        sum_tail_losses = np.sum(self.results.total_losses[tail_mask])
        
        # Calculate DIRECT node contributions to ES
        node_direct_contributions = {}
        for node_id in self.risk_dag.nodes.keys():
            node_losses_in_tail = []
            failure_count = 0
            
            for idx in tail_indices:
                sim_result = self.results.runs[idx]
                if node_id in sim_result and sim_result[node_id].get('failed', False):
                    loss = sim_result[node_id].get('loss', 0)
                    node_losses_in_tail.append(loss)
                    failure_count += 1
            
            if node_losses_in_tail:
                total_direct_loss = np.sum(node_losses_in_tail)
                es_direct_dollar = total_direct_loss / n_tail
                es_direct_pct = (total_direct_loss / sum_tail_losses) * 100
                
                node_direct_contributions[node_id] = {
                    'es_direct_dollar': es_direct_dollar,
                    'es_direct_pct': es_direct_pct,
                    'avg_loss_when_failed': np.mean(node_losses_in_tail),
                    'failure_rate_in_tail': (failure_count / n_tail) * 100,
                    'total_direct_loss': total_direct_loss
                }
        
        # Calculate INDIRECT contributions (downstream costs caused by this node)
        node_indirect_contributions = {}
        for node_id in self.risk_dag.nodes.keys():
            indirect_losses = []
            
            for idx in tail_indices:
                sim_result = self.results.runs[idx]
                
                # Check if this node failed in this scenario
                if node_id not in sim_result or not sim_result[node_id].get('failed', False):
                    continue
                
                # Find all downstream nodes that failed due to this node
                # Direct cascade: children that failed
                downstream_loss = 0
                for child_id in self.risk_dag.graph.successors(node_id):
                    if child_id in sim_result and sim_result[child_id].get('failed', False):
                        # Check if child failed due to cascade
                        cause = sim_result[child_id].get('failure_cause')
                        if cause in ['cascade', 'latent_risk']:
                            downstream_loss += sim_result[child_id].get('loss', 0)
                
                indirect_losses.append(downstream_loss)
            
            if indirect_losses:
                total_indirect = np.sum(indirect_losses)
                node_indirect_contributions[node_id] = {
                    'es_indirect_dollar': total_indirect / n_tail,
                    'es_indirect_pct': (total_indirect / sum_tail_losses) * 100,
                    'total_indirect_loss': total_indirect
                }
        
        # Combine direct + indirect
        combined_contributions = {}
        all_nodes = set(node_direct_contributions.keys()) | set(node_indirect_contributions.keys())
        
        for node_id in all_nodes:
            direct = node_direct_contributions.get(node_id, {})
            indirect = node_indirect_contributions.get(node_id, {})
            
            es_direct = direct.get('es_direct_dollar', 0)
            es_indirect = indirect.get('es_indirect_dollar', 0)
            es_total = es_direct + es_indirect
            
            combined_contributions[node_id] = {
                'es_direct_dollar': es_direct,
                'es_direct_pct': direct.get('es_direct_pct', 0),
                'es_indirect_dollar': es_indirect,
                'es_indirect_pct': indirect.get('es_indirect_pct', 0),
                'es_total_dollar': es_total,
                'es_total_pct': direct.get('es_direct_pct', 0) + indirect.get('es_indirect_pct', 0),
                'avg_loss_when_failed': direct.get('avg_loss_when_failed', 0),
                'failure_rate_in_tail': direct.get('failure_rate_in_tail', 0)
            }
        
        # Rank by TOTAL attribution (descending)
        ranked_contributors = sorted(
            combined_contributions.items(),
            key=lambda x: x[1]['es_total_dollar'],
            reverse=True
        )[:5]
        
        # Build HTML
        html = f"""
        <div style='background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;
                    padding:20px;margin:16px 0;max-width:1100px;'>
            <h3 style='margin:0 0 16px 0;color:#333;border-bottom:2px solid #dee2e6;
                       padding-bottom:8px;'>
                Top 5 Contributors to ES - Root Cause Attribution
            </h3>
            
            <div style='background:#e7f3ff;padding:10px;border-radius:4px;margin-bottom:12px;
                        font-size:12px;color:#555;'>
                <b>How to read this table:</b><br>
                <b>Direct ES</b> = Node's own losses when it fails (Σ losses / n_tail)<br>
                <b>Indirect ES</b> = Downstream losses it causes (losses of nodes it triggered)<br>
                <b>Total ES</b> = Direct + Indirect (full root cause impact)<br>
                This shows which failures have the largest <i>total</i> impact including cascades.
            </div>
        """
        
        if not ranked_contributors:
            html += "<p style='color:#888;font-style:italic;'>No node failures in ES tail scenarios.</p>"
        else:
            html += """
            <table style='width:100%;border-collapse:collapse;font-size:13px;'>
                <thead>
                    <tr style='background:#343a40;color:white;'>
                        <th style='text-align:center;padding:10px;border-right:1px solid #555;width:50px;'>Rank</th>
                        <th style='text-align:left;padding:10px;border-right:1px solid #555;'>Node</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Direct ES ($)</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Indirect ES ($)</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'><b>Total ES ($)</b></th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Total %</th>
                        <th style='text-align:right;padding:10px;'>Failure Rate</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for rank, (node_id, contrib) in enumerate(ranked_contributors, 1):
                # Alternate row colors
                bg_color = '#ffffff' if rank % 2 == 1 else '#f8f9fa'
                
                html += f"""
                <tr style='background:{bg_color};border-bottom:1px solid #dee2e6;'>
                    <td style='text-align:center;padding:10px;font-weight:bold;color:#495057;'>{rank}</td>
                    <td style='padding:10px;font-weight:bold;color:#212529;'>{node_id}</td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        ${contrib['es_direct_dollar']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;color:#d9534f;'>
                        ${contrib['es_indirect_dollar']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        ${contrib['es_total_dollar']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        {contrib['es_total_pct']:.2f}%
                    </td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        {contrib['failure_rate_in_tail']:.1f}%
                    </td>
                </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
            
            # Add summary stats
            total_es_dollar = sum(c[1]['es_total_dollar'] for c in ranked_contributors)
            total_direct = sum(c[1]['es_direct_dollar'] for c in ranked_contributors)
            total_indirect = sum(c[1]['es_indirect_dollar'] for c in ranked_contributors)
            
            html += f"""
            <div style='margin-top:12px;padding:10px;background:#fff3cd;border-radius:4px;
                        font-size:12px;'>
                <b>Top 5 Combined:</b> 
                Direct = <b>${total_direct:,.0f}</b>, 
                Indirect = <b>${total_indirect:,.0f}</b>, 
                <b>Total = ${total_es_dollar:,.0f}</b>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <b>ES ({self.es_percentile*100:.0f}%):</b> ${es_value:,.0f}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <b>Tail scenarios:</b> {n_tail} / {n_total}
            </div>
            """
        
        html += "</div>"
        
        # Display in the output widget
        self.es_contributors_output.clear_output()
        with self.es_contributors_output:
            display(HTML(html))
    
    def _update_failure_patterns_panel(self):
        """Update the failure patterns panel showing top failure modes in ES tail."""
        if not self.failure_patterns_output:
            return
        
        # Get tail scenarios
        tail_mask = self.results.total_losses >= self.es_threshold
        tail_indices = np.where(tail_mask)[0]
        n_tail = len(tail_indices)
        n_total = len(self.results.total_losses)
        es_value = np.mean(self.results.total_losses[tail_mask])
        
        # Extract failure patterns
        patterns = {}  # pattern -> {'count': int, 'total_loss': float, 'scenarios': [indices]}
        
        for idx in tail_indices:
            sim_result = self.results.runs[idx]
            total_loss = self.results.total_losses[idx]
            
            # Get set of failed nodes
            failed_nodes = frozenset([
                node_id for node_id, node_data in sim_result.items()
                if node_data.get('failed', False)
            ])
            
            # Use frozenset as pattern key
            if failed_nodes not in patterns:
                patterns[failed_nodes] = {
                    'count': 0,
                    'total_loss': 0.0,
                    'scenarios': [],
                    'avg_loss': 0.0
                }
            
            patterns[failed_nodes]['count'] += 1
            patterns[failed_nodes]['total_loss'] += total_loss
            patterns[failed_nodes]['scenarios'].append(idx)
        
        # Calculate average loss and frequency for each pattern
        for pattern_data in patterns.values():
            pattern_data['avg_loss'] = pattern_data['total_loss'] / pattern_data['count']
            pattern_data['frequency_pct'] = (pattern_data['count'] / n_tail) * 100
            pattern_data['es_contrib'] = pattern_data['total_loss'] / n_tail
        
        # Rank by ES contribution (frequency × avg loss)
        ranked_patterns = sorted(
            patterns.items(),
            key=lambda x: x[1]['es_contrib'],
            reverse=True
        )[:10]  # Top 10 patterns
        
        # Build HTML table
        html = f"""
        <div style='background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;
                    padding:20px;margin:16px 0;max-width:1200px;'>
            <h3 style='margin:0 0 16px 0;color:#333;border-bottom:2px solid #dee2e6;
                       padding-bottom:8px;'>
                Top 10 Failure Patterns in ES Tail
            </h3>
            
            <div style='background:#fff3cd;padding:10px;border-radius:4px;margin-bottom:12px;
                        font-size:12px;color:#555;'>
                <b>What this shows:</b> Common combinations of node failures that lead to worst-case losses.
                Each row shows which nodes failed together (not causation order).<br>
                <b>Click "View" button</b> to see an example of this pattern in the DAG above.<br>
                <b>ES Contribution</b> = (pattern frequency) × (avg loss) = total impact of this failure mode
            </div>
        """
        
        if not ranked_patterns:
            html += "<p style='color:#888;font-style:italic;'>No failure patterns detected.</p>"
        else:
            # Create table with buttons
            html += """
            <table style='width:100%;border-collapse:collapse;font-size:13px;'>
                <thead>
                    <tr style='background:#343a40;color:white;'>
                        <th style='text-align:center;padding:10px;border-right:1px solid #555;width:50px;'>Rank</th>
                        <th style='text-align:left;padding:10px;border-right:1px solid #555;min-width:300px;'>Failure Pattern<br><span style='font-size:11px;font-weight:normal;'>(Nodes that failed together)</span></th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Frequency</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Avg Loss</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'><b>ES Contrib ($)</b></th>
                        <th style='text-align:center;padding:10px;width:80px;'>Action</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            # Create buttons list
            pattern_buttons = []
            
            for rank, (failed_nodes, pattern_data) in enumerate(ranked_patterns, 1):
                bg_color = '#ffffff' if rank % 2 == 1 else '#f8f9fa'
                
                # Pick representative scenario (median loss)
                scenarios = pattern_data['scenarios']
                scenario_losses = [(idx, self.results.total_losses[idx]) for idx in scenarios]
                scenario_losses.sort(key=lambda x: x[1])
                representative_idx = scenario_losses[len(scenario_losses)//2][0]
                
                # Format node list - USE COMMAS not arrows
                if len(failed_nodes) == 0:
                    nodes_display = "<i style='color:#888;'>No failures</i>"
                else:
                    # Sort nodes for consistent display
                    sorted_nodes = sorted(list(failed_nodes))
                    
                    # Color code by node type
                    node_spans = []
                    for node_id in sorted_nodes:
                        node = self.risk_dag.nodes.get(node_id)
                        if node and node.is_latent:
                            node_spans.append(f"<span style='color:#d9534f;font-weight:bold;'>{node_id}</span>")
                        else:
                            node_spans.append(f"<span style='color:#0275d8;'>{node_id}</span>")
                    
                    # Join with COMMAS (not arrows - no causation implied)
                    if len(node_spans) <= 6:
                        nodes_display = ", ".join(node_spans)
                    else:
                        # Show first 5 + "and N more"
                        visible = ", ".join(node_spans[:5])
                        remaining = len(node_spans) - 5
                        nodes_display = f"{visible}, <i>+{remaining} more</i>"
                
                # Create button for this pattern
                button = widgets.Button(
                    description='View',
                    button_style='info',
                    tooltip=f'View pattern #{rank} in DAG',
                    layout=widgets.Layout(width='60px', height='28px')
                )
                
                # Closure to capture representative_idx
                def make_callback(sim_idx):
                    def callback(b):
                        self.show_simulation(sim_idx)
                    return callback
                
                button.on_click(make_callback(representative_idx))
                pattern_buttons.append(button)
                
                html += f"""
                <tr id='pattern-row-{rank}' style='background:{bg_color};border-bottom:1px solid #dee2e6;'>
                    <td style='text-align:center;padding:10px;font-weight:bold;color:#495057;'>{rank}</td>
                    <td style='padding:10px;line-height:1.6;'>{nodes_display}</td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        {pattern_data['count']} ({pattern_data['frequency_pct']:.1f}%)
                    </td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        ${pattern_data['avg_loss']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        ${pattern_data['es_contrib']:,.0f}
                    </td>
                    <td style='text-align:center;padding:10px;' id='button-cell-{rank}'>
                        <!-- Button widget inserted here -->
                    </td>
                </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
            
            # Add legend and summary
            html += f"""
            <div style='margin-top:12px;padding:10px;background:#e7f3ff;border-radius:4px;
                        font-size:11px;color:#555;'>
                <b>Legend:</b> 
                <span style='color:#d9534f;font-weight:bold;'>Red = Latent risk</span>, 
                <span style='color:#0275d8;'>Blue = Task node</span>
                &nbsp;&nbsp;|&nbsp;&nbsp;
                Patterns show which nodes failed together (commas = no causation order implied)
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <b>Top 10 patterns account for:</b> {sum(p[1]['frequency_pct'] for p in ranked_patterns):.1f}% of tail scenarios
                &nbsp;&nbsp;|&nbsp;&nbsp;
                ES: ${es_value:,.0f} | Tail: {n_tail}/{n_total}
            </div>
            """
            
            html += "</div>"
            
            # Display HTML and buttons
            self.failure_patterns_output.clear_output()
            with self.failure_patterns_output:
                display(HTML(html))
                
                # Display buttons in a grid
                if pattern_buttons:
                    button_label = widgets.HTML(
                        "<div style='font-size:11px;color:#666;margin:8px 0 4px 0;'>"
                        "<b>Click to view pattern in DAG:</b></div>"
                    )
                    button_grid = widgets.GridBox(
                        pattern_buttons,
                        layout=widgets.Layout(
                            width='100%',
                            grid_template_columns='repeat(10, 70px)',
                            grid_gap='8px'
                        )
                    )
                    display(button_label)
                    display(button_grid)
    
    def _update_root_cause_partition_panel(self):
        """Update the root cause partition panel - Minimal Cut Set decomposition."""
        if not self.root_cause_partition_output:
            return
        
        # Get tail scenarios
        tail_mask = self.results.total_losses >= self.es_threshold
        tail_indices = np.where(tail_mask)[0]
        n_tail = len(tail_indices)
        n_total = len(self.results.total_losses)
        es_value = np.mean(self.results.total_losses[tail_mask])
        
        # Partition scenarios by root cause (Minimal Cut Set)
        # Priority order: most upstream to most downstream
        partitions = {}
        
        # Get topological order (upstream to downstream)
        topo_order = list(nx.topological_sort(self.risk_dag.graph))
        
        for idx in tail_indices:
            sim_result = self.results.runs[idx]
            total_loss = self.results.total_losses[idx]
            
            # Find root cause: first node in topo order that failed independently
            root_cause = None
            for node_id in topo_order:
                if node_id in sim_result and sim_result[node_id].get('failed', False):
                    failure_cause = sim_result[node_id].get('failure_cause')
                    if failure_cause in ['independent', 'latent_trigger']:
                        root_cause = node_id
                        break
            
            # If no independent failure found (shouldn't happen), use 'unknown'
            if root_cause is None:
                root_cause = 'unknown'
            
            # Add to partition
            if root_cause not in partitions:
                partitions[root_cause] = {
                    'scenarios': [],
                    'total_loss': 0.0
                }
            
            partitions[root_cause]['scenarios'].append(idx)
            partitions[root_cause]['total_loss'] += total_loss
        
        # Calculate metrics for each partition
        for p_name, p_data in partitions.items():
            p_data['count'] = len(p_data['scenarios'])
            p_data['frequency_pct'] = (p_data['count'] / n_tail) * 100
            p_data['avg_loss'] = p_data['total_loss'] / p_data['count']
            p_data['es_contrib'] = p_data['total_loss'] / n_tail
            p_data['es_pct'] = (p_data['total_loss'] / (es_value * n_tail)) * 100
        
        # Sort by ES contribution
        ranked_partitions = sorted(
            partitions.items(),
            key=lambda x: x[1]['es_contrib'],
            reverse=True
        )
        
        # Build HTML
        self.root_cause_partition_output.clear_output()
        with self.root_cause_partition_output:
            header_html = f"""
            <div style='background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;
                        padding:20px;margin:16px 0;max-width:1100px;'>
                <h3 style='margin:0 0 16px 0;color:#333;border-bottom:2px solid #dee2e6;
                           padding-bottom:8px;'>
                    Root Cause Partition Analysis (Minimal Cut Set Decomposition)
                </h3>
                
                <div style='background:#e7f3ff;padding:10px;border-radius:4px;margin-bottom:12px;
                            font-size:12px;color:#555;'>
                    <b>What this shows:</b> ES tail scenarios partitioned by <i>root cause</i> - the initiating 
                    failure that triggered cascades. Each scenario belongs to exactly one partition based on the 
                    most upstream node that failed independently.<br>
                    <b>Minimal Cut Set (MCS):</b> The smallest set of component failures causing system failure.
                    This decomposition is MECE (Mutually Exclusive, Collectively Exhaustive) - every tail scenario 
                    is counted exactly once.<br>
                    <b>ES Contribution:</b> Average loss attributable to this root cause = (total loss in partition) / n_tail
                </div>
            """
            display(HTML(header_html))
            
            if not ranked_partitions:
                display(HTML("<p style='color:#888;font-style:italic;'>No partitions detected.</p></div>"))
                return
            
            # Table
            table_html = f"""
            <table style='width:100%;border-collapse:collapse;font-size:13px;'>
                <thead>
                    <tr style='background:#343a40;color:white;'>
                        <th style='text-align:left;padding:10px;border-right:1px solid #555;min-width:150px;'>Root Cause<br><span style='font-size:11px;font-weight:normal;'>(Initiating failure)</span></th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Scenarios</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Frequency</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'>Avg Loss</th>
                        <th style='text-align:right;padding:10px;border-right:1px solid #555;'><b>ES Contrib ($)</b></th>
                        <th style='text-align:right;padding:10px;'><b>ES %</b></th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for root_cause, p_data in ranked_partitions:
                bg_color = '#ffffff' if (ranked_partitions.index((root_cause, p_data)) % 2 == 0) else '#f8f9fa'
                
                # Check if this is a latent risk
                node = self.risk_dag.nodes.get(root_cause)
                if node and node.is_latent:
                    root_cause_display = f"<span style='color:#d9534f;font-weight:bold;'>{root_cause}</span>"
                else:
                    root_cause_display = f"<span style='color:#0275d8;'>{root_cause}</span>"
                
                table_html += f"""
                <tr style='background:{bg_color};border-bottom:1px solid #dee2e6;'>
                    <td style='padding:10px;font-weight:bold;'>{root_cause_display}</td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        {p_data['count']}
                    </td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        {p_data['frequency_pct']:.1f}%
                    </td>
                    <td style='text-align:right;padding:10px;color:#495057;'>
                        ${p_data['avg_loss']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        ${p_data['es_contrib']:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        {p_data['es_pct']:.1f}%
                    </td>
                </tr>
                """
            
            # Add TOTAL row
            total_scenarios = sum(p[1]['count'] for p in ranked_partitions)
            total_es_contrib = sum(p[1]['es_contrib'] for p in ranked_partitions)
            total_es_pct = sum(p[1]['es_pct'] for p in ranked_partitions)
            
            table_html += f"""
                <tr style='background:#fffacd;border-top:2px solid #333;'>
                    <td style='padding:10px;font-weight:bold;'>TOTAL</td>
                    <td style='text-align:right;padding:10px;font-weight:bold;'>{total_scenarios}</td>
                    <td style='text-align:right;padding:10px;font-weight:bold;'>100.0%</td>
                    <td style='text-align:right;padding:10px;'>—</td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        ${total_es_contrib:,.0f}
                    </td>
                    <td style='text-align:right;padding:10px;font-weight:bold;color:#b22222;'>
                        {total_es_pct:.1f}%
                    </td>
                </tr>
                </tbody>
            </table>
            """
            
            display(HTML(table_html))
            
            # Verification checks
            verification_passed = (total_scenarios == n_tail and 
                                 abs(total_es_contrib - es_value) < 0.01)
            
            check_icon = "✓" if verification_passed else "✗"
            check_color = "#28a745" if verification_passed else "#dc3545"
            
            footer_html = f"""
            <div style='margin-top:12px;padding:10px;background:#f8f9fa;border-radius:4px;
                        font-size:11px;color:#555;'>
                <b>Verification:</b> 
                <span style='color:{check_color};font-weight:bold;'>{check_icon}</span>
                Partitions are MECE (Mutually Exclusive, Collectively Exhaustive)
                <br>
                Total scenarios: {total_scenarios} / {n_tail} (should be equal)
                <br>
                Total ES: ${total_es_contrib:,.0f} / ${es_value:,.0f} (should be equal)
                <br><br>
                <b>Legend:</b> 
                <span style='color:#d9534f;font-weight:bold;'>Red = Latent risk</span>, 
                <span style='color:#0275d8;'>Blue = Task node</span>
                <br>
                <b>Interpretation:</b> Each row shows scenarios where that node was the <i>initiating failure</i> 
                (root cause). ES Contribution = total impact of that root cause across all tail scenarios.
            </div>
        </div>
            """
            display(HTML(footer_html))
    
    def show_simulation(self, sim_index: int):
        """
        Show DAG snapshot for a specific simulation.
        
        Args:
            sim_index: Index of simulation to visualize
        """
        if not CYTOSCAPE_AVAILABLE:
            print("Cytoscape not available. Install: pip install ipycytoscape")
            return
        
        if sim_index < 0 or sim_index >= len(self.results.runs):
            print(f"Invalid simulation index: {sim_index}")
            return
        
        # Get simulation result
        sim_result = self.results.runs[sim_index]
        total_loss = self.results.total_losses[sim_index]
        
        # Check if in ES tail
        in_es_tail = total_loss >= self.es_threshold
        
        # --- Correct ES contribution math ---
        # ES = E[L | L >= VaR] = (1/n_tail) * sum(tail losses)
        # Dollar contribution of this sim to ES = L_i / n_tail
        # % contribution = L_i / sum(tail losses)
        tail_mask = self.results.total_losses >= self.es_threshold
        tail_losses = self.results.total_losses[tail_mask]
        n_tail = len(tail_losses)
        n_total = len(self.results.total_losses)
        es_value = np.mean(tail_losses)           # ES = mean of tail
        sum_tail_losses = np.sum(tail_losses)     # denominator for %
        
        # This sim's probability-weighted dollar contribution to ES
        # = L_i * P(this scenario) / P(tail) = L_i / n_tail  (uniform weights)
        es_dollar_contrib = total_loss / n_tail if in_es_tail else 0.0
        # % of total ES value
        es_pct_contrib = (total_loss / sum_tail_losses * 100) if (in_es_tail and sum_tail_losses > 0) else 0.0
        
        # Percentile rank of this simulation
        percentile_rank = np.sum(self.results.total_losses <= total_loss) / n_total * 100
        
        # Per-node losses in this simulation
        node_losses = []
        for node_id, node_result in sim_result.items():
            if node_result.get('failed') and node_result.get('loss', 0) > 0:
                node_losses.append((node_id, node_result['loss']))
        node_losses.sort(key=lambda x: x[1], reverse=True)
        
        # Create DAG visualization
        cyto = self._create_dag_snapshot(sim_result, sim_index, total_loss, in_es_tail)
        
        # --- Build header HTML ---
        tail_badge = (
            "<span style='background:#b22222;color:white;padding:2px 8px;"
            "border-radius:3px;font-size:12px;margin-left:8px;'>IN ES TAIL</span>"
        ) if in_es_tail else (
            "<span style='background:#2ca02c;color:white;padding:2px 8px;"
            "border-radius:3px;font-size:12px;margin-left:8px;'>BELOW ES</span>"
        )
        
        es_contrib_text = ""
        if in_es_tail:
            es_contrib_text = (
                f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"<span style='color:#b22222;font-size:13px;'>"
                f"ES Contribution: <b>${es_dollar_contrib:,.0f}</b> "
                f"(<b>{es_pct_contrib:.2f}%</b> of ES)"
                f"</span>"
            )
        
        header_html = (
            f"<div style='padding:8px 0;border-bottom:1px solid #eee;margin-bottom:6px;'>"
            f"<span style='font-size:15px;font-weight:bold;color:#333;'>"
            f"Simulation #{sim_index}</span>{tail_badge}"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='font-size:14px;'>Total Loss: <b>${total_loss:,.0f}</b></span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='font-size:13px;color:#555;'>{percentile_rank:.1f}th percentile</span>"
            f"{es_contrib_text}"
            f"</div>"
        )
        
        # --- Build stats panel HTML ---
        stats_html = f"""
        <div style='background:#fafafa;border:1px solid #ddd;border-radius:6px;
                    padding:14px;min-width:280px;max-width:360px;font-size:13px;
                    margin-left:12px;'>
            <h4 style='margin:0 0 10px 0;color:#333;'>Sim #{sim_index} · {percentile_rank:.1f}th %ile</h4>
            
            <div style='margin-bottom:10px;padding:8px;background:#f0f4ff;
                        border-radius:4px;border-left:3px solid #4a90d9;'>
                <b>Total Loss:</b> &nbsp;${total_loss:,.0f}<br>
                <b>ES ({self.es_percentile*100:.0f}%):</b> &nbsp;${es_value:,.0f}<br>
                <b>ES Threshold (VaR):</b> &nbsp;${self.es_threshold:,.0f}<br>
                <b>Tail scenarios:</b> &nbsp;{n_tail} / {n_total}
            </div>
        """
        
        if in_es_tail:
            pct_above_threshold = (total_loss - self.es_threshold) / self.es_threshold * 100
            stats_html += f"""
            <div style='margin-bottom:10px;padding:8px;background:#fde8e8;
                        border-radius:4px;border-left:3px solid #b22222;'>
                <b style='color:#b22222;'>In ES Tail</b><br>
                <b>ES contribution ($):</b> &nbsp;<b>${es_dollar_contrib:,.0f}</b><br>
                <span style='font-size:11px;color:#666;'>= Loss / n_tail scenarios</span><br>
                <b>ES contribution (%):</b> &nbsp;<b>{es_pct_contrib:.2f}%</b><br>
                <span style='font-size:11px;color:#666;'>= Loss / Σ tail losses</span><br>
                <b>Above VaR by:</b> &nbsp;${total_loss - self.es_threshold:,.0f} ({pct_above_threshold:.1f}%)
            </div>
            """
        else:
            pct_below = (self.es_threshold - total_loss) / self.es_threshold * 100
            stats_html += f"""
            <div style='margin-bottom:10px;padding:8px;background:#e8f5e9;
                        border-radius:4px;border-left:3px solid #2ca02c;'>
                <b style='color:#2ca02c;'>Below ES Threshold</b><br>
                <b>ES contribution:</b> &nbsp;$0 (0.00%)<br>
                <b>Below VaR by:</b> &nbsp;${self.es_threshold - total_loss:,.0f} ({pct_below:.1f}%)
            </div>
            """
        
        if node_losses:
            stats_html += "<b>Node Losses This Simulation:</b>"
            stats_html += "<table style='width:100%;margin-top:4px;border-collapse:collapse;'>"
            stats_html += ("<tr style='background:#eee;'>"
                          "<th style='text-align:left;padding:3px 6px;'>Node</th>"
                          "<th style='text-align:right;padding:3px 6px;'>Loss</th>"
                          "<th style='text-align:right;padding:3px 6px;'>% of Total</th>"
                          "</tr>")
            for node_id, loss in node_losses:
                pct = loss / total_loss * 100 if total_loss > 0 else 0
                stats_html += (
                    f"<tr style='border-bottom:1px solid #eee;'>"
                    f"<td style='padding:3px 6px;'><b>{node_id}</b></td>"
                    f"<td style='text-align:right;padding:3px 6px;'>${loss:,.0f}</td>"
                    f"<td style='text-align:right;padding:3px 6px;'>{pct:.1f}%</td>"
                    f"</tr>"
                )
            stats_html += "</table>"
        else:
            stats_html += "<i style='color:#888;'>No node failures this simulation.</i>"
        
        stats_html += "</div>"
        
        # Display
        if self.dag_output:
            self.dag_output.clear_output()
            with self.dag_output:
                display(HTML(header_html))
                display(cyto)
                self.current_cyto_widget = cyto
        else:
            display(HTML(header_html))
            display(cyto)
            self.current_cyto_widget = cyto
        
        # Update stats panel
        if self.stats_output:
            self.stats_output.clear_output()
            with self.stats_output:
                display(HTML(stats_html))
    
    def save_current_layout(self):
        """
        Save the current layout from the displayed widget.
        Call this after dragging nodes to desired positions.
        """
        if hasattr(self, 'current_cyto_widget'):
            count = self._save_layout_from_widget(self.current_cyto_widget)
            if count > 0:
                print(f"Saved layout with {count} node positions")
                return True
            else:
                print("No positions saved - try dragging nodes first")
                return False
        else:
            print("No widget displayed yet")
            return False
    
    def clear_saved_layout(self):
        """Clear the saved layout to use dagre again."""
        self.current_layout = {}
        print("Cleared saved layout - will use dagre for next visualization")
    
    def export_to_html(self, filename: str = "risk_dashboard.html", mode: str = "voila"):
        """
        Export the dashboard to HTML.
        
        Args:
            filename: Output HTML filename
            mode: Export mode:
                - 'voila': Instructions for Voilà (recommended)
                - 'plotly': Plotly-only static HTML (works, but no DAG interaction)
                - 'widget': Try ipywidgets embed (limited, may not work fully)
        
        Returns:
            Path to the saved file or instructions
        """
        if mode == 'voila':
            print("="*70)
            print("RECOMMENDED: Use Voilà for Full Interactivity")
            print("="*70)
            print()
            print("Voilà turns your notebook into a web app with full interactivity.")
            print()
            print("Steps:")
            print("1. Install Voilà:")
            print("   pip install voila")
            print()
            print("2. Save your notebook (File → Save)")
            print()
            print("3. Run Voilà:")
            print(f"   voila your_notebook.ipynb")
            print()
            print("4. Opens at: http://localhost:8866")
            print()
            print("5. To share publicly:")
            print("   - Deploy to Heroku/Binder (free)")
            print("   - Or use ngrok for temporary sharing")
            print()
            print("All features work: buttons, slider, DAG updates! ✅")
            print("="*70)
            return None
            
        elif mode == 'plotly':
            # Export just the exceedance curve as interactive HTML
            try:
                # Create a standalone Plotly figure
                fig = self._create_interactive_exceedance_curve()
                
                # Add ES summary as annotations
                es_mean = np.mean(self.results.total_losses[
                    self.results.total_losses >= self.es_threshold
                ])
                
                annotation_text = (
                    f"<b>Expected Shortfall (ES) at {self.es_percentile*100:.0f}%</b><br>"
                    f"ES Threshold: ${self.es_threshold:,.0f}<br>"
                    f"ES Mean: ${es_mean:,.0f}<br>"
                    f"Scenarios in tail: {np.sum(self.results.total_losses >= self.es_threshold)}"
                )
                
                fig.add_annotation(
                    text=annotation_text,
                    xref="paper", yref="paper",
                    x=0.02, y=0.98,
                    xanchor='left', yanchor='top',
                    showarrow=False,
                    bgcolor="white",
                    bordercolor="black",
                    borderwidth=1,
                    font=dict(size=12)
                )
                
                # Write to HTML
                fig.write_html(
                    filename,
                    include_plotlyjs='cdn',
                    config={'displayModeBar': True, 'displaylogo': False}
                )
                
                import os
                abs_path = os.path.abspath(filename)
                print(f"Exceedance curve exported to: {abs_path}")
                print(f"  (Interactive Plotly chart - DAG snapshots not included)")
                print()
                print(f"  For full dashboard, use mode='voila' instead.")
                
                return abs_path
                
            except Exception as e:
                print(f"Export failed: {e}")
                return None
                
        elif mode == 'widget':
            # Try ipywidgets embed (limited functionality)
            try:
                from ipywidgets import embed
                import os
                
                if not hasattr(self, 'main_widget'):
                    self.main_widget = self.create_dashboard()
                
                embed.embed_minimal_html(filename, views=[self.main_widget], title='Risk Dashboard')
                
                abs_path = os.path.abspath(filename)
                print(f"Dashboard exported to: {abs_path}")
                print()
                print("WARNING: ipywidgets export has limitations:")
                print("  - Cytoscape may not render properly")
                print("  - Button interactions may not work")
                print("  - Use mode='voila' for full interactivity")
                
                return abs_path
                
            except Exception as e:
                print(f"Export failed: {e}")
                return None
        else:
            print(f"❌ Unknown mode: {mode}")
            print("   Valid modes: 'voila', 'plotly', 'widget'")
            return None
    
    def _create_dag_snapshot(self, sim_result: Dict, sim_index: int, 
                            total_loss: float, in_es_tail: bool):
        """Create Cytoscape DAG showing this simulation's failures."""
        
        # Build graph
        self.risk_dag.build_graph()
        
        # Separate tasks and latent risks
        task_nodes = [nid for nid, n in self.risk_dag.nodes.items() if not n.is_latent]
        latent_nodes = [nid for nid, n in self.risk_dag.nodes.items() if n.is_latent]
        
        # Create nodes
        nodes = []
        
        # Add task nodes
        for node_id in task_nodes:
            node = self.risk_dag.nodes[node_id]
            node_result = sim_result.get(node_id, {})
            
            failed = node_result.get('failed', False)
            loss = node_result.get('loss', 0)
            
            # Get operator type from metadata if available
            operator = ''
            if hasattr(node, 'metadata') and node.metadata:
                raw = node.metadata.get('operator_type', '')
                operator = raw.replace('Operator', '').replace('Sensor', '⏳') if raw else ''
            
            # Label
            if failed:
                label = f"{node_id}\n❌ ${loss:,.0f}"
            else:
                label = f"{node_id}\n✓"
            if operator:
                label += f"\n[{operator}]"
            
            # Tooltip
            tooltip = f"{node_id}\nStatus: {'FAILED' if failed else 'OK'}\nLoss: ${loss:,.0f}"
            if operator:
                tooltip += f"\nOperator: {node.metadata.get('operator_type', '')}"
            
            # Style based on failure
            node_class = 'failed_task' if failed else 'ok_task'
            
            nodes.append(Node(
                data={'id': node_id, 'label': label, 'tooltip': tooltip},
                classes=node_class
            ))
        
        # Add latent nodes
        for node_id in latent_nodes:
            node = self.risk_dag.nodes[node_id]
            node_result = sim_result.get(node_id, {})
            
            triggered = node_result.get('failed', False)
            loss = node_result.get('loss', 0)
            
            # Get operator type from metadata if available
            operator = ''
            if hasattr(node, 'metadata') and node.metadata:
                raw = node.metadata.get('operator_type', '')
                operator = raw.replace('Operator', '').replace('Sensor', '⏳') if raw else ''
            
            # Label
            if triggered:
                label = f"{node_id}\n⚡ ${loss:,.0f}"
            else:
                label = f"{node_id}\n○"
            if operator:
                label += f"\n[{operator}]"
            
            # Tooltip
            tooltip = f"{node_id}\nStatus: {'TRIGGERED' if triggered else 'OK'}\nLoss: ${loss:,.0f}"
            if operator:
                tooltip += f"\nOperator: {node.metadata.get('operator_type', '')}"
            
            # Style
            node_class = 'triggered_latent' if triggered else 'ok_latent'
            
            nodes.append(Node(
                data={'id': node_id, 'label': label, 'tooltip': tooltip},
                classes=node_class
            ))
        
        # Create edges - color red if failure propagated through them
        edges = []
        failed_nodes = {nid for nid, res in sim_result.items() if res.get('failed', False)}
        
        for source_id, target_id in self.risk_dag.graph.edges():
            # Check if this edge propagated failure
            source_failed = source_id in failed_nodes
            target_failed = target_id in failed_nodes
            
            # Edge is red if source failed and target failed
            # (indicating propagation through this edge)
            propagated = source_failed and target_failed
            
            source_node = self.risk_dag.nodes[source_id]
            
            # Determine edge class
            if source_node.is_latent:
                edge_class = 'propagated_latent_edge' if propagated else 'latent_edge'
            else:
                edge_class = 'propagated_task_edge' if propagated else 'task_edge'
            
            edges.append(Edge(
                data={'source': source_id, 'target': target_id},
                classes=edge_class
            ))
        
        # Create widget
        cyto = ipycytoscape.CytoscapeWidget()
        cyto.graph.add_nodes(nodes)
        cyto.graph.add_edges(edges)
        
        # Apply styles - USE SAME GOOD STYLES AS cytoscape_viz
        cyto.set_style([
            # OK task nodes (green border, good text)
            {
                'selector': 'node.ok_task',
                'style': {
                    'shape': 'round-rectangle',
                    'background-color': '#fff',
                    'border-width': 2,
                    'border-color': '#2ca02c',
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '20px',
                    'font-weight': 'bold',
                    'font-family': 'Arial, sans-serif',
                    'color': '#2ca02c',
                    'width': 200,
                    'height': 90,
                    'padding': 16,
                    'text-wrap': 'wrap',
                    'text-max-width': '180px'
                }
            },
            # Failed task nodes (RED)
            {
                'selector': 'node.failed_task',
                'style': {
                    'shape': 'round-rectangle',
                    'background-color': '#ffcccc',
                    'border-width': 3,
                    'border-color': '#d62728',
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '20px',
                    'font-weight': 'bold',
                    'font-family': 'Arial, sans-serif',
                    'color': '#d62728',
                    'width': 200,
                    'height': 90,
                    'padding': 16,
                    'text-wrap': 'wrap',
                    'text-max-width': '180px'
                }
            },
            # OK latent nodes
            {
                'selector': 'node.ok_latent',
                'style': {
                    'shape': 'round-rectangle',
                    'background-color': '#fff7e6',
                    'border-width': 2,
                    'border-color': '#ffa940',
                    'border-style': 'dashed',
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '20px',
                    'font-weight': 'bold',
                    'font-family': 'Arial, sans-serif',
                    'color': '#666',
                    'width': 200,
                    'height': 90,
                    'padding': 16,
                    'text-wrap': 'wrap',
                    'text-max-width': '180px'
                }
            },
            # Triggered latent nodes (RED/ORANGE)
            {
                'selector': 'node.triggered_latent',
                'style': {
                    'shape': 'round-rectangle',
                    'background-color': '#ffe6cc',
                    'border-width': 3,
                    'border-color': '#ff7f0e',
                    'border-style': 'dashed',
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '20px',
                    'font-weight': 'bold',
                    'font-family': 'Arial, sans-serif',
                    'color': '#ff7f0e',
                    'width': 200,
                    'height': 90,
                    'padding': 16,
                    'text-wrap': 'wrap',
                    'text-max-width': '180px'
                }
            },
            # Normal edges
            {
                'selector': 'edge.task_edge',
                'style': {
                    'width': 2,
                    'line-color': '#ccc',
                    'target-arrow-color': '#ccc',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier'
                }
            },
            {
                'selector': 'edge.latent_edge',
                'style': {
                    'width': 2,
                    'line-color': '#ccc',
                    'target-arrow-color': '#ccc',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'line-style': 'dashed'
                }
            },
            # Propagated edges (RED/THICK)
            {
                'selector': 'edge.propagated_task_edge',
                'style': {
                    'width': 4,
                    'line-color': '#d62728',
                    'target-arrow-color': '#d62728',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier'
                }
            },
            {
                'selector': 'edge.propagated_latent_edge',
                'style': {
                    'width': 4,
                    'line-color': '#ff7f0e',
                    'target-arrow-color': '#ff7f0e',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'line-style': 'dashed'
                }
            }
        ])
        
        # Configure and set layout - ALWAYS use dagre initially
        # Only use saved positions after user explicitly saves
        use_saved_layout = False
        
        if self.current_layout and len(self.current_layout) > 0:
            # Check if we have valid positions for this graph
            valid_count = 0
            for node in cyto.graph.nodes:
                node_id = node.data['id']
                if node_id in self.current_layout:
                    pos = self.current_layout[node_id]
                    if isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                        # Verify positions are reasonable (not 0,0 or negative)
                        if pos['x'] != 0 and pos['y'] != 0:
                            valid_count += 1
            
            # Use saved layout ONLY if we have positions for ALL nodes
            if valid_count == len(cyto.graph.nodes):
                # Apply saved positions
                for node in cyto.graph.nodes:
                    node_id = node.data['id']
                    if node_id in self.current_layout:
                        pos = self.current_layout[node_id]
                        if isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                            node.position = {'x': pos['x'], 'y': pos['y']}
                
                use_saved_layout = True
        
        # Set layout based on whether we have saved positions
        if use_saved_layout:
            layout_config = {
                'name': 'preset',
                'animate': False
            }
        else:
            # Use dagre - the default
            layout_config = {
                'name': 'dagre',
                'rankDir': 'LR',
                'nodeSep': 100,
                'rankSep': 150,
                'animate': False
            }
        
        cyto.set_layout(**layout_config)
        
        # THEN set tooltip and size
        cyto.set_tooltip_source('tooltip')
        cyto.layout.width = '100%'
        cyto.layout.height = '500px'  # Larger for better visibility
        
        return cyto
    
    def _save_layout_from_widget(self, cyto_widget):
        """Extract and save current layout from widget."""
        saved_count = 0
        try:
            if hasattr(cyto_widget, 'graph') and hasattr(cyto_widget.graph, 'nodes'):
                for node in cyto_widget.graph.nodes:
                    if hasattr(node, 'data') and 'id' in node.data:
                        node_id = node.data['id']
                        if hasattr(node, 'position') and node.position is not None:
                            pos = node.position
                            # Make sure position is a dict with x and y
                            if hasattr(pos, 'get'):
                                # It's already a dict-like object
                                self.current_layout[node_id] = {'x': pos.get('x', 0), 'y': pos.get('y', 0)}
                                saved_count += 1
                            elif hasattr(pos, '__iter__') and not isinstance(pos, str):
                                # It's iterable but not a string
                                pos_dict = dict(pos) if hasattr(pos, 'items') else {}
                                if 'x' in pos_dict and 'y' in pos_dict:
                                    self.current_layout[node_id] = {'x': pos_dict['x'], 'y': pos_dict['y']}
                                    saved_count += 1
            
            if saved_count == 0:
                print("Warning: No positions could be extracted. Try dragging nodes first.")
        except Exception as e:
            print(f"Error saving layout: {e}")
        
        return saved_count


def create_interactive_dashboard(risk_dag, results, es_percentile=0.95):
    """
    Create interactive risk dashboard with exceedance curve and DAG snapshots.
    
    Args:
        risk_dag: RiskDAG instance
        results: SimulationResults from run_monte_carlo
        es_percentile: Percentile for Expected Shortfall (default 0.95)
    
    Returns:
        InteractiveExceedanceDashboard instance with create_dashboard() method
    
    Example:
        >>> results = dag.run_monte_carlo(1000, seed=42)
        >>> dashboard = create_interactive_dashboard(dag, results)
        >>> widget = dashboard.create_dashboard()
        >>> display(widget)
        >>> 
        >>> # Show specific simulation
        >>> dashboard.show_simulation(50)  # Show simulation #50
        >>> dashboard.show_simulation(950)  # Show high-loss scenario
    """
    dashboard = InteractiveExceedanceDashboard(risk_dag, results, es_percentile)
    return dashboard
