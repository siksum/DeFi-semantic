import axios from "axios";
import * as fs from "fs";
import * as path from "path";
import { ethers } from "ethers";
import { config } from "dotenv";
import solc from "solc";
config();

const ABI_CACHE_DIR = path.join(__dirname, "../abis");
if (!fs.existsSync(ABI_CACHE_DIR)) fs.mkdirSync(ABI_CACHE_DIR, { recursive: true });

// EIP-1967 implementation storage slot
const EIP1967_IMPLEMENTATION_SLOT =
  "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";

// 1. Implementation 주소 조회 (Proxy 대응)
async function getImplementationAddress(
  proxyAddress: string,
  provider: ethers.Provider
): Promise<string | null> {
  try {
    const raw = await provider.getStorage(proxyAddress, EIP1967_IMPLEMENTATION_SLOT);
    if (!raw || raw === "0x") return null;
    return ethers.getAddress("0x" + raw.slice(-40)); // 마지막 20바이트
  } catch (e) {
    return null;
  }
}

// 2. ABI fetch
// async function fetchAbiFromEtherscan(address: string): Promise<any | null> {
//   try {
//     const url = `https://api.etherscan.io/api?module=contract&action=getabi&address=${address}&apikey=${process.env.ETHERSCAN_API_KEY}`;
//     const res = await axios.get(url);

//     if (res.data.status !== "1") return null;
//     return JSON.parse(res.data.result);
//   } catch {
//     return null;
//   }
// }

function loadSolcVersion(version: string): Promise<typeof solc> {
  return new Promise((resolve, reject) => {
    solc.loadRemoteVersion(version, (err: Error | null, solcSnapshot: typeof solc | undefined) => {
      if (err || !solcSnapshot) reject(err || new Error("Failed to load solc"));
      else resolve(solcSnapshot);
    });
  });
}

const abiCache: Record<string, any[]> = {};

export async function fetchAbiFromEtherscan(address: string): Promise<any[] | null> {
  if (abiCache[address]) {
    console.log(`Using cached ABI for ${address}`);
    return abiCache[address];
  }

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
        abiCache[address] = abis; // 캐시에 저장
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

// 3. 통합 ABI 가져오기 함수
export async function getAbiWithProxySupport(
  address: string,
  provider: ethers.Provider
): Promise<any | null> {
  const addrLower = address.toLowerCase();
  const abiPath = path.join(ABI_CACHE_DIR, `${addrLower}.json`);

  // 1. 캐시 확인
  if (fs.existsSync(abiPath)) {
    return JSON.parse(fs.readFileSync(abiPath, "utf-8"));
  }

  // 2. Etherscan fetch
  const abi = await fetchAbiFromEtherscan(addrLower);
  if (abi) {
    fs.writeFileSync(abiPath, JSON.stringify(abi, null, 2));
    return abi;
  }

  // 3. Proxy 확인
  const implAddress = await getImplementationAddress(addrLower, provider);
  if (implAddress) {
    console.log(`Proxy detected → Implementation: ${implAddress}`);

    const implAbi = await fetchAbiFromEtherscan(implAddress);
    if (implAbi) {
      fs.writeFileSync(abiPath, JSON.stringify(implAbi, null, 2)); // 캐시에는 원래 주소로 저장
      return implAbi;
    }
  }

  // 4. 실패
  return null;
}
