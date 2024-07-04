# reads the SQLite file and shows you how to perform actions

import json
import os

from chain_types import Tx
from SQL import Database

current_dir = os.path.dirname(os.path.realpath(__file__))

def main():
    db = Database(db="your_db_name", user="your_username", password="your_password", host="your_host", port="your_port")

    total = db.get_total_blocks()
    earliest_block = db.get_earliest_block()
    latest_block = db.get_latest_saved_block()

    print(f"Total Blocks: {total}")
    print(f"Earliest Block: {earliest_block.height}")
    print(f"Latest Block Height: {latest_block.height}")

    missing = db.get_missing_blocks(earliest_block.height, latest_block.height)
    print(f"Missing Blocks total: {missing}")
    exit(1)

if __name__ == "__main__":
    main()
