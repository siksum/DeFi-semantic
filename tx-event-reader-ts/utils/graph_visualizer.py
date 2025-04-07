import json
import networkx as nx
from pyvis.network import Network
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
import re
import os
import traceback

# JSON 파일 로드 및 기본 구조 검증
def load_transaction_data(file_path, debug=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 기본 구조 검증
        if debug:
            print(f"JSON 파일 '{file_path}' 로드 완료")
            print(f"데이터 키: {list(data.keys())}")
            if "events" in data:
                print(f"이벤트 수: {len(data['events'])}")
                if len(data['events']) > 0:
                    print(f"첫 번째 이벤트 키: {list(data['events'][0].keys())}")
            else:
                print("경고: 'events' 키가 없습니다.")
        
        return data
    except Exception as e:
        print(f"JSON 파일 로드 중 오류 발생: {e}")
        traceback.print_exc()
        return None

# 자금 이동 이벤트 유형 정의
fund_transfer_events = [
    "Transfer", "Withdrawal", "Deposit", "Mint", "Borrow", 
    "LogDeposit", "LogWithdraw", "EthPurchase", "TokenPurchase",
    "KyberTrade", "ExecuteTrade", "TradeExecute", "EtherReceival"
]

def build_transaction_graph(data, debug=False):
    # 그래프 초기화
    G = nx.DiGraph()
    
    # 엣지 정보 저장을 위한 리스트
    edges_info = []
    
    # 주소별 거래 금액 추적
    address_total_volume = defaultdict(float)
    
    # 데이터 구조 확인
    if "events" not in data:
        print("오류: JSON 파일에 'events' 키가 없습니다.")
        if debug:
            print(f"데이터 키: {list(data.keys())}")
        return G
    
    # 이벤트 카운터 및 처리된 이벤트 수
    event_counter = 0
    processed_events = 0
    
    # 이벤트를 eventIndex 기준으로 정렬
    sorted_events = sorted(data["events"], key=lambda x: x.get("eventIndex", event_counter))
    
    # 이벤트 순회
    for event_counter, event in enumerate(sorted_events):
        # 필수 필드 확인
        if "name" not in event:
            if debug:
                print(f"경고: 이벤트 #{event_counter}에 'name' 필드가 없습니다.")
            continue
        
        event_name = event["name"]
        
        # 이벤트 인덱스 처리
        event_index = event.get("eventIndex", event_counter)
        
        if debug:
            print(f"이벤트 처리 중: #{event_index} - {event_name}")
        
        # 자금 이동 이벤트만 처리
        if event_name in fund_transfer_events or "Transfer" in event_name or "Mint" in event_name or "Borrow" in event_name:
            source = None
            target = None
            amount = 0
            token_symbol = ""
            
            # 입력값 필드 확인
            if "inputs" not in event:
                if debug:
                    print(f"경고: 이벤트 #{event_index} ({event_name})에 'inputs' 필드가 없습니다.")
                continue
            
            # 각 이벤트 유형별 소스, 대상, 금액 추출
            inputs = event["inputs"]
            
            # Transfer 이벤트 처리
            if event_name == "Transfer" or "Transfer" in event_name:
                if debug:
                    print(f"Transfer 이벤트 #{event_index} 필드:")
                    for input_item in inputs:
                        print(f"  - {input_item['name']}: {input_item.get('displayValue') or input_item.get('rawValue')}")
                
                for input_item in inputs:
                    # 소스 필드 (from, src)
                    if input_item["name"].lower() in ["from", "src", "source", "sender"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                        if debug:
                            print(f"  소스 찾음: {source} (필드: {input_item['name']})")
                    
                    # 대상 필드 (to, dst)
                    elif input_item["name"].lower() in ["to", "dst", "destination", "receiver", "recipient"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                        if debug:
                            print(f"  대상 찾음: {target} (필드: {input_item['name']})")
                    
                    # 금액 필드
                    elif input_item["name"].lower() in ["value", "amount", "wad", "tokens", "val"]:
                        # 숫자 형식 처리
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        
                        token_symbol = input_item.get("symbol", "")
                        if debug:
                            print(f"  금액 찾음: {amount} {token_symbol} (필드: {input_item['name']})")
                
                # 소스나 타겟이 없는 경우 기본값 설정
                if not source:
                    if "address" in event:
                        source = event["address"]
                        if debug:
                            print(f"  소스 기본값 설정: {source} (이벤트 주소)")
                    else:
                        source = "External"
                        if debug:
                            print(f"  소스 기본값 설정: External")
                
                if not target:
                    target = "External"
                    if debug:
                        print(f"  대상 기본값 설정: External")
            
            # Mint 이벤트 처리 - 특수 케이스
            elif event_name == "Mint" or "Mint" in event_name:
                # 기본적으로 컨트랙트 주소를 소스로 설정
                if "address" in event:
                    source = event["address"]
                else:
                    source = "External"
                
                for input_item in inputs:
                    # to 또는 account 필드에서 목적지 주소 찾기
                    if input_item["name"] in ["to", "account", "dst", "user", "minter"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                    # 금액 필드 처리
                    elif input_item["name"] in ["value", "amount", "wad", "mintAmount", "mintTokens"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 대상이 없는 경우
                if not target:
                    for input_item in inputs:
                        # 다른 적절한 필드 찾기
                        value = input_item.get("displayValue") or input_item.get("rawValue")
                        if isinstance(value, str) and (value.startswith("0x") or "contract" in value.lower()):
                            target = value
                            break
                
                # 여전히 타겟이 없으면 External로 설정
                if not target:
                    target = "External"
                
                if debug:
                    print(f"Mint 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # AccrueInterest 이벤트도 추가
            elif event_name == "AccrueInterest":
                # 컨트랙트 주소를 소스로 설정
                if "address" in event:
                    source = event["address"]
                else:
                    source = "External"
                
                # AccrueInterest는 내부 이벤트이므로 대상도 동일하게 설정
                target = source
                
                # 금액 필드 찾기
                for input_item in inputs:
                    if input_item["name"] in ["interestAccumulated", "borrowIndex", "totalBorrows"]:
                        try:
                            if "formattedValue" in input_item:
                                amount = float(input_item.get("formattedValue", 0))
                                token_symbol = input_item.get("symbol", "")
                                break
                        except (ValueError, TypeError):
                            pass
            
            # Deposit 이벤트 처리
            elif event_name in ["Deposit", "LogDeposit"]:
                for input_item in inputs:
                    if input_item["name"] in ["src", "from", "user", "sender"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["dst", "to", "reserve"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["amount", "value", "wad"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 소스나 대상이 없는 경우 기본값 설정
                if not source:
                    source = "External"
                if not target and "address" in event:
                    target = event["address"]
            
            # Withdrawal 이벤트 처리
            elif event_name in ["Withdrawal", "LogWithdraw"]:
                for input_item in inputs:
                    if input_item["name"] in ["src", "from", "reserve"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["dst", "to", "user", "receiver"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["amount", "value", "wad"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 소스나 대상이 없는 경우 기본값 설정
                if not source and "address" in event:
                    source = event["address"]
                if not target:
                    target = "External"
            
            # Borrow 이벤트 처리
            elif event_name == "Borrow":
                # 컨트랙트 주소를 소스로 설정
                if "address" in event:
                    source = event["address"]
                else:
                    source = "External"
                
                # 차용자를 대상으로 설정
                target = None
                
                for input_item in inputs:
                    if input_item["name"] in ["borrower", "account", "user"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["borrowAmount", "amount", "value"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 대상이 없으면 처리하지 않음
                if not target:
                    continue
                
                if debug:
                    print(f"Borrow 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # TokenPurchase 이벤트 처리
            elif event_name == "TokenPurchase":
                # 컨트랙트 주소를 소스로 설정
                if "address" in event:
                    source = event["address"]
                else:
                    source = "External"
                
                # 구매자를 대상으로 설정
                target = None
                
                for input_item in inputs:
                    if input_item["name"] in ["buyer", "to", "dst"]:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["tokens_bought", "amount", "value"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 대상이 없으면 처리하지 않음
                if not target:
                    continue
                
                if debug:
                    print(f"TokenPurchase 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # EthPurchase 이벤트 처리
            elif event_name == "EthPurchase":
                # 구매자를 소스로 설정
                source = None
                
                for input_item in inputs:
                    if input_item["name"] in ["buyer", "from", "src"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["eth_bought", "amount", "value"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 컨트랙트 주소를 대상으로 설정
                if "address" in event:
                    target = event["address"]
                else:
                    target = "External"
                
                # 소스가 없으면 처리하지 않음
                if not source:
                    continue
                
                if debug:
                    print(f"EthPurchase 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # TradeExecute 이벤트 처리
            elif event_name == "TradeExecute" or event_name == "ExecuteTrade":
                # 거래자를 소스로 설정
                source = None
                
                for input_item in inputs:
                    if input_item["name"] in ["sender", "trader", "from", "src"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["destAmount", "actualDestAmount", "amount", "value"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                    elif input_item["name"] in ["destAddress", "to", "dst"] and not target:
                        target = input_item.get("displayValue") or input_item.get("rawValue")
                
                # 컨트랙트 주소를 대상으로 설정(목적지가 지정되지 않은 경우)
                if not target and "address" in event:
                    target = event["address"]
                elif not target:
                    target = "External"
                
                # 소스가 없으면 처리하지 않음
                if not source:
                    continue
                
                if debug:
                    print(f"TradeExecute 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # EtherReceival 이벤트 처리
            elif event_name == "EtherReceival":
                # 보낸 사람을 소스로 설정
                source = None
                
                for input_item in inputs:
                    if input_item["name"] in ["sender", "from", "src"]:
                        source = input_item.get("displayValue") or input_item.get("rawValue")
                    elif input_item["name"] in ["amount", "value"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            try:
                                amount = float(input_item.get("rawValue", 0) or 0)
                            except (ValueError, TypeError):
                                amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                # 컨트랙트 주소를 대상으로 설정
                if "address" in event:
                    target = event["address"]
                else:
                    target = "External"
                
                # 소스가 없으면 처리하지 않음
                if not source:
                    continue
                
                if debug:
                    print(f"EtherReceival 이벤트 처리: source={source}, target={target}, amount={amount}")
            
            # 기타 이벤트 간단히 처리
            else:
                # 간단한 처리: 첫 번째 주소를 소스로, 두 번째 주소를 대상으로
                addresses = []
                for input_item in inputs:
                    value = input_item.get("displayValue") or input_item.get("rawValue")
                    if isinstance(value, str) and value.startswith("0x"):
                        addresses.append(value)
                    
                    # 금액 필드 처리
                    if input_item["name"] in ["amount", "value", "wad"]:
                        try:
                            amount = float(input_item.get("formattedValue", 0) or 0)
                        except (ValueError, TypeError):
                            amount = 0
                        token_symbol = input_item.get("symbol", "")
                
                if len(addresses) >= 2:
                    source = addresses[0]
                    target = addresses[1]
                elif len(addresses) == 1:
                    source = "External"
                    target = addresses[0]
                else:
                    # 주소를 찾을 수 없으면 처리하지 않음
                    continue
            
            # 소스와 대상이 모두 있는 경우만 처리
            if source and target:
                # 주소별 거래량 추적
                address_total_volume[source] += amount
                address_total_volume[target] += amount
                
                # 엣지 정보 저장
                edge_info = {
                    "from_address": source,
                    "to_address": target,
                    "event": event_name,
                    "token": token_symbol,
                    "amount": amount,
                    "event_index": event_index
                }
                edges_info.append(edge_info)
                processed_events += 1
                
                if debug:
                    print(f"이벤트 추가됨: #{event_index} {event_name} - {source} -> {target} ({amount} {token_symbol})")
            else:
                if debug:
                    print(f"이벤트 처리 실패: #{event_index} {event_name} - 소스 또는 대상 없음 (source={source}, target={target})")
    
    # 처리 결과 요약
    print(f"총 {len(sorted_events)}개 이벤트 중 {processed_events}개 처리됨")
    print(f"추출된 엣지 수: {len(edges_info)}")
    
    # 검증: 각 이벤트 인덱스가 처리되었는지 확인
    if debug:
        all_event_indices = [e.get("eventIndex") for e in sorted_events if "eventIndex" in e]
        processed_indices = [e["event_index"] for e in edges_info]
        missing_indices = set(all_event_indices) - set(processed_indices)
        if missing_indices:
            print(f"처리되지 않은 이벤트 인덱스: {sorted(missing_indices)}")
    
    # 이벤트 인덱스로 엣지 정보 정렬
    edges_info.sort(key=lambda x: x["event_index"])
    
    # 엣지 정보를 데이터프레임으로 변환
    if edges_info:
        edges_df = pd.DataFrame(edges_info)
        
        if debug:
            print(f"엣지 DataFrame 열: {list(edges_df.columns)}")
            print(f"처리된 이벤트 인덱스: {sorted([e['event_index'] for e in edges_info])}")
        
        # 모든 고유 주소 추출
        all_addresses = set(edges_df["from_address"].tolist() + edges_df["to_address"].tolist())
        
        # 주소를 기준으로 노드 생성
        for address in all_addresses:
            # 노드 크기 계산 (거래량 기반)
            volume = address_total_volume.get(address, 0)
            size = max(15, min(50, 15 + volume / 1000))
            
            # 주소가 "External"인 경우 특별 처리
            if address == "External":
                G.add_node(address, size=60, title="외부 주소", type="external")
            else:
                G.add_node(address, size=size, title=f"주소: {address}\n거래량: {volume:.2f}", type="address")
        
        # 엣지 추적을 위한 세트
        added_edges = set()
        
        # 엣지 생성
        for _, row in edges_df.iterrows():
            source = row["from_address"]
            target = row["to_address"]
            event = row["event"]
            token = row.get("token", "")
            amount = row.get("amount", 0)
            event_index = row.get("event_index", -1)
            
            # 엣지 키 생성 (소스, 대상, 이벤트 인덱스)
            edge_key = (source, target, event_index)
            
            # 이미 추가된 엣지가 아닌 경우에만 추가
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                
                # 엣지 추가
                G.add_edge(
                    source, target,
                    event=event,
                    token=token,
                    amount=amount,
                    title=f"{event}: {amount} {token}",
                    weight=amount,
                    event_index=event_index
                )
                
                if debug:
                    print(f"그래프에 엣지 추가: {source} -> {target} (이벤트 #{event_index} {event})")
    
    return G

def visualize_graph(G, output_file="transaction_graph.html", debug=False):
    """그래프를 HTML 파일로 시각화"""
    if G.number_of_nodes() == 0:
        print("노드가 없어 시각화할 수 없습니다.")
        return None
    
    # 고립된 노드 제거 (엣지가 없는 노드)
    isolated_nodes = [node for node in G.nodes() if G.degree(node) == 0]
    if isolated_nodes:
        if debug:
            print(f"고립된 노드 {len(isolated_nodes)}개 제거: {', '.join(isolated_nodes[:5])}" + 
                 ("..." if len(isolated_nodes) > 5 else ""))
        G.remove_nodes_from(isolated_nodes)
    
    # 0x0000 주소 제거 (필요시)
    zero_address = "0x0000000000000000000000000000000000000000"
    if zero_address in G.nodes():
        if debug:
            print(f"제로 주소 제거: {zero_address}")
        G.remove_node(zero_address)
    
    if debug:
        print(f"시각화 중: 노드 {G.number_of_nodes()}개, 엣지 {G.number_of_edges()}개")
        
        # 엣지 인덱스 출력 (디버깅용)
        print("엣지 이벤트 인덱스:")
        for edge in G.edges(data=True):
            print(f"  {edge[0]} -> {edge[1]}: 이벤트 #{edge[2].get('event_index', -1)} {edge[2].get('event', 'Unknown')}")
    
    # 네트워크 생성
    net = Network(height="900px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
    
    # 노드 추가
    for node in G.nodes(data=True):
        node_id = node[0]
        attrs = node[1]
        
        # 노드 라벨 처리 (긴 주소 축약)
        if node_id.startswith("0x") and len(node_id) > 20:
            label = f"{node_id[:8]}...{node_id[-4:]}"
        else:
            label = node_id
        
        # 노드 크기
        size = attrs.get("size", 15)
        
        # 노드 색상 설정
        if node_id == "External":
            color = "#ff7700"  # 외부 주소는 주황색
        else:
            color = "#1f77b4"  # 일반 주소는 파란색
        
        # 노드 제목 (마우스 오버시 표시)
        title = attrs.get("title", node_id)
        
        # 노드 추가
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
    
    # 엣지 추가 부분 수정
    for edge in G.edges(data=True):
        source, target = edge[0], edge[1]
        attrs = edge[2]
        
        event = attrs.get("event", "")
        token = attrs.get("token", "")
        amount = attrs.get("amount", 0)
        event_index = attrs.get("event_index", -1)
        
        # 엣지 색상 설정
        if "Transfer" in event:
            color = "#0066cc"  # 전송은 파란색
        elif "Withdraw" in event:
            color = "#ff5050"  # 출금은 빨간색
        elif "Deposit" in event:
            color = "#00cc66"  # 입금은 녹색
        elif "Borrow" in event:
            color = "#666666"  # 대출은 회색
        else:
            color = "#999999"  # 기타는 회색
        
        # 엣지 제목 (마우스 오버시 표시)
        title = attrs.get("title", f"{event}: {amount} {token}")
        
        # 엣지 너비 (금액 기반)
        width = max(1, min(5, 1 + amount / 5000))
        
        # 엣지 라벨
        label = f"#{event_index}: {event}"
        
        # 엣지 추가
        net.add_edge(
            source, 
            target, 
            title=title, 
            width=width,
            color=color,
            label=label,
            arrows={"to": {"enabled": True, "scaleFactor": 0.3}}
        )
    
    # 물리 엔진 옵션
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
          "iterations": 2000,
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
          "size": 10,
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
    
    # 파일로 저장
    try:
        net.save_graph(output_file)
        print(f"그래프가 {output_file}에 저장되었습니다.")
    except Exception as e:
        print(f"그래프 저장 중 오류 발생: {e}")
    
    return net

def extract_network_data_from_html(html_file_path, debug=False):
    """HTML 파일에서 nodes와 edges 데이터를 추출하는 함수"""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 노드 데이터 추출
        nodes_pattern = r'nodes = new vis\.DataSet\(\[(.*?)\]\);'
        nodes_match = re.search(nodes_pattern, html_content, re.DOTALL)
        
        # 엣지 데이터 추출
        edges_pattern = r'edges = new vis\.DataSet\(\[(.*?)\]\);'
        edges_match = re.search(edges_pattern, html_content, re.DOTALL)
        
        if not nodes_match or not edges_match:
            raise ValueError("HTML 파일에서 nodes 또는 edges 데이터를 찾을 수 없습니다")
        
        # 노드 데이터를 JSON으로 변환
        nodes_json_str = "[" + nodes_match.group(1) + "]"
        nodes_json_str = nodes_json_str.replace("'", '"')
        nodes_data = json.loads(nodes_json_str)
        
        # 엣지 데이터를 JSON으로 변환
        edges_json_str = "[" + edges_match.group(1) + "]"
        edges_json_str = edges_json_str.replace("'", '"')
        edges_data = json.loads(edges_json_str)
        
        if debug:
            print(f"HTML에서 추출: 노드 {len(nodes_data)}개, 엣지 {len(edges_data)}개")
        
        return nodes_data, edges_data
    except Exception as e:
        print(f"HTML 데이터 추출 중 오류 발생: {e}")
        if debug:
            traceback.print_exc()
        return [], []

def build_graph_from_html(html_file_path, debug=False):
    """HTML 파일에서 추출한 데이터로 그래프 구축"""
    nodes_data, edges_data = extract_network_data_from_html(html_file_path, debug)
    
    if not nodes_data or not edges_data:
        print("경고: HTML에서 유효한 그래프 데이터를 추출하지 못했습니다.")
        return nx.DiGraph()
    
    # 그래프 생성
    G = nx.DiGraph()
    
    # 노드 추가
    for node in nodes_data:
        G.add_node(
            node["id"],
            label=node.get("label", node["id"]),
            title=node.get("title", node["id"]),
            size=node.get("size", 10),
            color=node.get("color", "#97c2fc")
        )
    
    # 엣지 추가
    for edge in edges_data:
        G.add_edge(
            edge["from"],
            edge["to"],
            event=edge.get("event", "Unknown"),
            title=edge.get("title", ""),
            width=edge.get("width", 1),
            event_index=edge.get("event_index", 0),
            color=edge.get("color", "gray"),
            label=edge.get("label", "")
        )
    
    return G

def analyze_graph(G):
    """그래프 분석 함수: 중심성, 연결 패턴 등 분석"""
    print(f"그래프 정보: 노드 {G.number_of_nodes()}개, 엣지 {G.number_of_edges()}개")
    
    # 노드 중심성 계산
    degree_dict = dict(G.degree())
    
    # 가장 연결이 많은 노드
    if degree_dict:
        max_degree = max(degree_dict.items(), key=lambda x: x[1])
        print(f"가장 많은 연결을 가진 노드: {max_degree[0]} (연결 수: {max_degree[1]})")
    
    # 중심성 계산
    try:
        if G.number_of_nodes() > 1:
            betweenness = nx.betweenness_centrality(G)
            max_betweenness = max(betweenness.items(), key=lambda x: x[1])
            print(f"가장 높은 중심성을 가진 노드: {max_betweenness[0]} (중심성: {max_betweenness[1]:.4f})")
    except Exception as e:
        print(f"중심성 계산 중 오류가 발생했습니다: {e}")
    
    # 가장 일반적인 이벤트 유형 찾기
    event_types = [data.get('event', 'Unknown') for _, _, data in G.edges(data=True)]
    event_counts = pd.Series(event_types).value_counts()
    
    if not event_counts.empty:
        print("\n이벤트 유형 통계:")
        for event, count in event_counts.items():
            print(f"  - {event}: {count}개")
    
    return degree_dict, event_counts

def main(file_path, debug=True):
    """메인 함수: 파일 유형에 따라 처리 방식 선택"""
    # 파일 존재 확인
    if not os.path.exists(file_path):
        print(f"오류: 파일 '{file_path}'을(를) 찾을 수 없습니다.")
        return None
    
    # 파일 확장자 확인
    _, ext = os.path.splitext(file_path)
    
    # 결과 그래프
    G = None
    
    # 출력 파일 이름 생성
    output_file = os.path.basename(file_path)
    output_file = os.path.splitext(output_file)[0]
    
    if ext.lower() == '.json':
        # JSON 파일 처리
        print(f"JSON 파일 '{file_path}' 처리 중...")
        data = load_transaction_data(file_path, debug)
        
        if data:
            G = build_transaction_graph(data, debug)
            output_file += "_graph.html"
        else:
            print("데이터 로드 실패. 처리를 중단합니다.")
            return None
    
    elif ext.lower() == '.html':
        # HTML 파일 처리
        print(f"HTML 파일 '{file_path}' 처리 중...")
        G = build_graph_from_html(file_path, debug)
        output_file += "_reprocessed.html"
    
    else:
        print(f"지원되지 않는 파일 형식: {ext}")
        return None
    
    # 그래프 생성 확인
    if G is None or G.number_of_nodes() == 0:
        print("그래프 생성 실패: 노드가 없습니다.")
        return None
    
    # 그래프 분석
    print("\n그래프 분석 결과:")
    analyze_graph(G)
    
    # 그래프 시각화
    output_path = visualize_graph(G, output_file, debug)
    
    if output_path:
        print(f"\n그래프가 {output_path}에 저장되었습니다.")
    
    return G

# 메인 실행
if __name__ == "__main__":
    # 사용자 입력 파일 경로
    import sys
    
    # 디버그 모드 설정
    debug_mode = True
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # 기본 파일 경로
        file_path = "../decoded_logs/tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json"
    
    G = main(file_path, debug_mode)