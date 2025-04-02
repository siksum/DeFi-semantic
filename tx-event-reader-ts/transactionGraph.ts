// This file will generate a semantic graph of address interactions and value flows
// Based on previously decoded logs

import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";

// A simplified type for a log entry with decoded data
interface DecodedLog {
  index: number;
  event: string;
  from: string;
  to: string;
  token?: string;
  amount?: number;
}

interface Node {
  address: string;
  balanceChanges: Record<string, number>; // token => net change
}

interface Edge {
  from: string;
  to: string;
  token?: string;
  amount?: number;
  event: string;
  index: number;
}

const decodedLogPath = path.join(__dirname, "./output/decodedLogs.json");

function loadDecodedLogs(): DecodedLog[] {
  const raw = fs.readFileSync(decodedLogPath, "utf-8");
  return JSON.parse(raw);
}

function buildGraph(logs: DecodedLog[]): { nodes: Record<string, Node>; edges: Edge[] } {
  const nodes: Record<string, Node> = {};
  const edges: Edge[] = [];

  for (const log of logs) {
    const { from, to, token, amount, event, index } = log;
    if (!from || !to || !amount || !token) continue;

    if (!nodes[from]) nodes[from] = { address: from, balanceChanges: {} };
    if (!nodes[to]) nodes[to] = { address: to, balanceChanges: {} };

    nodes[from].balanceChanges[token] = (nodes[from].balanceChanges[token] || 0) - amount;
    nodes[to].balanceChanges[token] = (nodes[to].balanceChanges[token] || 0) + amount;

    edges.push({ from, to, token, amount, event, index });
  }

  return { nodes, edges };
}

function exportGraphToJson(nodes: Record<string, Node>, edges: Edge[], outputPath: string) {
  const graph = {
    nodes: Object.values(nodes),
    edges,
  };
  fs.writeFileSync(outputPath, JSON.stringify(graph, null, 2));
}

function main() {
  const logs = loadDecodedLogs();
  const { nodes, edges } = buildGraph(logs);
  exportGraphToJson(nodes, edges, path.join(__dirname, "./output/graph.json"));
  console.log("Graph exported to ./output/graph.json");
}

main();
