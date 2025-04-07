import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";
import { config } from "dotenv";
import { getAbiWithProxySupport, fetchAbiFromEtherscan } from "./utils/getAbiWithProxySupport";
import { ContractClassification, classifyAddress } from "./utils/classifyAddress";
import { getTokenMetadata } from "./utils/getTokenMetadata";

config();

const provider = new ethers.AlchemyProvider("mainnet", process.env.ALCHEMY_API_KEY);
const logFilePath = path.join(
  __dirname,
  "logs/0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json"
);
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

async function decodeLogs(logs: ethers.Log[]) {
  const valueToTokenMap: Record<string, string> = {};

  for (const log of logs) {
    const info = addressClassificationMap[log.address.toLowerCase()];
    const abiAddress = info?.isProxy && info.implementation ? info.implementation : log.address;
    let abi = await getAbiWithProxySupport(abiAddress, provider);

    if (!abi || abi.length === 0) {
      abi = await fetchAbiFromEtherscan(abiAddress);
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

      console.log(`\n Event Index: ${log.index}`);
      console.log(`[${decoded.name}] from ${log.address}`);

      for (const [i, input] of decoded.fragment.inputs.entries()) {
        const name = input.name || `arg${i}`;
        const value = decoded.args[i];
        const type = input.type;
        const nameLower = name.toLowerCase();

        let displayValue = value;

        if (type === "address") {
          displayValue = ethers.getAddress(value);
        } else if (
          type.startsWith("uint") &&
          (nameLower.includes("amount") ||
            nameLower.includes("value") ||
            nameLower.includes("wad") ||
            nameLower.includes("fee") ||
            nameLower.includes("token") ||
            nameLower.includes("price") ||
            nameLower.includes("bought") ||
            nameLower.includes("sold") ||
            nameLower.includes("rate") ||
            nameLower.includes("borrow"))
        ) {
          let tokenMetadata = { symbol: "?", decimals: 18 };
          let candidateAddresses: string[] = [];

          for (const [j, arg] of decoded.args.entries()) {
            if (ethers.isAddress(arg)) candidateAddresses.push(arg);
          }

          candidateAddresses.push(log.address);

          for (const addr of candidateAddresses) {
            if (tokenMetadataCache[addr]) {
              tokenMetadata = tokenMetadataCache[addr];
              break;
            }
            const meta = await getTokenMetadata(addr, provider);
            if (meta.symbol !== "?") {
              tokenMetadata = meta;
              tokenMetadataCache[addr] = meta;
              break;
            }
          }

          const rawValueStr = value.toString();

          if (valueToTokenMap[rawValueStr]) {
            const reused = tokenMetadataCache[valueToTokenMap[rawValueStr]];
            if (reused) tokenMetadata = reused;
          } else {
            for (const addr of candidateAddresses) {
              if (tokenMetadataCache[addr]) {
                valueToTokenMap[rawValueStr] = addr;
                break;
              }
            }
          }

          let symbol = tokenMetadata.symbol;
          let decimals = tokenMetadata.decimals;

          const isCToken = symbol.startsWith("c");
          const isUnderlyingAmount =
            nameLower.includes("mintamount") ||
            nameLower.includes("borrowamount") ||
            nameLower.includes("repayamount");

          if (isCToken && isUnderlyingAmount) {
            const underlyingSymbol = symbol.slice(1);
            const underlyingEntry = Object.entries(tokenMetadataCache).find(
              ([_, meta]) => meta.symbol === symbol
            );
            if (underlyingEntry) {
              symbol = underlyingSymbol;
              decimals = underlyingEntry[1].decimals;
            } else {
              symbol = underlyingSymbol;
              decimals = 18;
            }
          }

          const formattedNum = parseFloat(ethers.formatUnits(value, decimals));
          const formatted = isNaN(formattedNum)
            ? "0"
            : formattedNum.toLocaleString(undefined, {
                maximumFractionDigits: 6,
              });

          displayValue = `${value.toString()} (${formatted} ${symbol})`;
        }

        console.log(`  - ${name} (${type}): ${displayValue}`);
      }
    } catch (err) {
      console.warn(`Could not decode log ${log.index} from ${log.address}`);
    }
  }
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