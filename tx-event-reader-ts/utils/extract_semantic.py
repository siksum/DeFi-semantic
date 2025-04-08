import json
import networkx as nx
from pyvis.network import Network
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
import re
import os
import traceback
import sys

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


def build_transaction_graph(data, debug=False):
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
            print(f"processing event #{event_index} - {event_name}")
        
        if event_name in fund_transfer_events or "Transfer" in event_name or "Mint" in event_name or "Borrow" in event_name:
            source = None
            target = None
            amount = 0
            token_symbol = ""
        
    
def main(file_path, debug=True):
    if not os.path.exists(file_path):
        print(f"error: file '{file_path}' not found.")
        return None
    
    output_file = os.path.basename(file_path)
    
    G = None
    data = load_transaction_data(file_path, debug)
    if data:
        G = build_transaction_graph(data, debug)
        output_file += "_graph.html"
    else:
        print("warning: failed to load transaction data.")
        return None
    
    


if __name__ == "__main__":
    
    debug_mode = True
    
    file_path = "../decoded_logs/tx_0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json"
    
    G = main(file_path, debug_mode)