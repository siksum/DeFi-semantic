import streamlit as st
import pandas as pd
import json
import os

# 샘플 데이터 경로 (실제 데이터 경로로 변경해주세요)
DATA_PATH = "../../decoded_logs"

def load_transaction_data(filename):
    """파일에서 트랜잭션 데이터를 로드합니다."""
    try:
        file_path = os.path.join(DATA_PATH, f"{filename}.json")
        print(file_path)
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def read_reciept():
    original_filename = "0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838"
    decoded_filename = "tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838"
    semantic_filename = "tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838_graph"
    st.write(f"Transaction Receipt: {original_filename}")
    
    # 트랜잭션 데이터 로드
    tx_original_data = load_transaction_data(original_filename)
    tx_decoded_data = load_transaction_data(decoded_filename)
    tx_semantic_data = load_transaction_data(semantic_filename)
    if tx_original_data:
        # 탭 생성
        tab1, tab2, tab3, tab4 = st.tabs(["Basic Information", "Original Events", "Detailed Information", "Semantic Graph"])
        
        with tab1:
            st.subheader("Transaction Basic Information")
            st.download_button(label="Download Raw Data", data=json.dumps(tx_original_data), file_name=f"{original_filename}.json")
            tx_info = len(tx_original_data["events"])
            tx_time = tx_original_data["timestamp"]
            tx_hash = tx_original_data["transactionHash"]
            df = pd.DataFrame({
                'Item': ['Event Count', 'Time', 'Hash'],
                'Value': [tx_info, tx_time, tx_hash]
            })
            st.dataframe(df, hide_index=True)
            
            st.subheader("Detailed Information")
            if "show_raw_data" in st.session_state and st.session_state.show_raw_data:
                st.json(tx_original_data)
            else:
                st.info("원본 데이터를 보려면 사이드바에서 'Show raw data'를 체크하세요.")

        with tab2:
            st.subheader("Original Transaction Events")
            if "events" in tx_original_data and tx_original_data["events"]:
                events = tx_original_data["events"]
                for i, event in enumerate(events):
                    with st.expander(f"Event #{i+1}: {event.get('name', 'No name')}"):
                        st.write("**Contract Address:**", event.get("address", "N/A"))
                        st.write("**Event Name:**", event.get("name", "N/A"))
                        
                        if "inputs" in event and event["inputs"]:
                            st.write("**Arguments:**")
                            # 필요한 필드만 추출하여 새로운 데이터 구조 생성
                            args_data = []
                            for input_item in event["inputs"]:
                                args_data.append({
                                    "Name": input_item.get("name", ""),
                                    "Type": input_item.get("type", ""),
                                    "Value": str(input_item.get("rawValue", ""))  # 문자열로 변환하여 복잡한 값도 처리
                                })
                            args_df = pd.DataFrame(args_data)
                            st.dataframe(args_df, hide_index=True)
            else:
                st.info("No transaction events.")
        
        with tab3:
            st.subheader("Decoded Transaction Events")
            if "events" in tx_decoded_data and tx_decoded_data["events"]:
                events = tx_decoded_data["events"]
                for i, event in enumerate(events):
                    with st.expander(f"Event #{event.get('eventIndex', 'No index')}: {event.get('name', 'No name')}"):
                        st.write("**Contract Address:**", event.get("address", "N/A"))
                        st.write("**Event Name:**", event.get("name", "N/A"))
                        
                        if "inputs" in event and event["inputs"]:
                            st.write("**Arguments:**")
                            # 필요한 필드만 추출하여 새로운 데이터 구조 생성
                            args_data = []
                            for input_item in event["inputs"]:
                                args_data.append({
                                    "Name": input_item.get("name", ""),
                                    "Type": input_item.get("type", ""),
                                    "Value": str(input_item.get("displayValue", input_item.get("rawValue", "")))
                                })
                            args_df = pd.DataFrame(args_data)
                            st.dataframe(args_df, hide_index=True)
            else:
                st.info("No transaction events.")
        
        with tab4:
            st.subheader("Transaction Graph Data")
            
            # 그래프 HTML 파일 표시
            with st.expander("Graph Visualization", expanded=True):
                # HTML 파일 경로 생성 (tx_decoded_data 파일 경로에서 파일명 추출)
                graph_html_path = "../tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838_graph.html"
                
                # 디버그 정보 (필요시 주석 해제)
                # st.write(f"Graph HTML path: {graph_html_path}")
                # st.write(f"File exists: {os.path.exists(graph_html_path)}")
                
                if os.path.exists(graph_html_path):
                    try:
                        # HTML 파일 읽기
                        with open(graph_html_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        
                        # HTML 내용 표시
                        st.components.v1.html(html_content, height=600, scrolling=True)
                    except Exception as e:
                        st.error(f"Error loading graph visualization: {str(e)}")
                else:
                    st.info("Graph visualization not available for this transaction.")
                    st.write("Expected path:", graph_html_path)
            
            # 노드 정보 표시
            with st.expander("Nodes Information", expanded=False):
                if "nodes" in tx_semantic_data and tx_semantic_data["nodes"]:
                    nodes_data = []
                    for node in tx_semantic_data["nodes"]:
                        nodes_data.append({
                            "ID": node.get("id", ""),
                            "Type": node.get("type", ""),
                            "Size": node.get("size", ""),
                            "Title": node.get("title", "")
                        })
                    nodes_df = pd.DataFrame(nodes_data)
                    st.dataframe(nodes_df, hide_index=True)
                else:
                    st.info("No node information available.")
            
            # 엣지 정보 표시
            with st.expander("Edges Information", expanded=False):
                if "edges" in tx_semantic_data and tx_semantic_data["edges"]:
                    edges_data = []
                    for edge in tx_semantic_data["edges"]:
                        edges_data.append({
                            "From": edge.get("from", ""),
                            "To": edge.get("to", ""),
                            "Event": edge.get("event", ""),
                            "Token": edge.get("token", ""),
                            "Amount": edge.get("amount", ""),
                            "Event Index": edge.get("event_index", "")
                        })
                    edges_df = pd.DataFrame(edges_data)
                    st.dataframe(edges_df, hide_index=True)
                else:
                    st.info("No edge information available.")
    else:
        st.warning("트랜잭션 데이터를 불러올 수 없습니다.")

def load_page():
    # 파일 목록은 실제 데이터 폴더의 파일을 스캔하도록 수정 가능
    file_list = ["bZx Hack"]
    
    st.sidebar.selectbox("Transaction Selection", file_list, key="file_name")
    st.sidebar.checkbox("Show raw data", value=False, key="show_raw_data")

    # 함수 자체를 navigation에 전달
    pg = st.navigation([read_reciept])
    pg.run()

def main():
    st.title("Transaction Semantic Graph")
    st.write("This app can visualize the semantic graph of a transaction.")

    load_page()

if __name__ == "__main__":
    main()