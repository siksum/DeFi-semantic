import { ethers } from "ethers";
import { config } from "dotenv";

config(); // .env 파일에서 ALCHEMY_API_KEY 로드

// provider : 이더리움 네트워크에 연결하는 객체
const provider = new ethers.AlchemyProvider(
    "mainnet",
    process.env.ALCHEMY_API_KEY!
);

// 추출하고자 하는 트랜잭션 해시
const txHash = "0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838"; // bzx 공격 트랜잭션

async function main(){
    // receipt : 트랜잭션 실행 결과 (event logs 포함)
    const receipt = await provider.getTransactionReceipt(txHash);

    if(!receipt){
        console.log("Transaction not found");
        return;
    }

    console.log("Transaction successful");
    
    // event logs 추출
    for (const [i, log] of receipt.logs.entries()){
        console.log(`Event log ${i+1}:`);
        console.log("Address:", log.address);
        console.log("Topics:", log.topics);
        console.log("Data:", log.data);
        console.log("--------------------------------");
    }    
}

main().catch(console.error);