import { ethers } from "ethers";
import { config } from "dotenv";
import axios from "axios"; // 웹에 HTTP 요청 보내는 라이브러리

config(); // .env 파일에서 ALCHEMY_API_KEY, ETHERSCAN_API_KEY 로드

// provider : 이더리움 네트워크에 연결하는 객체
const provider = new ethers.AlchemyProvider(
    "mainnet",
    process.env.ALCHEMY_API_KEY
);

// 추출하고자 하는 트랜잭션 해시
const txHash = "0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838"; // bzx 공격 트랜잭션

// receipt : 트랜잭션 실행 결과 (event logs 포함)
async function getTxReceipt(txHash: string) {
    const receipt = await provider.getTransactionReceipt(txHash);
    return receipt;
}

// 주소가 EOA인지 CA인지 확인
async function isContract(address: string): Promise<boolean> {
    const code = await provider.getCode(address);
    return code !== "0x";
}

// 주소의 ABI 가져오기
async function getAbiFromEtherscan(address: string) {
    const url = `https://api.etherscan.io/api?module=contract&action=getabi&address=${address}&apikey=${process.env.ETHERSCAN_API_KEY}`;
    const response = await axios.get(url);
    if (response.data.status !== "1") {
        throw new Error("Failed to fetch ABI from Etherscan");
    }
    return JSON.parse(response.data.result);
}

// 토큰의 소수점 자리수 가져오기
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
        return 18; // 디코딩 실패시 기본값 18 반환(ETH)
    }
}

// ENS 이름 해석
async function resolveENS(address: string): Promise<string> {
    try {
        const name = await provider.lookupAddress(address);
        return name ?? address;
    } catch {
        return address;
    }
}

// event logs 디코딩 및 출력
async function decodeEventLogs(log: ethers.Log, abi: any[]) {
    try {
        const iface = new ethers.Interface(abi);
        const parsed = iface.parseLog(log);
        if (!parsed) {
            console.log("Failed to decode event log");
            return;
        }

        const paramOutputs: string[] = [];

        for (const [key, value] of Object.entries(parsed.args)) {
            if (isNaN(Number(key))) {
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
        }

        console.log(`${parsed.name}(${paramOutputs.join(", ")})`);

    } catch (e) {
        console.error("Failed to decode event log:", (e as Error).message);
    }
}

// 메인 함수
async function main() {
    const receipt = await getTxReceipt(txHash);

    if (!receipt) {
        console.log("Transaction not found");
        return;
    }

    console.log("Transaction successful. Start decoding event logs...\n");

    for (const [i, log] of receipt.logs.entries()) {
        console.log(`Event log ${i + 1}:`);
        console.log("Address:", log.address);
        console.log("Topics:", log.topics);
        console.log("Data:", log.data);
        console.log("--------------------------------");

        const isCA = await isContract(log.address);
        if (isCA) {
            try {
                const abi = await getAbiFromEtherscan(log.address);
                await decodeEventLogs(log, abi);
            } catch (e) {
                console.warn("⚠️ ABI fetch or decode failed:", (e as Error).message);
            }
        } else {
            console.log("This is an EOA address. No ABI needed.");
        }
    }
}

main().catch(console.error);
