import sys
import os
sys.path.append(os.getcwd())
try:
    from src.workflow.graph import build_graph
    graph = build_graph()
    print("Graph Compiled Successfully")
except Exception as e:
    print(f"Graph Compilation Failed: {e}")
    import traceback
    traceback.print_exc()
