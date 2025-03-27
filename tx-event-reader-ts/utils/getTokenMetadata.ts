import { ethers } from "ethers";

const metadataCache: Record<string, { symbol: string; decimals: number }> = {};
const UNDERLYING_MAPPING: Record<string, string> = {
  // Compound cTokens (mainnet)
  "0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5": "ETH", // cETH
  "0xC11b1268C1A384e55C48c2391d8d480264A3A7F4": "WBTC", // cWBTC
  "0x39AA39c021dfbaE8faC545936693aC917d5E7563": "USDC", // cUSDC
  // 추가 가능
};

export async function getTokenMetadata(address: string, provider: ethers.Provider) {
  const addr = address.toLowerCase();

  // 특수 주소 대응
  if (addr === "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee") {
    return { symbol: "ETH", decimals: 18 };
  }

  if (metadataCache[addr]) return metadataCache[addr];

  const ERC20_ABI = [
    "function symbol() view returns (string)",
    "function decimals() view returns (uint8)",
  ];

  try {
    const contract = new ethers.Contract(address, ERC20_ABI, provider);
    const [symbol, decimals] = await Promise.all([
      contract.symbol(),
      contract.decimals(),
    ]);
    metadataCache[addr] = { symbol, decimals };
    return { symbol, decimals };
  } catch {
    metadataCache[addr] = { symbol: "?", decimals: 18 };
    return { symbol: "?", decimals: 18 };
  }
}

export async function getDisplayMetadata(
  fieldName: string,
  contractAddress: string,
  fallbackSymbol: string,
  fallbackDecimals: number
): Promise<{ symbol: string; decimals: number }> {
  const key = contractAddress.toLowerCase();
  const isCToken = fallbackSymbol.startsWith("c") && fallbackDecimals === 8;

  const field = fieldName.toLowerCase();

  // cToken에서 underlying 관련 필드는 18자리로 강제 처리
  if (isCToken && (field.includes("mintamount") || field.includes("borrowamount") || field.includes("redeemamount") || field.includes("repayamount"))) {
    return { symbol: fallbackSymbol.replace(/^c/, ""), decimals: 18 };
  }

  return { symbol: fallbackSymbol, decimals: fallbackDecimals };
}
