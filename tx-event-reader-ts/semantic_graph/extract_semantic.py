import json
import networkx as nx
from collections import defaultdict
import os
import traceback
import pandas as pd
from pyvis.network import Network

def load_semantic_event():
    semantic_event = []
    
    for file in os.listdir("."):
        if file.endswith(".json"):
            with open(f"{file}", "r", encoding="utf-8") as f:
                data = json.load(f)
                semantic_event.append(data)
    
    return semantic_event

def load_transaction_data(file_path, debug=False):
    """
    디코딩 된 이벤트 로그 파일에서 key-value 형태의 데이터 로드
    """
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if debug:
            print(f"success: JSON file '{file_path}' loaded")
            print(f"data keys: {list(data.keys())}")
            if "events" in data:
                print(f"number of events: {len(data['events'])}")
                if len(data['events']) > 0:
                    print(f"first event keys: {list(data['events'][0].keys())}")
            else:
                print("warning: 'events' key not found.")
        
        return data
    
    except Exception as e:
        print(f"error: failed to load JSON file '{file_path}': {e}")
        traceback.print_exc()
        return None


def build_transaction_graph(data, semantic_events_list, debug=False):
    G = nx.DiGraph()
    edges_info = []
    address_total_volume = defaultdict(float)
    event_counter = 0
    processed_events = 0
    
    for event_counter, event in enumerate(data['events']):
        if "name" not in event:
            if debug:
                print(f"warning: event #{event_counter} has no 'name' field.")
            continue
        
        event_name = event['name']
        event_index = event.get('eventIndex', event_counter)
        event_address = event['address']
        event_inputs = event.get('inputs', [])
        
        if debug:
            print(f"#{event_index} {event_name}")
        
        # 이벤트 정의 찾기
        for semantic_event in semantic_events_list:
            if 'events' in semantic_event:
                for event_def in semantic_event['events']:
                    event_def_name = event_def.get('name')
                        
                    if (isinstance(event_def_name, str) and event_def_name == event_name) or \
                       (isinstance(event_def_name, list) and event_name in event_def_name):
                        processed_events += 1
                        
                        # Transfer와 같은 단순 이벤트 처리
                        if 'src' in event_def and 'dst' in event_def and 'amount' in event_def:
                            src = extract_node_value(event, event_def['src'])
                            dst = extract_node_value(event, event_def['dst'])
                            amount = extract_amount_value(event, event_def['amount'])
                            
                            if src and dst and amount:
                                edge_info = {
                                    "from_address": src,
                                    "to_address": dst,
                                    "event": event_name,
                                    "amount": amount,
                                    "event_index": event_index
                                }
                                edges_info.append(edge_info)
                                # 거래량 추적
                                amount_value = float(amount.split()[0]) if isinstance(amount, str) and ' ' in amount else float(amount or 0)
                                address_total_volume[src] += amount_value
                                address_total_volume[dst] += amount_value
                                
                                if debug:
                                    print(f"#{event_index} {event_name}: {src} -> {dst} ({amount})")
                        
                        # 프로토콜 기반 복잡한 이벤트 처리 (Mint, Borrow 등)
                        elif 'protocols' in event_def:
                            for protocol in event_def['protocols']:
                                if 'transfers' in protocol:
                                    for transfer in protocol['transfers']:
                                        src = extract_node_value(event, transfer['src'])
                                        dst = extract_node_value(event, transfer['dst'])
                                        amount = extract_amount_value(event, transfer['amount'])
                                        
                                        if src and dst and amount:
                                            edge_info = {
                                                "from_address": src,
                                                "to_address": dst,
                                                "event": event_name,
                                                "amount": amount,
                                                "event_index": event_index
                                            }
                                            edges_info.append(edge_info)
                                            # 거래량 추적
                                            amount_value = float(amount.split()[0]) if isinstance(amount, str) and ' ' in amount else float(amount or 0)
                                            address_total_volume[src] += amount_value
                                            address_total_volume[dst] += amount_value
                                            
                                            if debug:
                                                print(f"#{event_index} {event_name}: {src} -> {dst} ({amount})")
                        
                        # 기본 transfers 배열 처리 (Deposit 등)
                        elif 'transfers' in event_def:
                            for transfer in event_def['transfers']:
                                src = extract_node_value(event, transfer['src'])
                                dst = extract_node_value(event, transfer['dst'])
                                amount = extract_amount_value(event, transfer['amount'])
                                
                                if src and dst and amount:
                                    edge_info = {
                                        "from_address": src,
                                        "to_address": dst,
                                        "event": event_name,
                                        "amount": amount,
                                        "event_index": event_index
                                    }
                                    edges_info.append(edge_info)
                                    # 거래량 추적
                                    amount_value = float(amount.split()[0]) if isinstance(amount, str) and ' ' in amount else float(amount or 0)
                                    address_total_volume[src] += amount_value
                                    address_total_volume[dst] += amount_value
                                    
                                    if debug:
                                        print(f"#{event_index} {event_name}: {src} -> {dst} ({amount})")
                        break
                
                # 이벤트 처리가 완료되면 다음 이벤트로 넘어감
                if processed_events > event_counter:
                    break
    
    print(f"Total {event_counter+1} events, {processed_events} processed")
    
    # 노드와 엣지 생성
    if edges_info:
        # 모든 고유 주소 추출
        all_addresses = set()
        for edge in edges_info:
            all_addresses.add(edge["from_address"])
            all_addresses.add(edge["to_address"])
        
        # 노드 생성
        for address in all_addresses:
            volume = address_total_volume.get(address, 0)
            size = max(15, min(50, 15 + volume / 1000))
            
            if address == "External":
                G.add_node(address, size=60, title="External", type="external")
            else:
                G.add_node(address, size=size, title=f"Address: {address}\nVolume: {volume:.2f}", type="address")
        
        # 중복 엣지 제거를 위한 세트
        added_edges = set()
        
        # 엣지 생성
        for edge in edges_info:
            source = edge["from_address"]
            target = edge["to_address"]
            event = edge["event"]
            amount = edge["amount"]
            event_index = edge["event_index"]
            
            edge_key = (source, target, event_index)
            
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                
                # 금액과 토큰 분리
                if isinstance(amount, str) and ' ' in amount:
                    amount_parts = amount.split(' ', 1)
                    amount_value = amount_parts[0]
                    token = amount_parts[1]
                else:
                    amount_value = amount
                    token = ""
                
                G.add_edge(
                    source, target,
                    event=event,
                    token=token,
                    amount=amount_value,
                    title=f"{event}: {amount}",
                    weight=float(amount_value) if amount_value else 0,
                    event_index=event_index
                )
    
    return G

def extract_node_value(event, node_spec):
    """이벤트에서 노드 값을 추출하는 함수"""
    if 'event_field' in node_spec:
        field = node_spec['event_field']
        if field == 'address':
            return event['address']
        elif field == 'inputs':
            param_names = node_spec['param_name']
            for input_field in event.get('inputs', []):
                if input_field.get('name') in param_names:
                    return input_field.get('displayValue') or input_field.get('rawValue') 
    elif 'json_key' in node_spec:
        field = node_spec['json_key']
        if field == 'inputs':
            param_names = node_spec['param_name']
            for input_field in event.get('inputs', []):
                if input_field.get('name') in param_names:
                    return input_field.get('displayValue') or input_field.get('rawValue')
    return None

def extract_amount_value(event, amount_spec):
    """이벤트에서 금액 값을 추출하는 함수"""
    if 'event_field' in amount_spec:
        field = amount_spec['event_field']
        if field == 'inputs':
            param_names = amount_spec['param_name']
            for input_field in event.get('inputs', []):
                if input_field.get('name') in param_names:
                    value = input_field.get('formattedValue') or input_field.get('rawValue')
                    symbol = input_field.get('symbol', '')
                    return f"{value} {symbol}".strip()
    elif 'json_key' in amount_spec:
        field = amount_spec['json_key']
        if field == 'inputs':
            param_names = amount_spec['param_name']
            for input_field in event.get('inputs', []):
                if input_field.get('name') in param_names:
                    value = input_field.get('formattedValue') or input_field.get('rawValue')
                    symbol = input_field.get('symbol', '')
                    return f"{value} {symbol}".strip()
    return None

def visualize_graph(G, output_file="transaction_graph.html", debug=False):
    """그래프를 HTML 파일로 시각화"""
    if G.number_of_nodes() == 0:
        print("warning: no nodes in graph.")
        return None
    
    # 고립된 노드 제거
    isolated_nodes = [node for node in G.nodes() if G.degree(node) == 0]
    if isolated_nodes and debug:
        print(f"Isolated nodes {len(isolated_nodes)} removed")
    G.remove_nodes_from(isolated_nodes)
    
    zero_address = "0x0000000000000000000000000000000000000000"
    
    if zero_address in G.nodes():
        G.remove_node(zero_address)
    
    if debug:
        print(f"Visualization: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # 네트워크 생성
    net = Network(height="900px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
    
    # 노드 추가
    for node in G.nodes(data=True):
        node_id = node[0]
        attrs = node[1]
        
        # 긴 주소 축약
        if isinstance(node_id, str) and node_id.startswith("0x") and len(node_id) > 20:
            label = f"{node_id[:8]}...{node_id[-4:]}"
        else:
            label = str(node_id)
        
        # 노드 속성
        size = attrs.get("size", 15)
        color = "#9FB3DF" if node_id == "External" else "#BDDDE4"
        title = attrs.get("title", str(node_id))
        
        net.add_node(
            node_id, 
            label=label, 
            size=size, 
            title=title,
            color=color,
            borderWidth=2,
            borderWidthSelected=4,
            font={'color': 'black'}
        )
    
    # 엣지 추가
    for edge in G.edges(data=True):
        source, target = edge[0], edge[1]
        attrs = edge[2]
        
        event = attrs.get("event", "")
        token = attrs.get("token", "")
        amount = attrs.get("amount", 0)
        event_index = attrs.get("event_index", -1)
        
        # 엣지 색상
        if "Transfer" in event:
            color = "#48A6A7"
        elif "Withdraw" in event:
            color = "#5F8B4C"
        elif "Deposit" in event:
            color = "#FF9A9A"
        elif "Borrow" in event:
            color = "#C68EFD"
        elif "Mint" in event:
            color = "#FF9A9A"
        else:
            color = "#5F8B4C"
        
        # 엣지 속성
        title = attrs.get("title", f"{event}: {amount} {token}")
        width = 1
        # try:
        #     width = max(1, min(5, 1 + float(amount) / 1000 if amount else 1))
        # except (ValueError, TypeError):
        #     width = 1
        label = f"#{event_index}: {event}"
        
        net.add_edge(
            source, 
            target, 
            title=title, 
            width=width,
            color=color,
            label=label,
            arrows={"to": {"enabled": True, "scaleFactor": 0.3}}
        )
    
    # 레이아웃 설정
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.05,
        spring_length=300,
        spring_strength=0.04,
        damping=0.95,
        overlap=0.2
    )
    
    # 상호작용 옵션
    net.set_options("""
    {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -3000,
          "centralGravity": 0.05,
          "springLength": 300,
          "springConstant": 0.04,
          "damping": 0.95,
          "avoidOverlap": 0.2
        },
        "maxVelocity": 40,
        "minVelocity": 0.1,
        "solver": "barnesHut",
        "stabilization": {
          "enabled": true,
          "iterations": 1000,
          "updateInterval": 25
        },
        "timestep": 0.5
      },
      "edges": {
        "smooth": {
          "enabled": true,
          "type": "dynamic",
          "roundness": 0.5
        },
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.3
          }
        },
        "font": {
          "size": 12,
          "strokeWidth": 0,
          "align": "middle"
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      },
      "layout": {
        "improvedLayout": true
      }
    }
    """)
    
    # 파일 저장
    try:
        net.save_graph(output_file)
        print(f"Graph saved to {output_file}")
        return output_file
    except Exception as e:
        print(f"Graph saving error: {e}")
        return None
    
def main(file_path, debug=True):
    if not os.path.exists(file_path):
        print(f"error: file '{file_path}' not found.")
        return None
    
    output_file = os.path.basename(file_path)
    
    semantic_events_list = load_semantic_event()
    
    data = load_transaction_data(file_path, debug)
    if data:
        # 그래프 생성
        G = build_transaction_graph(data, semantic_events_list, debug)
        
        # 그래프 시각화
        if G and G.number_of_nodes() > 0:
            output_html = os.path.splitext(output_file)[0] + "_graph.html"
            visualize_graph(G, output_html, debug)
        else:
            print("warning: no nodes in graph.")
        
        return G
    else:
        print("warning: failed to load transaction data.")
        return None

if __name__ == "__main__":
    debug_mode = True
    file_path = "../decoded_logs/tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json"
    G = main(file_path, debug_mode)