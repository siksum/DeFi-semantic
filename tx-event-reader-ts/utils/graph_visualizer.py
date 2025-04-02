import json
import networkx as nx
import matplotlib.pyplot as plt
import os
from networkx.drawing.nx_agraph import graphviz_layout

# 경로 설정
project_root = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(project_root, "../output/txGraph.json")
output_img = os.path.join(project_root, "../output/txGraph_ordered.png")

# JSON 로드
with open(json_path, "r") as f:
    edges = json.load(f)

# 그래프 생성
G = nx.DiGraph()

# 인덱스를 기준으로 정렬
edges_sorted = sorted(edges, key=lambda x: x.get("index", 0))

for edge in edges_sorted:
    from_addr = edge["from"]
    to_addr = edge["to"]
    function = edge.get("function", "unknown")
    event_index = edge.get("index", "?")
    amount = edge.get("amount")

    label = f"#{event_index} - {function}"
    if amount:
        try:
            # eth_value = int(amount) / 1e18
            label += f"\n{amount}"
        except:
            pass

    G.add_edge(from_addr, to_addr, label=label)

# 시각화
plt.figure(figsize=(24, 12))
pos = graphviz_layout(G, prog="dot")  # 왼쪽 → 오른쪽 흐름

nx.draw(G, pos, with_labels=True, arrows=True, node_size=600, node_color="lightblue", font_size=6)
edge_labels = nx.get_edge_attributes(G, "label")
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=5)

plt.axis("off")
plt.tight_layout()
plt.savefig(output_img, dpi=300)
print(f"Graph saved as {output_img}")
