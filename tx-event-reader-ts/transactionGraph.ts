import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";

const decodedLogPath = path.join(__dirname, "output/decodedLogs.json");
const outputPath = path.join(__dirname, "output/txGraph.json");

interface LogEntry {
//   index: number;
  function: string;
  from: string;
  args: Record<string, { type: string; value: string }>;
}

interface Edge {
  from: string;
  to: string;
  amount?: string;
  function: string;
  index: number;
}

async function buildTransactionGraph() {
  const raw = fs.readFileSync(decodedLogPath, "utf-8");
  const logs: LogEntry[] = JSON.parse(raw);

  const edges: Edge[] = [];

  for (const log of logs) {
    const { function: funcName, from, args, index } = log;
    let to: string | undefined;
    let amount: bigint | undefined;
    const candidateAddresses: string[] = [];

    for (const [argName, argValue] of Object.entries(args)) {
      const { type, value } = argValue as { type: string; value: string };

      if (type === "address") {
        const normalized = ethers.getAddress(value);
        if (!to) to = normalized;
        else candidateAddresses.push(normalized);
      }

      if (type.startsWith("uint")) {
        const num = BigInt(value);
        if (num > 0n) {
          if (!amount) amount = num;
        }
      }
    }

    if (to) {
      edges.push({
        from,
        to,
        amount: amount?.toString(),
        function: funcName,
        index,
      });
    }
  }

  fs.writeFileSync(outputPath, JSON.stringify(edges, null, 2));
  console.log(`Graph data written to ${outputPath}`);
}

buildTransactionGraph().catch(console.error);