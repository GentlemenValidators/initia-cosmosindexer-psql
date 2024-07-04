import asyncio
import json
import os
import random
import sys
import time
import traceback
import uuid

import httpx

from chain_types import BlockData, DecodeGroup
from SQL import Database
from util import command_exists, get_latest_chain_height, get_sender, run_decode_file

current_dir = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(current_dir, "chain_config.json"), "r") as f:
    chain_config = dict(json.load(f))

TASK = chain_config.get("TASK", "no_impl").lower()
all_tasks = ["missing", "download", "sync", "decode"]
if TASK not in all_tasks:
    print(f"TASK is not in the allowed group {', '.join(all_tasks)}")
    exit(1)

if len(sys.argv) < 2:
    print(f"Please specify a section: ({', '.join(chain_config.get('sections', {}).keys())}) for mode {TASK}")
    exit(1)

chain_section_key = sys.argv[1]

COSMOS_PROTO_DECODER_BINARY_FILE = chain_config.get("COSMOS_PROTO_DECODE_BINARY", "juno-decode")
DECODE_LIMIT = chain_config.get("COSMOS_PROTO_DECODE_LIMIT", 10_000)
COSMOS_PROTO_DECODE_BLOCK_LIMIT = chain_config.get("COSMOS_PROTO_DECODE_BLOCK_LIMIT", 10_000)
if not command_exists(COSMOS_PROTO_DECODER_BINARY_FILE):
    print(f"Command {COSMOS_PROTO_DECODER_BINARY_FILE} not found")
    exit(1)

TX_AMINO_LENGTH_CUTTOFF_LIMIT = chain_config.get("TX_AMINO_LENGTH_CUTTOFF_LIMIT", 0)

WALLET_PREFIX = chain_config.get("WALLET_PREFIX", "juno1")
VALOPER_PREFIX = chain_config.get("VALOPER_PREFIX", "junovaloper1")

specific_section = chain_config.get("sections", {}).get(chain_section_key, {})
if specific_section == {}:
    print(f"Chain section {chain_section_key} not found")
    exit(1)

START_BLOCK = specific_section.get("start", -1)
END_BLOCK = specific_section.get("end", -1)
GROUPING = specific_section.get("grouping", 10_000)
if START_BLOCK < 0 or END_BLOCK < 0:
    print("START_BLOCK or END_BLOCK is not set correctly")
    exit(1)
RPC_ARCHIVE_LINKS = specific_section.get("rpc_endpoints", [])
if len(RPC_ARCHIVE_LINKS) == 0:
    print(f"RPC_ARCHIVE_LINKS is empty")
    exit(1)

tmp_decode_dir = os.path.join(current_dir, "tmp_decode")
os.makedirs(tmp_decode_dir, exist_ok=True)

built_in_print = print

def print(*args, **kwargs):
    built_in_print(f"(thread:#{chain_section_key})", *args, **kwargs)

print(f"Starting {TASK} task")

db: Database

async def download_block(client: httpx.AsyncClient, height: int) -> BlockData | None:
    if db.get_block(height) is not None:
        if height % (GROUPING * 5) == 0:
            print(f"Block {height} is already saved.")
        return None

    RPC_ARCHIVE_URL = random.choice(RPC_ARCHIVE_LINKS)
    REAL_URL = f"{RPC_ARCHIVE_URL}/block?height={height}"
    r = await client.get(REAL_URL, timeout=30)
    if r.status_code != 200:
        print(f"Error: {r.status_code} @ height {height}")
        with open(os.path.join(current_dir, f"errors.txt"), "a") as f:
            f.write(f"Height: {height};{r.status_code} @ {RPC_ARCHIVE_URL} @ {time.time()};{r.text}\n\n")
        return None

    block_time = ""
    encoded_block_txs = []
    try:
        v = r.json()["result"]["block"]
        block_time = v["header"]["time"]
        encoded_block_txs = v["data"]["txs"]
    except KeyError:
        return None

    amino_txs = []
    if TX_AMINO_LENGTH_CUTTOFF_LIMIT <= 0:
        amino_txs = encoded_block_txs
    else:
        for x in encoded_block_txs:
            if len(x) <= TX_AMINO_LENGTH_CUTTOFF_LIMIT:
                amino_txs.append(x)

    return BlockData(height, block_time, amino_txs)

async def do_mass_url_download_and_decode(block_range: list[int] | range, httpx_client):
    if isinstance(block_range, range):
        block_range = list(block_range)

    tasks = {}
    start_time = time.time()
    for block in block_range:
        if block > END_BLOCK:
            break

        if block != 0:
            tasks[block] = asyncio.create_task(download_block(httpx_client, block))

    try:
        values = await asyncio.gather(*tasks.values())
        if not all(x is None for x in values):
            save_values_to_sql(values)
            print(f"Finished #{len(block_range)} blocks in {round(time.time() - start_time, 4)} seconds ({block_range[0]}->{block_range[-1]})")
    except Exception as e:
        print(f"Error: main(): {e}")
        traceback.print_exc()

async def main():
    global START_BLOCK, END_BLOCK

    while True:
        last_saved_block = db.get_latest_saved_block()
        latest_saved_height = 0
        if last_saved_block is not None:
            latest_saved_height = last_saved_block.height

        current_chain_height = get_latest_chain_height(RPC_ARCHIVE=RPC_ARCHIVE_LINKS[0])
        print(f"Last saved: {latest_saved_height:,} & Chain height: {current_chain_height:,}")

        if END_BLOCK > current_chain_height:
            END_BLOCK = current_chain_height

        if TASK == "sync":
            START_BLOCK = latest_saved_height
            END_BLOCK = current_chain_height

        GROUP_END_BLOCK = END_BLOCK - (END_BLOCK % GROUPING)
        print(f"Bulk Blocks: {START_BLOCK:,}->{END_BLOCK:,}")

        async with httpx.AsyncClient() as httpx_client:
            if END_BLOCK - START_BLOCK <= GROUPING:
                await do_mass_url_download_and_decode(range(START_BLOCK, current_chain_height + 1), httpx_client)
            else:
                num_groups = (GROUP_END_BLOCK - START_BLOCK) // GROUPING + 1
                for i in range(num_groups):
                    block_heights = [bh for bh in range(START_BLOCK + i * GROUPING, START_BLOCK + (i + 1) * GROUPING)]
                    await do_mass_url_download_and_decode(block_heights, httpx_client)

                remainder_blocks = range(GROUP_END_BLOCK, END_BLOCK + 1)
                if remainder_blocks:
                    await do_mass_url_download_and_decode(remainder_blocks, httpx_client)

        print("Sleeping for more blocks.")
        time.sleep(10)

def decode_and_save_updated(to_decode: list[dict]):
    global db

    start_time = time.time()

    _rand = str(uuid.uuid4())
    DUMPFILE = os.path.join(tmp_decode_dir, f"in-{_rand}.json")
    OUTFILE = os.path.join(tmp_decode_dir, f"out-{_rand}.json")

    with open(DUMPFILE, "w") as f:
        json.dump(to_decode, f)

    values = run_decode_file(COSMOS_PROTO_DECODER_BINARY_FILE, DUMPFILE, OUTFILE)

    for data in values:
        tx_id = data["id"]
        tx_data = json.loads(data["tx"])

        tx = db.get_tx(tx_id)
        if tx is None:
            continue

        height = tx.height

        sender = get_sender(height, tx_data["body"]["messages"][0], "juno", "junovaloper")
        if sender is None:
            print("No sender found for tx: ", tx_id, "at height: ", height)
            sender = "UNKNOWN"

        msg_types = {}
        for msg in tx_data["body"]["messages"]:
            _type = msg["@type"]
            if _type not in msg_types:
                msg_types[_type] = 0
            msg_types[_type] += 1

        msg_types_list = list(msg_types.keys())
        msg_types_list.sort()

        for i in range(60):
            try:
                db.update_tx(tx_id, json.dumps(tx_data), json.dumps(msg_types_list), sender)
                break
            except Exception as e:
                random_sleep = random.random() + 0.5
                print(f"[!] Error: decode_and_save_updated(): {e}. Waiting {random_sleep} seconds to try again")
                time.sleep(random_sleep)
                continue

    db.commit()

    if TASK == "decode":
        print(f"Time: Decoded & stored ({len(to_decode)} Txs): {time.time() - start_time}")

    os.remove(DUMPFILE)
    os.remove(OUTFILE)

def do_decode(lowest_height: int, highest_height: int):
    global db

    groups = []
    if highest_height - lowest_height <= COSMOS_PROTO_DECODE_BLOCK_LIMIT:
        groups.append(DecodeGroup(lowest_height - 1, highest_height))
        print(f"Group: {lowest_height-1}->{highest_height}")
    else:
        for i in range(((highest_height - lowest_height) // COSMOS_PROTO_DECODE_BLOCK_LIMIT + 1) - 1):
            groups.append(DecodeGroup(lowest_height + i * COSMOS_PROTO_DECODE_BLOCK_LIMIT, lowest_height + (i + 1) * COSMOS_PROTO_DECODE_BLOCK_LIMIT))

        if len(groups) > 0 and groups[-1].end < highest_height:
            groups.append(DecodeGroup(groups[-1].end, highest_height))

    print(f"Groups: {len(groups):,}")
    print(f"Total Blocks: {highest_height - lowest_height:,}")

    latest_block = db.get_latest_saved_block()
    if latest_block is None:
        print("No latest block found. Cannot decode. Exiting.")
        exit(1)

    for group in groups:
        start_height = group.start
        end_height = group.end
        print(f"Decoding Group: {start_height:,}->{end_height:,} ({(end_height - start_height):,} blocks)")

        txs = db.get_non_decoded_txs_in_range(start_height, end_height)
        print(f"Total non decoded Txs in Blocks: {start_height:,}->{end_height:,}: Txs #:{len(txs):,}")

        to_decode = []
        for tx in txs:
            if len(tx.tx_json) == 0:
                to_decode.append({"id": tx.id, "tx": tx.tx_amino})

            if len(to_decode) >= DECODE_LIMIT:
                decode_and_save_updated(to_decode)
                to_decode.clear()

        if len(to_decode) > 0:
            decode_and_save_updated(to_decode)
            to_decode.clear()

def save_values_to_sql(values: list[BlockData]):
    global db

    for bd in values:
        if bd is None:
            continue

        height = bd.height
        block_time = bd.block_time
        amino_txs = bd.encoded_txs

        sql_tx_ids = []
        for amino_tx in amino_txs:
            unique_id = db.insert_tx(height, amino_tx)
            sql_tx_ids.append(unique_id)

        db.insert_block(height, block_time, sql_tx_ids)

    db.commit()

    if TASK == "sync":
        heights = [v.height for v in values if v is not None]
        if not heights:
            print("Error: no heights found in range")
            return

        lowest_height = min(heights)
        latest_height = max(heights)

        do_decode(lowest_height, latest_height)

if __name__ == "__main__":
    db = Database(db="your_db_name", user="your_username", password="your_password", host="your_host", port="your_port")
    db.create_tables()
    db.optimize_tables()
    db.optimize_db(vacuum=False)

    if TASK == "decode":
        print(f"Doing a decode of all Txs in the range {START_BLOCK} - {END_BLOCK}")
        do_decode(START_BLOCK, END_BLOCK)
        exit(1)

    elif TASK == "missing":
        earliest_block = BlockData(START_BLOCK, "", [])
        latest_saved_block = BlockData(END_BLOCK, "", [])
        if earliest_block is None or latest_saved_block is None:
            print("No blocks downloaded yet")
            exit(1)

        print(f"Searching through blocks: {earliest_block.height:,} - {latest_saved_block.height:,}")

        print("Waiting on missing blocks query...")
        missing_blocks = db.get_missing_blocks(earliest_block.height, latest_saved_block.height)
        if missing_blocks:
            missing_blocks.sort()
            with open(os.path.join(current_dir, "missing_blocks.json"), "w") as f:
                json.dump(missing_blocks, f)
        else:
            print("No missing blocks in this range")

        print("Waiting on non decoded txs in range query...")
        failed_to_decode_txs = db.get_non_decoded_txs_in_range(earliest_block.height, latest_saved_block.height)
        if len(failed_to_decode_txs) > 0:
            print("Missing txs (ones which are failed to be decoded)...")
            heights = sorted(set(tx.height for tx in failed_to_decode_txs))
            tx_ids = sorted(set(tx.id for tx in failed_to_decode_txs))
            with open(os.path.join(current_dir, "missing_txs.json"), "w") as f:
                json.dump({"heights": heights, "tx_ids": tx_ids}, f)
        else:
            print("No missing decoded txs")

        exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
    loop.close()
