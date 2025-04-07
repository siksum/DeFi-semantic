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

// 디코딩된 이벤트 타입 정의
type DecodedEvent = {
  eventIndex: number;
  name: string;
  address: string;
  inputs: {
    name: string;
    type: string;
    rawValue: string;
    displayValue?: string;
    formattedValue?: number;
    symbol?: string;
  }[];
};

// 전체 출력 타입 정의
type DecodedLogsOutput = {
  events: DecodedEvent[];
  timestamp: string;
  transactionHash?: string;
};

async function decodeLogs(logs: ethers.Log[], txHash?: string): Promise<DecodedLogsOutput> {
  const valueToTokenMap: Record<string, string> = {};
  const decodedOutput: DecodedLogsOutput = {
    events: [],
    timestamp: new Date().toISOString(),
    transactionHash: txHash
  };
  
  // 기본 토큰 메타데이터 설정
  const defaultTokenMetadata: Record<string, { symbol: string; decimals: number }> = {
    'eth': { symbol: 'ETH', decimals: 18 },
    'weth': { symbol: 'WETH', decimals: 18 },
    'dai': { symbol: 'DAI', decimals: 18 },
    'usdc': { symbol: 'USDC', decimals: 6 },
    'usdt': { symbol: 'USDT', decimals: 6 },
    'wbtc': { symbol: 'WBTC', decimals: 8 }
  };

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

      // JSON에 저장할 이벤트 객체 생성
      const decodedEvent: DecodedEvent = {
        eventIndex: log.index,
        name: decoded.name,
        address: log.address,
        inputs: []
      };

      // 이벤트 이름으로 토큰 추론
      const eventNameLower = decoded.name.toLowerCase();
      let eventRelatedToken: string | null = null;
      
      if (eventNameLower.includes('eth')) eventRelatedToken = 'eth';
      else if (eventNameLower.includes('weth')) eventRelatedToken = 'weth';
      else if (eventNameLower.includes('dai')) eventRelatedToken = 'dai';
      else if (eventNameLower.includes('usdc')) eventRelatedToken = 'usdc';
      else if (eventNameLower.includes('usdt')) eventRelatedToken = 'usdt';
      else if (eventNameLower.includes('wbtc')) eventRelatedToken = 'wbtc';

      for (const [i, input] of decoded.fragment.inputs.entries()) {
        const name = input.name || `arg${i}`;
        const value = decoded.args[i];
        const type = input.type;
        const nameLower = name.toLowerCase();

        // 입력 파라미터 객체 생성
        const inputParam: DecodedEvent['inputs'][0] = {
          name,
          type,
          rawValue: value.toString()
        };

        if (type === "address") {
          inputParam.displayValue = ethers.getAddress(value);
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

          // 파라미터 이름으로 토큰 추론
          let paramRelatedToken: string | null = null;
          
          if (nameLower.includes('eth')) paramRelatedToken = 'eth';
          else if (nameLower.includes('weth')) paramRelatedToken = 'weth';
          else if (nameLower.includes('dai')) paramRelatedToken = 'dai';
          else if (nameLower.includes('usdc')) paramRelatedToken = 'usdc';
          else if (nameLower.includes('usdt')) paramRelatedToken = 'usdt';
          else if (nameLower.includes('wbtc') || nameLower.includes('btc')) paramRelatedToken = 'wbtc';
          
          // 파라미터 이름으로 추론된 토큰 우선 사용
          if (paramRelatedToken && defaultTokenMetadata[paramRelatedToken]) {
            tokenMetadata = defaultTokenMetadata[paramRelatedToken];
          }
          // 이벤트 이름으로 추론된 토큰 사용
          else if (eventRelatedToken && defaultTokenMetadata[eventRelatedToken]) {
            tokenMetadata = defaultTokenMetadata[eventRelatedToken];
          }

          for (const [j, arg] of decoded.args.entries()) {
            if (ethers.isAddress(arg)) candidateAddresses.push(arg);
          }

          candidateAddresses.push(log.address);

          // 기존 캐시 및 메타데이터 조회 로직
          if (tokenMetadata.symbol === "?") {
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

          // Compound 관련 로직
          const isCToken = symbol.startsWith("c");
          const isUnderlyingAmount =
            nameLower.includes("mintamount") ||
            nameLower.includes("borrowamount") ||
            nameLower.includes("repayamount");

          if (isCToken && isUnderlyingAmount) {
            const underlyingSymbol = symbol.slice(1);
            const underlyingEntry = Object.entries(tokenMetadataCache).find(
              ([_, meta]) => meta.symbol === underlyingSymbol
            );
            if (underlyingEntry) {
              symbol = underlyingSymbol;
              decimals = underlyingEntry[1].decimals;
            } else if (defaultTokenMetadata[underlyingSymbol.toLowerCase()]) {
              symbol = underlyingSymbol;
              decimals = defaultTokenMetadata[underlyingSymbol.toLowerCase()].decimals;
            } else {
              symbol = underlyingSymbol;
              decimals = 18;
            }
          }

          // Mint 이벤트의 mintAmount는 항상 기본 토큰(ETH 등)이어야 함
          if (decoded.name === "Mint" && nameLower === "mintamount") {
            if (symbol.startsWith("c")) {
              symbol = symbol.slice(1);
              if (defaultTokenMetadata[symbol.toLowerCase()]) {
                decimals = defaultTokenMetadata[symbol.toLowerCase()].decimals;
              }
            }
          }

          // EthPurchase 이벤트의 eth_bought는 ETH여야 함
          if (decoded.name === "EthPurchase" && nameLower === "eth_bought") {
            symbol = "ETH";
            decimals = 18;
          }

          const formattedNum = parseFloat(ethers.formatUnits(value, decimals));
          
          // JSON에 추가 정보 저장
          inputParam.formattedValue = formattedNum;
          inputParam.symbol = symbol;
          inputParam.displayValue = `${formattedNum.toLocaleString(undefined, { maximumFractionDigits: 6 })} ${symbol}`;
        }

        // 입력 파라미터를 이벤트에 추가
        decodedEvent.inputs.push(inputParam);
      }

      // 이벤트를 출력 객체에 추가
      decodedOutput.events.push(decodedEvent);

      // 콘솔에도 출력 (필요시)
      console.log(`\n Event Index: ${log.index}`);
      console.log(`[${decoded.name}] from ${log.address}`);
      for (const input of decodedEvent.inputs) {
        console.log(`  - ${input.name} (${input.type}): ${input.displayValue || input.rawValue}`);
      }
    } catch (err) {
      console.warn(`Could not decode log ${log.index} from ${log.address}`);
    }
  }

  return decodedOutput;
}

// JSON 저장 함수
export async function decodeAndSaveLogsAsJson(logs: ethers.Log[], txHash?: string, outputPath?: string): Promise<string> {
  const decodedLogs = await decodeLogs(logs, txHash);
  
  // 기본 출력 경로 설정
  const finalOutputPath = outputPath || path.join(process.cwd(), 'decoded_logs', `tx_${txHash}.json`);
  
  // 디렉토리가 없으면 생성
  const dir = path.dirname(finalOutputPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  
  // JSON 파일로 저장
  fs.writeFileSync(finalOutputPath, JSON.stringify(decodedLogs, null, 2));
  
  console.log(`Decoded logs saved to: ${finalOutputPath}`);
  return finalOutputPath;
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

  await decodeAndSaveLogsAsJson(rawLogs, "0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838");
}

main().catch(console.error);