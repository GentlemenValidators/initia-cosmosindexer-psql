import asyncio
import json
import os
import sys

import httpx
from _types import Contract

current_dir = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current_dir)
sys.path.append(parent)

from SQL import Database

# PostgreSQL connection parameters
DB_PARAMS = {
    'dbname': 'your_db_name',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'your_host',
    'port': 'your_port'
}

db = Database(**DB_PARAMS)
latest_block = db.get_latest_saved_block()
if latest_block is None:
    print("No blocks found in db")
    exit(1)

# Block Range
START_BLOCK = 1
END_BLOCK = latest_block.height

print(f"Getting all transactions in range of blocks: {START_BLOCK} to {END_BLOCK}")
all_txs = db.get_txs_in_range(START_BLOCK, END_BLOCK)
print(f"Total Txs found: {len(all_txs):,}")

async def get_label(client: httpx.AsyncClient, contract_addr: str) -> Contract:
    for i in range(2):
        try:
            resp = await client.get(f"{REST_API}/cosmwasm/wasm/v1/contract/{contract_addr}")
            if resp.status_code == 200:
                return Contract(contract_addr, resp.json()["contract_info"]["label"])
            else:
                return Contract(contract_addr, "")
        except Exception as e:
            await asyncio.sleep(1)
    return Contract(contract_addr, "")

print("Getting all MsgExecuteContract's")
contracts = {}
for tx in all_txs:
    if "MsgExecuteContract" not in tx.msg_types:
        continue

    _json = json.loads(tx.tx_json)
    for msg in _json["body"]["messages"]:
        if msg["@type"] == "/cosmwasm.wasm.v1.MsgExecuteContract":
            c_addr = msg["contract"]
            if c_addr not in contracts:
                contracts[c_addr] = 0
            contracts[c_addr] += 1

contracts = {k: v for k, v in contracts.items() if v >= INTERACTION_CUTOFF}
print(f"Total contracts (after removing <{INTERACTION_CUTOFF} interactions): {len(contracts):,}")

async def main():
    labels = {}
    tasks = {}
    print("Getting labels requests")
    async with httpx.AsyncClient() as client:
        for c_addr in contracts:
            tasks[c_addr] = get_label(client, c_addr)

        res = await asyncio.gather(*tasks.values())
        for r in res:
            labels[r.contract_addr] = r.label

        with open("contract_labels.json", "w") as f:
            json.dump(
                {
                    "start_block": START_BLOCK,
                    "end_block": END_BLOCK,
                    "interaction_cutoff": INTERACTION_CUTOFF,
                    "labels": labels,
                },
                f,
                indent=2,
            )

asyncio.run(main())
