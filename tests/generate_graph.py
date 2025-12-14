import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.workflow.graph import APP

try:
    graph_png = APP.get_graph().draw_mermaid_png()
    with open("agent_graph.png", "wb") as f:
        f.write(graph_png)
    print("Graph generated successfully: agent_graph.png")
except Exception as e:
    print(f"Failed to generate graph: {e}")
