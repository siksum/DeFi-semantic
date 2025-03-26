import { ethers } from "ethers";
import * as fs from "fs";
import * as path from "path";
import { config } from "dotenv";
config();

const provider = new ethers.AlchemyProvider("mainnet", process.env.ALCHEMY_API_KEY);
const logFilePath = path.join(__dirname, "logs/0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json");

// 주소 타입 확인 함수 (EOA or CA)
async function checkAddressType(provider: ethers.Provider, address: string): Promise<"EOA" | "CA"> {
    const code = await provider.getCode(address);
    return code === "0x" ? "EOA" : "CA";
}

//  주소 추출 및 분류
async function extractAddressesFromLogs(logs: any[], provider: ethers.Provider) {
    const addressSet: Set<string> = new Set();
  
    for (const log of logs) {
      addressSet.add(log.address);
      // topic[0] = event signature → topic[1..] 은 indexed params
      for (const topic of log.topics.slice(1)) {
        if (ethers.isHexString(topic) && topic.length === 66) {
          // 32바이트 주소 padding → 마지막 40자만 추출
          const possibleAddress = "0x" + topic.slice(26);
          if (possibleAddress !== "0x0000000000000000000000000000000000000000" && ethers.isAddress(possibleAddress) && !possibleAddress.startsWith("0x0000000000000000000")) {
            const addr = ethers.getAddress(possibleAddress);
            addressSet.add(addr);
          }
        }
      }
  
      // data 안에 들어간 address는 abi 없으면 해석 불가 → 후처리 예정
    }
  
    const results: { address: string; type: "EOA" | "CA" }[] = [];
  
    for (const address of addressSet) {
      const type = await checkAddressType(provider, address);
      results.push({ address, type });
    }
  
    return results;
  }

async function main() {
    if (!fs.existsSync(logFilePath)) {
      console.error("Log file not found");
      return;
    }
  
    const rawLogs = JSON.parse(fs.readFileSync(logFilePath, "utf-8"));
    const addresses = await extractAddressesFromLogs(rawLogs, provider);
  
    console.log("\n 주소 분류 결과:");
    for (const { address, type } of addresses) {
      console.log(`- ${address} → ${type}`);
    }
  }
  
  main().catch(console.error);