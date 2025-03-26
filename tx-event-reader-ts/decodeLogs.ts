import * as fs from "fs";
import * as path from "path";
import { ethers } from "ethers";

// 타입스크립트 타입 무시하고 CommonJS 방식으로 로딩
// @ts-ignore
const abiGuesser = require("@openchainxyz/abi-guesser");

async function main() {
    const logsPath = path.join(__dirname, "logs/0xb5c8bd9430b6cc87a0e2fe110ece6bf527fa4f170a4bc8cd032f768fc5219838.json");
    const raw = fs.readFileSync(logsPath, "utf-8");
    const logs = JSON.parse(raw);

    for (const [i, log] of logs.entries()) {
        console.log(`\n🔍 Decoding log ${i + 1}`);
        console.log(`Address: ${log.address}`);
        console.log(`Topics: ${log.topics}`);
        console.log(`Data: ${log.data}`);

        try {
            const result = await abiGuesser.decodeLog({
                address: log.address,
                topics: log.topics,
                data: log.data,
            });

            if (result) {
                console.log("✅ Event:", result.signature);
                console.log("📦 Args:", result.args);
            } else {
                console.log("⚠️ Could not decode this log.");
            }
        } catch (err) {
            console.error("❌ Error decoding log:", err);
        }
    }
}

main().catch(console.error);
