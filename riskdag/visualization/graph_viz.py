"""
Grapg visualization for RiskDAGs.

Provides Airflow-like DAG visualization with draggable nodes.
"""
from typing import Optional, Dict, Any
import json

#requires ipycytoscape
try:
    import ipycytoscape
    from ipycytoscape import Node, Edge
    CYTOSCAPE_AVAILABLE = True
except ImportError:
    CYTOSCAPE_AVAILABLE = False
    Node = None
    Edge = None


class GraphVisualizer:
    """Visualization matching Airflow UI style functionality."""
    
    # Airflow-inspired styling
    TASK_STYLE = {
        'shape': 'round-rectangle',
        'background-color': '#fff',
        'border-width': 2,
        'border-color': '#ccc',
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '16px',
        'font-weight': 'bold',
        'font-family': 'Arial, sans-serif',
        'color': '#333',
        'width': 180,
        'height': 80,
        'padding': 14,
        'text-wrap': 'wrap',
        'text-max-width': '160px'
    }
    
    LATENT_STYLE = {
        'shape': 'round-rectangle',
        'background-color': '#fff7e6',
        'border-width': 2,
        'border-color': '#ffa940',
        'border-style': 'dashed',
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '16px',
        'font-weight': 'bold',
        'font-family': 'Arial, sans-serif',
        'color': '#333',
        'width': 180,
        'height': 80,
        'padding': 14,
        'text-wrap': 'wrap',
        'text-max-width': '160px'
    }
    
    TASK_EDGE_STYLE = {
        'width': 2,
        'line-color': '#000',
        'target-arrow-color': '#000',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'line-style': 'solid'
    }
    
    LATENT_EDGE_STYLE = {
        'width': 2,
        'line-color': '#000',
        'target-arrow-color': '#000',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'line-style': 'dashed'
    }
    
    @staticmethod
    def visualize(
        risk_dag,
        title: Optional[str] = None,
        layout: str = 'dagre',
        draggable: bool = True,
        show_probabilities: bool = True,
        width: str = '100%',
        height: str = '600px'
    ):
        """
        Create visualization with Airflow-like styling.
        
        Args:
            risk_dag: RiskDAG instance to visualize
            title: Title for the visualization
            layout: Layout algorithm ('dagre', 'breadthfirst', 'cose')
            draggable: Allow dragging nodes
            show_probabilities: Show failure probabilities in labels
            width: Widget width
            height: Widget height
        
        Returns:
            ipycytoscape widget
        """
        if not CYTOSCAPE_AVAILABLE:
            print("\n" + "="*70)
            print("⚠️  ipycytoscape not installed - using Plotly visualization instead")
            print("="*70)
            print()
            print("For Airflow-style draggable graphs, install ipycytoscape:")
            print("  pip install ipycytoscape")
            print("  # Then restart Jupyter kernel")
            print()
            print("Falling back to Plotly visualization...")
            print("="*70 + "\n")
            
            # Fall back to Plotly visualization
            from .graph_viz import visualize_risk_dag
            return visualize_risk_dag(
                risk_dag, 
                title=title,
                show_probabilities=show_probabilities,
                interactive=True
            )
        
        # Auto-build graph
        risk_dag.build_graph()
        
        # Separate tasks and latent risks
        task_nodes = [nid for nid, n in risk_dag.nodes.items() if not n.is_latent]
        latent_nodes = [nid for nid, n in risk_dag.nodes.items() if n.is_latent]
        
        # Build node data
        nodes = []
        
        # Add task nodes
        for node_id in task_nodes:
            node = risk_dag.nodes[node_id]
            
            # Get operator type from metadata if available
            operator = ''
            if hasattr(node, 'metadata') and node.metadata:
                raw = node.metadata.get('operator_type', '')
                # Shorten e.g. "PythonOperator" → "Python"
                operator = raw.replace('Operator', '').replace('Sensor', '⏳') if raw else ''
            
            # Build label
            if show_probabilities:
                label = f"{node_id} ({node.p_fail*100:.1f}%)"
            else:
                label = node_id
            if operator:
                label += f"\n[{operator}]"
            
            # Tooltip data - use actual newlines for HTML rendering
            tooltip = f"{node_id}\nType: Task\nFailure Prob: {node.p_fail*100:.2f}%"
            if operator:
                tooltip += f"\nOperator: {node.metadata.get('operator_type', '')}"
            if hasattr(node.loss_dist, 'mean'):
                try:
                    mean_loss = node.loss_dist.mean()
                    std_loss = node.loss_dist.std()
                    tooltip += f"\nLoss: ${mean_loss:,.0f} ± ${std_loss:,.0f}"
                except:
                    pass
            
            nodes.append(Node(
                data={
                    'id': node_id,
                    'label': label,
                    'type': 'task',
                    'tooltip': tooltip,
                    'prob': node.p_fail
                },
                classes='task'
            ))
        
        # Add latent risk nodes
        for node_id in latent_nodes:
            node = risk_dag.nodes[node_id]
            
            # Get operator type from metadata if available
            operator = ''
            if hasattr(node, 'metadata') and node.metadata:
                raw = node.metadata.get('operator_type', '')
                operator = raw.replace('Operator', '').replace('Sensor', '⏳') if raw else ''
            
            # Build label
            if show_probabilities:
                label = f"{node_id} ({node.p_fail*100:.1f}%)"
            else:
                label = node_id
            if operator:
                label += f"\n[{operator}]"
            
            # Tooltip data - use actual newlines for HTML rendering
            tooltip = f"{node_id}\nType: Latent Risk\nTrigger Prob: {node.p_fail*100:.2f}%"
            if operator:
                tooltip += f"\nOperator: {node.metadata.get('operator_type', '')}"
            if hasattr(node.loss_dist, 'mean'):
                try:
                    mean_loss = node.loss_dist.mean()
                    std_loss = node.loss_dist.std()
                    tooltip += f"\nLoss: ${mean_loss:,.0f} ± ${std_loss:,.0f}"
                except:
                    pass
            
            nodes.append(Node(
                data={
                    'id': node_id,
                    'label': label,
                    'type': 'latent',
                    'tooltip': tooltip,
                    'prob': node.p_fail
                },
                classes='latent'
            ))
        
        # Build edge data
        edges = []
        
        for source_id, target_id in risk_dag.graph.edges():
            source_node = risk_dag.nodes[source_id]
            target_node = risk_dag.nodes[target_id]
            
            # Determine edge type
            if source_node.is_latent:
                # Latent to anything - dashed
                edge_class = 'latent_edge'
            else:
                # Task to task - solid
                edge_class = 'task_edge'
            
            edges.append(Edge(
                data={
                    'source': source_id,
                    'target': target_id
                },
                classes=edge_class
            ))
        
        # Create cytoscape widget
        cyto = ipycytoscape.CytoscapeWidget()
        cyto.graph.add_nodes(nodes)
        cyto.graph.add_edges(edges)
        
        # Set style
        cyto.set_style([
            {
                'selector': 'node.task',
                'style': GraphVisualizer.TASK_STYLE
            },
            {
                'selector': 'node.latent',
                'style': GraphVisualizer.LATENT_STYLE
            },
            {
                'selector': 'edge.task_edge',
                'style': GraphVisualizer.TASK_EDGE_STYLE
            },
            {
                'selector': 'edge.latent_edge',
                'style': GraphVisualizer.LATENT_EDGE_STYLE
            },
            {
                'selector': ':selected',
                'style': {
                    'border-width': 3,
                    'border-color': '#1890ff'
                }
            }
        ])
        
        # Configure layout
        if layout == 'dagre':
            # Dagre layout (same as Airflow)
            layout_config = {
                'name': 'dagre',
                'rankDir': 'LR',  # Left to right
                'nodeSep': 50,
                'rankSep': 100,
                'animate': False
            }
        elif layout == 'breadthfirst':
            layout_config = {
                'name': 'breadthfirst',
                'directed': True,
                'spacingFactor': 1.5
            }
        else:
            layout_config = {'name': layout}
        
        cyto.set_layout(**layout_config)
        
        # Set widget properties
        # Enable tooltips on hover
        cyto.set_tooltip_source('tooltip')
        
        # Enable panning and zooming
        if hasattr(cyto, 'panning_enabled'):
            cyto.panning_enabled = True
        if hasattr(cyto, 'zooming_enabled'):
            cyto.zooming_enabled = True
        if hasattr(cyto, 'user_zooming_enabled'):
            cyto.user_zooming_enabled = True
        if hasattr(cyto, 'user_panning_enabled'):
            cyto.user_panning_enabled = True
        
        # Size
        if isinstance(width, int):
            width = f"{width}px"
        if isinstance(height, int):
            height = f"{height}px"
        
        cyto.layout.width = width
        cyto.layout.height = height
        
        return cyto
    
    @staticmethod
    def export_to_html(
        risk_dag,
        filename: str = 'risk_dag.html',
        title: Optional[str] = None,
        layout: str = 'dagre',
        show_probabilities: bool = True,
        width: str = '100%',
        height: str = '800px'
    ):
        """
        Export visualization to standalone HTML file.
        
        Creates a self-contained HTML file with cytoscape.js (no Python/Jupyter needed).
        The result is interactive, draggable, and works in any browser.
        
        Args:
            risk_dag: RiskDAG instance to visualize
            filename: Output HTML filename
            title: Title for the visualization
            layout: Layout algorithm ('dagre', 'breadthfirst', 'cose', 'circle')
            show_probabilities: Show failure probabilities in labels
            width: Container width (CSS value like '100%' or '1200px')
            height: Container height (CSS value like '800px')
        
        Returns:
            Path to the saved HTML file
        
        Example:
            >>> from riskdag.visualization import GraphVisualizer
            >>> CytoscapeVisualizer.export_to_html(dag, 'my_dag.html')
            >>> # Opens my_dag.html in browser - fully interactive!
        """
        import os
        
        # Auto-build graph
        risk_dag.build_graph()
        
        # Build elements with proper styling
        elements = []
        
        # Helper function for smart percentage formatting
        def format_percentage(value):
            """Format percentage intelligently - remove trailing zeros but keep precision when needed."""
            # Format to 4 decimal places, then remove trailing zeros
            formatted = f"{value * 100:.4f}".rstrip('0').rstrip('.')
            return f"{formatted}%"
        
        # Add nodes (tasks and latent risks)
        for node_id, node in risk_dag.nodes.items():
            # Build label with smart percentage format
            if show_probabilities:
                label = f"{node_id} ({format_percentage(node.p_fail)})"  # e.g., "aws (1%)" or "db (0.0841%)"
            else:
                label = node_id
            
            # Build tooltip with HTML line breaks
            if node.is_latent:
                node_type = "Latent Risk"
            else:
                node_type = "Task"
            
            tooltip = f"{node_id}<br>Type: {node_type}<br>Failure Prob: {format_percentage(node.p_fail)}"
            
            if hasattr(node.loss_dist, 'mean'):
                try:
                    mean_loss = node.loss_dist.mean()
                    tooltip += f"<br>Expected Loss: ${mean_loss:,.0f}"
                except:
                    pass
            
            elements.append({
                'data': {
                    'id': node_id,
                    'label': label,
                    'is_latent': node.is_latent,
                    'tooltip': tooltip
                },
                'classes': 'latent' if node.is_latent else 'task'
            })
        
        # Add edges with proper operator type
        for source, target in risk_dag.graph.edges():
            edge_data = risk_dag.graph[source][target]
            operator = edge_data.get('operator', '>>')
            
            # Determine edge class based on source type
            source_node = risk_dag.nodes[source]
            if source_node.is_latent:
                edge_class = 'latent_edge'  # Dashed
            else:
                edge_class = 'task_edge'    # Solid
            
            elements.append({
                'data': {
                    'source': source,
                    'target': target,
                    'operator': operator
                },
                'classes': edge_class
            })
        
        # Generate HTML
        html_title = title or f"RiskDAG: {risk_dag.dag_id}"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html_title}</title>
    
    <!-- Cytoscape.js from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
    
    <!-- Dagre layout from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
    
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        
        h1 {{
            color: #333;
            margin: 0 0 20px 0;
            font-size: 24px;
        }}
        
        #cy {{
            width: {width};
            height: {height};
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .controls {{
            margin-bottom: 15px;
            padding: 10px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        
        button {{
            padding: 8px 16px;
            margin-right: 10px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        
        button:hover {{
            background: #45a049;
        }}
        
        .info {{
            margin-top: 15px;
            padding: 10px;
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
            font-size: 13px;
        }}
        
        .legend {{
            margin-top: 15px;
            padding: 10px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
        }}
        
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 5px;
        }}
        
        .legend-box {{
            display: inline-block;
            width: 20px;
            height: 12px;
            margin-right: 5px;
            vertical-align: middle;
        }}
        
        .popper-tooltip {{
            position: fixed;
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            max-width: 300px;
            z-index: 9999;
            pointer-events: none;
            line-height: 1.4;
            display: none;
        }}
    </style>
</head>
<body>
    <h1>{html_title}</h1>
    
    <div class="controls">
        <button onclick="cy.fit()">Fit to Screen</button>
        <button onclick="cy.center()">Center</button>
        <button onclick="cy.layout({{name: '{layout}', rankDir: 'LR', nodeSep: 50, rankSep: 100}}).run()">Reset Layout</button>
    </div>
    
    <div id="cy"></div>
    
    <div class="legend">
        <strong>Legend:</strong>
        <div class="legend-item">
            <span class="legend-box" style="background: #fff; border: 2px solid #ccc;"></span>
            <span>Task Node</span>
        </div>
        <div class="legend-item">
            <span class="legend-box" style="background: #fff7e6; border: 2px dashed #ffa940;"></span>
            <span>Latent Risk</span>
        </div>
        <div class="legend-item">
            <span class="legend-box" style="border-top: 2px solid #000;"></span>
            <span>Cascade (>>)</span>
        </div>
        <div class="legend-item">
            <span class="legend-box" style="border-top: 2px dashed #000;"></span>
            <span>Contagion (@)</span>
        </div>
    </div>
    
    <div class="info">
        <strong>💡 Interaction Tips:</strong>
        • Drag nodes to rearrange • Scroll to zoom • Click & drag background to pan • Hover over nodes for details
    </div>
    
    <script>
        // Initialize Cytoscape
        var cy = cytoscape({{
            container: document.getElementById('cy'),
            
            elements: {json.dumps(elements, indent=12)},
            
            style: [
                // Task nodes (white background, solid border)
                {{
                    selector: 'node.task',
                    style: {{
                        'shape': 'round-rectangle',
                        'background-color': '#fff',
                        'border-width': 2,
                        'border-color': '#ccc',
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '16px',
                        'font-weight': 'bold',
                        'font-family': 'Arial, sans-serif',
                        'color': '#333',
                        'width': 180,
                        'height': 80,
                        'padding': 14,
                        'text-wrap': 'wrap',
                        'text-max-width': '160px'
                    }}
                }},
                // Latent risk nodes (orange background, dashed border)
                {{
                    selector: 'node.latent',
                    style: {{
                        'shape': 'round-rectangle',
                        'background-color': '#fff7e6',
                        'border-width': 2,
                        'border-color': '#ffa940',
                        'border-style': 'dashed',
                        'label': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '16px',
                        'font-weight': 'bold',
                        'font-family': 'Arial, sans-serif',
                        'color': '#333',
                        'width': 180,
                        'height': 80,
                        'padding': 14,
                        'text-wrap': 'wrap',
                        'text-max-width': '160px'
                    }}
                }},
                // Task edges (solid, for >> operator)
                {{
                    selector: 'edge.task_edge',
                    style: {{
                        'width': 2,
                        'line-color': '#000',
                        'target-arrow-color': '#000',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'line-style': 'solid'
                    }}
                }},
                // Latent edges (dashed, for @ operator)
                {{
                    selector: 'edge.latent_edge',
                    style: {{
                        'width': 2,
                        'line-color': '#000',
                        'target-arrow-color': '#000',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'line-style': 'dashed'
                    }}
                }},
                // Selected nodes
                {{
                    selector: ':selected',
                    style: {{
                        'border-width': 4,
                        'border-color': '#2196F3'
                    }}
                }}
            ],
            
            layout: {{
                name: '{layout}',
                rankDir: 'LR',
                nodeSep: 50,
                rankSep: 100
            }}
        }});
        
        // Add hover tooltips with simple DOM positioning
        var tooltipDiv = null;
        
        cy.nodes().forEach(function(node) {{
            node.on('mouseover', function(e) {{
                var tooltipText = node.data('tooltip');
                
                // Create tooltip element if it doesn't exist
                if (!tooltipDiv) {{
                    tooltipDiv = document.createElement('div');
                    tooltipDiv.className = 'popper-tooltip';
                    document.body.appendChild(tooltipDiv);
                }}
                
                // Set content and show
                tooltipDiv.innerHTML = tooltipText;
                tooltipDiv.style.display = 'block';
                
                // Position tooltip above the node
                var renderedPosition = node.renderedPosition();
                var cyContainer = document.getElementById('cy').getBoundingClientRect();
                
                tooltipDiv.style.left = (cyContainer.left + renderedPosition.x - tooltipDiv.offsetWidth / 2) + 'px';
                tooltipDiv.style.top = (cyContainer.top + renderedPosition.y - tooltipDiv.offsetHeight - 10) + 'px';
            }});
            
            node.on('mouseout', function(e) {{
                if (tooltipDiv) {{
                    tooltipDiv.style.display = 'none';
                }}
            }});
        }});
        
        // Update tooltip position on pan/zoom
        cy.on('pan zoom', function() {{
            if (tooltipDiv && tooltipDiv.style.display === 'block') {{
                tooltipDiv.style.display = 'none';
            }}
        }});
        
        // Make it responsive
        window.addEventListener('resize', function() {{
            cy.resize();
            cy.fit();
        }});
    </script>
</body>
</html>"""
        
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        abs_path = os.path.abspath(filename)
        print(f"✓ Exported Cytoscape visualization to: {abs_path}")
        print(f"  → Self-contained HTML, works in any browser")
        print(f"  → Interactive: drag nodes, zoom, pan")
        print(f"  → Hover tooltips enabled")
        print(f"  → File size: ~{len(html_content) / 1024:.1f} KB")
        
        return abs_path
    
    @staticmethod
    def export_layout(cyto_widget, filename: str):
        """
        Export node positions from current layout.
        
        Args:
            cyto_widget: Cytoscape widget instance
            filename: JSON file to save positions
        
        Returns:
            Dictionary of positions
        """
        positions = {}
        
        # Try to get positions from the widget
        try:
            # Access the underlying cytoscape graph data
            if hasattr(cyto_widget, '_graph') and hasattr(cyto_widget._graph, '_nodes'):
                for node in cyto_widget._graph._nodes:
                    if hasattr(node, 'data') and 'id' in node.data:
                        node_id = node.data['id']
                        if hasattr(node, 'position') and node.position is not None:
                            positions[node_id] = dict(node.position)
            elif hasattr(cyto_widget, 'graph') and hasattr(cyto_widget.graph, 'nodes'):
                for node in cyto_widget.graph.nodes:
                    if hasattr(node, 'data') and 'id' in node.data:
                        node_id = node.data['id']
                        if hasattr(node, 'position') and node.position is not None:
                            positions[node_id] = dict(node.position)
        except Exception as e:
            print(f"Warning: Could not extract all positions: {e}")
        
        if not positions:
            print("⚠️  No positions found. Make sure to drag nodes before saving layout.")
            return {}
        
        with open(filename, 'w') as f:
            json.dump(positions, f, indent=2)
        
        print(f"✓ Saved {len(positions)} node positions to {filename}")
        return positions
    
    @staticmethod
    def import_layout(cyto_widget, filename: str):
        """
        Import node positions from saved layout.
        
        Args:
            cyto_widget: Cytoscape widget instance
            filename: JSON file with saved positions
        
        Returns:
            Number of positions loaded
        """
        try:
            with open(filename, 'r') as f:
                positions = json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Layout file not found: {filename}")
            return 0
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON in layout file: {filename}")
            return 0
        
        loaded_count = 0
        
        # Try to set positions
        try:
            if hasattr(cyto_widget, '_graph') and hasattr(cyto_widget._graph, '_nodes'):
                for node in cyto_widget._graph._nodes:
                    if hasattr(node, 'data') and 'id' in node.data:
                        node_id = node.data['id']
                        if node_id in positions:
                            node.position = positions[node_id]
                            loaded_count += 1
            elif hasattr(cyto_widget, 'graph') and hasattr(cyto_widget.graph, 'nodes'):
                for node in cyto_widget.graph.nodes:
                    if hasattr(node, 'data') and 'id' in node.data:
                        node_id = node.data['id']
                        if node_id in positions:
                            node.position = positions[node_id]
                            loaded_count += 1
        except Exception as e:
            print(f"Warning: Could not set all positions: {e}")
        
        if loaded_count > 0:
            # Use preset layout to show the loaded positions
            cyto_widget.set_layout(name='preset', animate=False)
            print(f"✓ Loaded {loaded_count} node positions from {filename}")
        else:
            print("⚠️  No positions could be loaded.")
        
        return loaded_count


def visualize_risk_dag(risk_dag, **kwargs):
    """
    Convenience function to create graph visualization.
    
    Args:
        risk_dag: RiskDAG instance
        **kwargs: Additional arguments passed to CytoscapeVisualizer.visualize()
    
    Returns:
        ipycytoscape widget
    
    Example:
        >>> cyto = visualize_risk_dag_cytoscape(dag, layout='dagre')
        >>> display(cyto)  # In Jupyter
        >>> 
        >>> # Save layout after dragging nodes
        >>> CytoscapeVisualizer.export_layout(cyto, 'my_layout.json')
        >>> 
        >>> # Reload layout
        >>> cyto = visualize_risk_dag_cytoscape(dag)
        >>> CytoscapeVisualizer.import_layout(cyto, 'my_layout.json')
        >>> display(cyto)
    """
    return GraphVisualizer.visualize(risk_dag, **kwargs)
