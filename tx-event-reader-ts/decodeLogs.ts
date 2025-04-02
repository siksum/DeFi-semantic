import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";
import { config } from "dotenv";
import { getAbiWithProxySupport } from "./utils/getAbiWithProxySupport";
import { ContractClassification, classifyAddress } from "./utils/classifyAddress";
import { getTokenMetadata } from "./utils/getTokenMetadata";
import solc from "solc";

config();
const ABI_CACHE_DIR = path.join(__dirname, "./abis");

const provider = new ethers.AlchemyProvider("mainnet", process.env.ALCHEMY_API_KEY);
const logFilePath = path.join(
  __dirname,
  "logs/0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json"
);
const decodedLogOutputPath = path.join(__dirname, "decodedLogs.json");
const addressClassificationMap: Record<string, ContractClassification> = {};
const tokenMetadataCache: Record<string, { symbol: string; decimals: number }> = {};

export async function extractAddressesFromLogs(
  logs: any[],
  provider: ethers.Provider
): Promise<ContractClassification[]> {
  const addressSet: Set<string> = new Set();

  for (const log of logs) {
    addressSet.add(log.address);
    for (const topic of log.topics.slice(1)) {
      if (ethers.isHexString(topic) && topic.length === 66) {
        const possibleAddress = "0x" + topic.slice(26);
        if (
          possibleAddress !== "0x0000000000000000000000000000000000000000" &&
          ethers.isAddress(possibleAddress) &&
          !possibleAddress.startsWith("0x0000000000000000000")
        ) {
          const addr = ethers.getAddress(possibleAddress);
          addressSet.add(addr);
        }
      }
    }
  }

  const results: ContractClassification[] = [];

  for (const address of addressSet) {
    const info = await classifyAddress(address, provider);
    addressClassificationMap[address.toLowerCase()] = info;
    results.push(info);
  }

  return results;
}

function loadSolcVersion(version: string): Promise<typeof solc> {
  return new Promise((resolve, reject) => {
    solc.loadRemoteVersion(version, (err: Error | null, solcSnapshot: typeof solc | undefined) => {
      if (err || !solcSnapshot) reject(err || new Error("Failed to load solc"));
      else resolve(solcSnapshot);
    });
  });
}

async function fetchAbiFromEtherscan(address: string): Promise<any[] | null> {
  const apiKey = process.env.ETHERSCAN_API_KEY;
  const url = `https://api.etherscan.io/api?module=contract&action=getsourcecode&address=${address}&apikey=${apiKey}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (
      data.status === "1" &&
      data.result.length > 0 &&
      data.result[0].SourceCode !== "Contract source code not verified"
    ) {
      const result = data.result[0];
      const sourceCodeRaw = result.SourceCode;
      const contractName = result.ContractName || "Contract";
      const compilerVersion = result.CompilerVersion; 

      if (!compilerVersion) {
        console.warn(`No compiler version found for ${address}`);
        return null;
      }

      const input = {
        language: "Solidity",
        sources: {
          [`${contractName}.sol`]: {
            content: sourceCodeRaw,
          },
        },
        settings: {
          outputSelection: {
            "*": {
              "*": ["abi"],
            },
          },
        },
      };

      console.log(`Loading solc ${compilerVersion} for ${address}...`);
      const solcInstance = await loadSolcVersion(compilerVersion);

      const output = JSON.parse(solcInstance.compile(JSON.stringify(input)));

      if (output.errors) {
        for (const error of output.errors) {
          if (error.severity === "error") {
            console.error(`Compiler error: ${error.formattedMessage}`);
            return null;
          }
        }
      }

      const abis: any[] = [];
      for (const file in output.contracts) {
        for (const contract in output.contracts[file]) {
          abis.push(...output.contracts[file][contract].abi);
        }
      }

      if (abis.length > 0) {
        console.log(`ABI extracted from ${compilerVersion}`);
        return abis;
      } else {
        console.warn(`Compiled successfully, but ABI is empty for ${address}`);
      }
    }
  } catch (err) {
    console.warn(`Failed to fetch ABI from Etherscan for ${address}`, err);
  }

  return null;
}

async function decodeLogs(logs: ethers.Log[]) {
  const decodedLogList: any[] = [];

  for (const log of logs) {
    const info = addressClassificationMap[log.address.toLowerCase()];
    const abiAddress = info?.isProxy && info.implementation ? info.implementation : log.address;
    let abi = await getAbiWithProxySupport(abiAddress, provider);

    if (!abi || abi.length === 0) {
      abi = await fetchAbiFromEtherscan(abiAddress);
      fs.writeFileSync(path.join(ABI_CACHE_DIR, `${abiAddress}.json`), JSON.stringify(abi, null, 2));
      if (!abi || abi.length === 0) {
        console.warn(`Contract ${abiAddress} has bytecode but no verified ABI. Manual ABI recovery not implemented.`);
        continue;
      }
    }

    const iface = new ethers.Interface(abi);

    try {
      const decoded = iface.parseLog(log);
      if (!decoded) {
        console.warn(`Could not decode log ${log.index} from ${log.address}`);
        continue;
      }

      const jsonLog: any = {
        index: log.index,
        function: decoded.name,
        from: log.address,
        args: {},
      };

      for (let i = 0; i < decoded.fragment.inputs.length; i++) {
        const input = decoded.fragment.inputs[i];
        const value = decoded.args[i];
        jsonLog.args[input.name || `arg${i}`] = {
          type: input.type,
          value: typeof value === "bigint" || (value && typeof value === 'object' && 'toString' in value)
            ? value.toString()
            : value,
        };
      }

      decodedLogList.push(jsonLog);
    } catch (err) {
      console.warn(`Could not decode log ${log.index} from ${log.address}`);
    }
  }

  fs.writeFileSync(decodedLogOutputPath, JSON.stringify(decodedLogList, null, 2));
  console.log(`Decoded logs written to ${decodedLogOutputPath}`);
}

async function main() {
  if (!fs.existsSync(logFilePath)) {
    console.error("Log file not found");
    return;
  }

  const rawLogs = JSON.parse(fs.readFileSync(logFilePath, "utf-8"));
  const classifiedAddresses = await extractAddressesFromLogs(rawLogs, provider);

  console.log("\n 주소 분류 결과:");
  for (const { address, type, isProxy, implementation } of classifiedAddresses) {
    console.log(`- ${address} → ${type} ${isProxy ? `(Proxy: ${implementation})` : ""}`);
  }

  await decodeLogs(rawLogs);
}

main().catch(console.error);