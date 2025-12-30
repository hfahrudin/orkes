import json
import itertools
from typing import Union, Dict, List, Optional
from pathlib import Path
import os
import argparse
from orkes.shared.utils import format_elapsed_time, format_start_time

# Default color palette for function nodes in the visualization.
DEFAULT_FUNCTION_NODE_COLORS = [
    "#E3FAFC", "#D0EBFF", "#C5F6FA", "#E5DBFF", "#D0BFFF",
    "#EDF2FF", "#E9ECEF", "#F1F3F5", "#DEE2E6", "#F3F0FF",
]

class TraceInspector:
    """A class to generate Vis.js compatible HTML visualizations from trace data.

    This class takes a trace of a graph's execution and generates an interactive
    HTML file that visualizes the graph's structure and execution flow.

    Attributes:
        template_path (Path): The path to the HTML template file.
        node_colors (itertools.cycle): An iterator for cycling through the default
                                       node colors.
        html_template (str): The content of the HTML template file.
    """

    def __init__(self, template_path: Optional[str] = None):
        """Initializes the TraceInspector.

        Args:
            template_path (Optional[str], optional): The path to the HTML template.
                If not provided, it defaults to 'inspector_template.html' in the
                same directory as this file.

        Raises:
            FileNotFoundError: If the template file cannot be found.
        """
        if template_path:
            self.template_path = Path(template_path)
        else:
            self.template_path = Path(__file__).parent / "inspector_template.html"
            
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found at: {self.template_path}")

        self.node_colors = itertools.cycle(DEFAULT_FUNCTION_NODE_COLORS)
        self.html_template = self.template_path.read_text(encoding='utf-8')

    def _build_title_card(self, title_data: dict = {}) -> str:
        """Generates the HTML for the title card in the visualization.

        Args:
            title_data (dict, optional): A dictionary of data to display in the
                                         title card. Defaults to {}.

        Returns:
            str: The HTML for the title card.
        """
        data = title_data
        main_title = data.pop('page_title', 'Orkes Trace Visualizer')
        
        status_color_wheel = {
            "FINISHED": "#007bff",
            "FAILED": "#dc3545",
            "INTERRUPTED": "#ffc107",
        }
        
        body_rows = []
        status = data.get("Status", "").upper()
        status_color = status_color_wheel.get(status, "#6c757d")

        header_html = f'''
            <div class="title-header">
                <div class="title-main">
                    <span style="color:{status_color};">&#9679;</span>
                    {main_title}
                </div>
                <button class="min-btn-title" onclick="toggleTitleCard()" title="Minimize/Maximize">&minus;</button>
            </div>
        '''

        for key, value in data.items():
            if isinstance(value, (dict, list)):
                continue
            
            label = key.replace("_", " ").title().replace("Id", "ID")
            val_str = str(value)
            
            row = f'<div class="prop-row"><span class="key">{label}:</span><div class="title-sub">{val_str}</div></div>'
            body_rows.append(row)
            
        body_html = f'<div id="title-card-body">{"".join(body_rows)}</div>'
        
        return header_html + body_html

    def _get_next_color(self) -> str:
        """Returns the next color from the node color iterator."""
        return next(self.node_colors)

    def _process_nodes(self, nodes_trace: List[Dict]) -> List[Dict]:
        """Transforms raw node traces into the format expected by Vis.js.

        Args:
            nodes_trace (List[Dict]): A list of node traces.

        Returns:
            List[Dict]: A list of nodes in Vis.js format.
        """
        nodes = []
        for node_trace in nodes_trace:
            nt = node_trace.copy()
            
            node_id = nt['node_name']
            node_label = nt['node_name']
            node_meta = nt.pop('meta', {})
            node_type = node_meta.get('type', 'function_node')

            shape = 'box'
            color = '#97c2fc'

            if node_type == 'start_node':
                shape = 'ellipse'
                color = "#af71f7"
            elif node_type == 'end_node':
                shape = 'ellipse'
                color = "#3deeb9"
            elif node_type == 'function_node':
                shape = 'box'
                color = self._get_next_color()

            node_data = {
                "id": node_id,
                "label": node_label,
                "shape": shape,
                "color": color,
            }
            node_data.update(nt)
            nodes.append(node_data)
        return nodes

    def _process_edges(self, edges_trace: List[Dict]) -> List[Dict]:
        """Transforms raw edge traces into the format expected by Vis.js.

        Args:
            edges_trace (List[Dict]): A list of edge traces.

        Returns:
            List[Dict]: A list of edges in Vis.js format.
        """
        edges = []
        for edge_trace in edges_trace:
            et = edge_trace.copy()
            edge_meta = et.pop('meta', {})
            edge_type = edge_meta.get('type', 'forward_edge')

            dashes: Union[bool, List[int]] = False
            if edge_type == 'conditional_edge':
                dashes = [5, 5]
            
            et["elapsed"] = format_elapsed_time(et["elapsed"])

            edge_data = {
                "from": et.pop('from_node'),
                "to": et.pop('to_node'),
                "label": f"{et.get('edge_run_number', '')}",
                "dashes": dashes,
                "width": 0.5
            }
            edge_data.update(et)
            edges.append(edge_data)
        return edges

    def generate_html(self, trace_data: Union[str, Dict]) -> str:
        """Generates the HTML content for the visualization.

        Args:
            trace_data (Union[str, Dict]): Either a dictionary containing the trace
                                           or a path to a JSON file.

        Returns:
            str: The complete HTML content.
        """
        if isinstance(trace_data, (str, Path)):
            with open(trace_data, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = trace_data

        self.node_colors = itertools.cycle(DEFAULT_FUNCTION_NODE_COLORS)

        run_id = data.get('run_id')
        elapsed = format_elapsed_time(data.get('elapsed_time'))
        start_time = format_start_time(data.get('start_time'))
        graph_name = data.get('graph_name', 'Unknown Graph')
        status = data.get('status', 'FAILED')
        nodes = self._process_nodes(data.get('nodes_trace', []))
        graph_description = data.get('graph_description') if data.get('graph_description') else "No description provided."
        edges = self._process_edges(data.get('edges_trace', []))
        
        title_card_content = self._build_title_card({
            "page_title": f"Graph: {graph_name}",
            "Run ID": run_id,
            "Status": status.upper(),
            "Start Time": start_time,
            "Elapsed": elapsed,
            "Description": graph_description
        })
        
        final_html = self.html_template.replace(
            "JSON_NODES", json.dumps(nodes, indent=2)
        ).replace(
            "JSON_EDGES", json.dumps(edges, indent=2)
        ).replace(
            "TITLE_CARD_CONTENT", title_card_content)
        
        return final_html

    def generate_viz(self, trace_data: Union[str, Dict], output_path: str = ""):
        """Generates the HTML visualization and saves it to a file.

        Args:
            trace_data (Union[str, Dict]): Either a dictionary containing the trace
                                           or a path to a JSON file.
            output_path (str, optional): The path to save the HTML file. Defaults to "".
        """
        html_content = self.generate_html(trace_data)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Created visualization at: {output_path}")
