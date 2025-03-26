import axios from "axios";
import * as fs from "fs";
import * as path from "path";
import { ethers } from "ethers";
import { config } from "dotenv";
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
    console.log(raw);
    if (!raw || raw === "0x") return null;
    return ethers.getAddress("0x" + raw.slice(-40)); // 마지막 20바이트
  } catch (e) {
    return null;
  }
}

// 2. ABI fetch
async function fetchAbiFromEtherscan(address: string): Promise<any | null> {
  try {
    const url = `https://api.etherscan.io/api?module=contract&action=getabi&address=${address}&apikey=${process.env.ETHERSCAN_API_KEY}`;
    const res = await axios.get(url);

    if (res.data.status !== "1") return null;
    return JSON.parse(res.data.result);
  } catch {
    return null;
  }
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
