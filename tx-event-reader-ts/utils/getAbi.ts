import axios from "axios";
import * as fs from "fs";
import * as path from "path";
import { config } from "dotenv";
config();

const ABI_CACHE_DIR = path.join(__dirname, "../abis");
if (!fs.existsSync(ABI_CACHE_DIR)) fs.mkdirSync(ABI_CACHE_DIR, { recursive: true });

export async function getAbi(address: string): Promise<any | null> {
  const checksummed = address.toLowerCase();
  const abiPath = path.join(ABI_CACHE_DIR, `${checksummed}.json`);

  if (fs.existsSync(abiPath)) {
    return JSON.parse(fs.readFileSync(abiPath, "utf-8"));
  }

  try {
    const url = `https://api.etherscan.io/api?module=contract&action=getabi&address=${checksummed}&apikey=${process.env.ETHERSCAN_API_KEY}`;
    const res = await axios.get(url);

    if (res.data.status !== "1") {
      console.warn(`ABI not found for ${address}`);
      return null;
    }

    const abi = JSON.parse(res.data.result);
    fs.writeFileSync(abiPath, JSON.stringify(abi, null, 2));
    return abi;
  } catch (err) {
    console.error(`⚠️ Failed to fetch ABI for ${address}:`, err instanceof Error ? err.message : String(err));
    return null;
  }
}
