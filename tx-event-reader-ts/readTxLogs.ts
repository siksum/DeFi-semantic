import { ethers } from "ethers";
import { config } from "dotenv";
import axios from "axios";
import fs from "fs";

config();

const provider = new ethers.AlchemyProvider("mainnet", process.env.ALCHEMY_API_KEY);
const txHash = "0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838";

const failedLogs: { address: string; topic: string; reason: string }[] = [];

async function getTxReceipt(txHash: string) {
    const receipt = await provider.getTransactionReceipt(txHash);
    return receipt;
}

async function isContract(address: string): Promise<boolean> {
    const code = await provider.getCode(address);
    return code !== "0x";
}

async function getAbiFromEtherscan(address: string) {
    const url = `https://api.etherscan.io/api?module=contract&action=getabi&address=${address}&apikey=${process.env.ETHERSCAN_API_KEY}`;
    const response = await axios.get(url);
    if (response.data.status !== "1") {
        throw new Error("Failed to fetch ABI from Etherscan");
    }
    return JSON.parse(response.data.result);
}

async function getTokenDecimals(address: string): Promise<number> {
    try {
        const tokenContract = new ethers.Contract(
            address,
            ["function decimals() view returns (uint8)"],
            provider
        );
        const decimals = await tokenContract.decimals();
        return decimals;
    } catch (error) {
        console.warn("Failed to get token decimals:", (error as Error).message);
        return 18;
    }
}

async function resolveENS(address: string): Promise<string> {
    try {
        const name = await provider.lookupAddress(address);
        return name ?? address;
    } catch {
        return address;
    }
}

function getEventSignatureName(topic0: string): string {
    const knownEvents: Record<string, string> = {
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "Transfer",
        "0xd78ad95fa46c994b6551d0da85fc275fe613f1d2c12e5df1f3d6f03d34647ec5": "Swap",
        "0x8c5be1e5ebec7d5bd14f714f4f8b6f01a34dd6e54f3efccb9f2b7dd0b8b8c6c0": "Approval"
    };
    return knownEvents[topic0.toLowerCase()] ?? "UnknownEvent";
}

async function decodeEventLogs(log: ethers.Log, abi: any[]) {
    try {
        const iface = new ethers.Interface(abi);
        const parsed = iface.parseLog(log);
        if (!parsed) {
            console.warn("Failed to decode event log");
            return;
        }
        console.log(parsed);    
        const paramOutputs: string[] = [];

        for (const [key, value] of Object.entries(parsed.args)) {
            // 🔁 숫자 키는 건너뛰고, 문자 키만 출력!
            if (!isNaN(Number(key))) continue;
          
            let displayValue: string;
          
            if (typeof value === 'bigint') {
              const decimals = await getTokenDecimals(log.address);
              displayValue = ethers.formatUnits(value, decimals);
            } else if (ethers.isAddress(value.toString())) {
              const ensName = await resolveENS(value.toString());
              displayValue = ensName;
            } else {
              displayValue = value.toString();
            }
          
            paramOutputs.push(`${key}: ${displayValue}`);
          }

        console.log(`✅ ${parsed.name}(${paramOutputs.join(", ")})`);

    } catch (e) {
        const topic0 = log.topics[0] ?? "";
        const reason = (e as Error).message;
        failedLogs.push({ address: log.address, topic: topic0, reason });
        console.warn(`❌ Failed to decode log for ${log.address} | topic0: ${topic0} | reason: ${reason}`);
        const knownName = getEventSignatureName(topic0);
        if (knownName !== "UnknownEvent") {
            console.log(`📌 Likely event: ${knownName}`);
        }
    }
}

async function main() {
    const receipt = await getTxReceipt(txHash);

    if (!receipt) {
        console.log("Transaction not found");
        return;
    }

    console.log("Transaction successful. Start decoding event logs...\n");

    for (const [i, log] of receipt.logs.entries()) {
        console.log(`Event log ${i + 1}:`);
        // console.log("Address:", log.address);
        // console.log("Topics:", log.topics);
        // console.log("Data:", log.data);
        // console.log("--------------------------------");

        const isCA = await isContract(log.address);
        if (isCA) {
            try {
                const abi = await getAbiFromEtherscan(log.address);
                await decodeEventLogs(log, abi);
            } catch (e) {
                const topic0 = log.topics[0] ?? "";
                const reason = (e as Error).message;
                failedLogs.push({ address: log.address, topic: topic0, reason });
                console.warn("⚠️ ABI fetch or decode failed:", reason);
            }
        } else {
            console.log("This is an EOA address. No ABI needed.");
        }
    }

    if (failedLogs.length > 0) {
        fs.writeFileSync("failed_logs.json", JSON.stringify(failedLogs, null, 2));
        console.log("\n❗ Some logs failed to decode. See failed_logs.json for details.");
    }
}

main().catch(console.error);
