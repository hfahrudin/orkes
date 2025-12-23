import json
import argparse
import os

import random

FUNCTION_NODE_COLORS = [
    "#E3FAFC",  # light cyan (best bridge blue ↔ green)
    "#D0EBFF",  # soft blue
    "#C5F6FA",  # ice cyan
    "#E5DBFF",  # light indigo
    "#D0BFFF",  # soft lavender
    "#EDF2FF",  # very light blue-gray
    "#E9ECEF",  # cool light gray
    "#F1F3F5",  # ultra light slate
    "#DEE2E6",  # soft neutral gray
    "#F3F0FF",  # light lavender gray
]

color_index = 0

def next_color():
    global color_index
    color = FUNCTION_NODE_COLORS[color_index]
    color_index = (color_index + 1) % len(FUNCTION_NODE_COLORS)
    return color

def generate_inspector_html(trace_file):
    with open(trace_file, 'r') as f:
        trace_data = json.load(f)

    # --- 1. Process Nodes ---
    nodes = []
    for node_trace in trace_data.get('nodes_trace', []):
        node_id = node_trace['node_name']
        node_label = node_trace['node_name']
        node_meta = node_trace.get('meta', {})
        node_type = node_meta.get('type', 'function_node')
        node_trace.pop('meta', {})
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
            color = next_color()
        node_data = {
            "id": node_id,
            "label": node_label,
            "shape": shape,
            "color": color,
        }
        node_data.update(node_trace)
        nodes.append(node_data)

    # --- 2. Process Edges ---
    edges = []
    for edge_trace in trace_data.get('edges_trace', []):
        et = edge_trace.copy()
        
        edge_meta = et.pop('meta', {}) # Removes 'meta' from 'et' so it's not in the UI
        edge_type = edge_meta.get('type', 'forward_edge')

        # forward_edge = solid line
        # conditional_edge = dashed line
        dashes = False

        
        if edge_type == 'conditional_edge':
            dashes = [5, 5] # 5px dash, 5px gap
        elif edge_type == 'forward_edge':
            dashes = False

        # 3. Build Edge Data
        edge_data = {
            "from": et.pop('from_node'),
            "to": et.pop('to_node'),
            "label": f"Run {et.get('edge_run_number', '')}",
            "dashes": dashes,
            "width": 2
        }
        
        # 4. Update with remaining data (meta and from/to already removed)
        edge_data.update(et)
        edges.append(edge_data)

    # --- 3. HTML Template with Minimize Feature ---
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trace Inspector</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style>
            body { font-family: 'Segoe UI', sans-serif; margin: 0; height: 100vh; overflow: hidden; background: #f0f2f5; }
            #mynetwork { width: 100%; height: 100%; background: #ffffff; }

            /* Inspector Base */
            #inspector { 
                position: absolute; top: 20px; right: 20px; width: 400px; height: 600px;
                min-width: 300px; min-height: 40px; background: #ffffff; border-radius: 8px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.2); display: flex; flex-direction: column;
                border: 1px solid #ccc; resize: both; overflow: hidden; z-index: 1000;
                transition: height 0.2s ease-in-out;
            }

            /* Minimized State */
            #inspector.minimized {
                height: 42px !important; /* Only header height */
                min-height: 42px !important;
                resize: none;
            }

            #inspector-header { 
                padding: 10px 15px; cursor: move; background: #343a40; color: white; 
                display: flex; justify-content: space-between; align-items: center;
                user-select: none; flex-shrink: 0;
            }

            .header-controls { display: flex; align-items: center; gap: 10px; }
            
            .min-btn {
                background: #555; border: none; color: white; border-radius: 4px;
                width: 24px; height: 24px; cursor: pointer; display: flex;
                align-items: center; justify-content: center; font-weight: bold;
            }
            .min-btn:hover { background: #777; }

            #inspector-content-wrapper { flex-grow: 1; overflow-y: auto; padding: 15px; }
            
            /* Text Display Fixes */
            .prop-row { margin-bottom: 8px; display: flex; flex-direction: column; }
            .key { font-weight: 700; color: #555; font-size: 0.85em; text-transform: uppercase; margin-bottom: 2px; }
            .value { 
                color: #222; font-size: 0.95em; word-wrap: break-word; 
                overflow-wrap: break-word; white-space: pre-wrap;
            }
            pre.json-box {
                background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; 
                font-family: monospace; font-size: 0.85em; white-space: pre-wrap; word-break: break-all;
            }
            .card { border-radius: 8px; padding: 10px; margin-bottom: 10px; border: 1px solid #e1e4e8; }
            .node-card { border-left: 5px solid #007bff; background: #f1f8ff; }
            .edge-card { border-left: 5px solid #6c757d; background: #f8f9fa; }
        </style>
    </head>
    <body>
        
        <div id="mynetwork"></div>

        <div id="inspector">
            <div id="inspector-header">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size: 12px; color: #aaa;">&#x2630;</span>
                    <span>Inspector</span>
                </div>
                <div class="header-controls">
                    <button class="min-btn" onclick="toggleMinimize()" title="Minimize/Maximize">&minus;</button>
                </div>
            </div>
            <div id="inspector-content-wrapper">
                <div id="content">Click a Node or an Edge to view details.</div>
            </div>
        </div>

        <script type="text/javascript">
            const nodes = new vis.DataSet(JSON_NODES);
            const edges = new vis.DataSet(JSON_EDGES);
            const container = document.getElementById('mynetwork');
            const network = new vis.Network(container, { nodes, edges }, {
                edges: { arrows: 'to', font: { size: 11, color: '#888' }, color: { inherit: 'both' }, smooth: true },
                physics: { enabled: true, solver: 'forceAtlas2Based' },
                interaction: { hover: true }
            });

            // Toggle Minimize
            let isMinimized = false;
            let originalHeight = "600px";

            function toggleMinimize() {
                const insp = document.getElementById('inspector');
                const btn = document.querySelector('.min-btn');
                if (!isMinimized) {
                    originalHeight = insp.style.height || "600px";
                    insp.classList.add('minimized');
                    btn.innerHTML = "&#43;"; // Plus sign
                } else {
                    insp.classList.remove('minimized');
                    insp.style.height = originalHeight;
                    btn.innerHTML = "&minus;"; // Minus sign
                }
                isMinimized = !isMinimized;
            }

            network.on("click", function (params) {
                if (isMinimized) toggleMinimize(); // Auto-expand on click if minimized
                
                let html = "";
                let targetData = null;

                if (params.nodes.length > 0) {
                    targetData = nodes.get(params.nodes[0]);
                    html = `<div class="card node-card"><h4>${targetData.label}</h4>`;
                } else if (params.edges.length > 0) {
                    targetData = edges.get(params.edges[0]);
                    html = `<div class="card edge-card"><h4>Edge</h4>`;
                }

                if (targetData) {
                    for (let key in targetData) {
                        if (['id', 'from', 'to', 'shape', 'color', 'label', 'x', 'y', 'dashes', 'width',].includes(key)) continue;
                        let val = targetData[key];
                        let display = (typeof val === 'object') ? `<pre class="json-box">${JSON.stringify(val, null, 2)}</pre>` : val;
                        html += `<div class="prop-row"><span class="key">${key}:</span><div class="value">${display}</div></div>`;
                    }
                    document.getElementById('content').innerHTML = html + '</div>';
                }
            });

            // Drag Logic
            dragElement(document.getElementById("inspector"));
            function dragElement(elmnt) {
                var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
                document.getElementById("inspector-header").onmousedown = function(e) {
                    e = e || window.event;
                    if (e.target.className === 'min-btn') return; // Don't drag if clicking button
                    e.preventDefault();
                    pos3 = e.clientX; pos4 = e.clientY;
                    document.onmouseup = () => { document.onmouseup = null; document.onmousemove = null; };
                    document.onmousemove = (e) => {
                        pos1 = pos3 - e.clientX; pos2 = pos4 - e.clientY;
                        pos3 = e.clientX; pos4 = e.clientY;
                        elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
                        elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
                        elmnt.style.right = 'auto'; elmnt.style.bottom = 'auto';
                    };
                };
            }
        </script>
    </body>
    </html>
    """

    final_html = html_template.replace("JSON_NODES", json.dumps(nodes, indent=2)).replace("JSON_EDGES", json.dumps(edges, indent=2))
    output_filename = f"{os.path.splitext(os.path.basename(trace_file))[0]}_inspector.html"
    with open(output_filename, "w") as f:
        f.write(final_html)
    print(f"Created {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_file")
    args = parser.parse_args()
    generate_inspector_html(args.trace_file)
