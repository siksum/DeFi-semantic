import { ethers } from "ethers";
import axios from "axios";
import { config } from "dotenv";
config();

const EIP1967_SLOT =
  "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";

export type ContractClassification = {
  address: string;
  type: "EOA" | "CA";
  isProxy: boolean;
  implementation?: string;
};

export async function classifyAddress(
  address: string,
  provider: ethers.Provider
): Promise<ContractClassification> {
  const code = await provider.getCode(address);

  // 1. EOA
  if (code === "0x") {
    return {
      address,
      type: "EOA",
      isProxy: false,
    };
  }

  // 3. Fallback: Etherscan getsourcecode
  try {
    const res = await axios.get(`https://api.etherscan.io/api?module=contract&action=getsourcecode&address=${address}&apikey=${process.env.ETHERSCAN_API_KEY}`);
    const result = res.data?.result?.[0];

    if (result?.Proxy === "1" && result?.Implementation && ethers.isAddress(result?.Implementation)) {
      return {
        address,
        type: "CA",
        isProxy: true,
        implementation: ethers.getAddress(result?.Implementation),
      };
    }
  } catch {}

  // 4. 일반 CA
  return {
    address,
    type: "CA",
    isProxy: false,
  };
}
