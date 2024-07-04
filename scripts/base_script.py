import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

# Used to import DBInformation into other scripts.

current_dir = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current_dir)
sys.path.append(parent)

from SQL import Block, Database, Tx

# PostgreSQL connection parameters
DB_PARAMS = {
    'dbname': 'your_db_name',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'your_host',
    'port': 'your_port'
}

db = Database(**DB_PARAMS)
if db is None:
    print("No db found")
    exit(1)

earliest_block = db.get_earliest_block()
if earliest_block is None:
    print("No blocks found in db")
    exit(1)

latest_block = db.get_latest_saved_block()
if latest_block is None:
    print("No blocks found in db")
    exit(1)

last_tx_saved = db.get_last_saved_tx()
if last_tx_saved is None:
    print("No txs found in db")
    exit(1)

@dataclass
class DBInformation:
    current_dir: str = current_dir
    parent: str = parent
    database: Database = db
    earliest_block: Optional[Block] = earliest_block
    latest_block: Optional[Block] = latest_block
    last_tx_saved: Optional[Tx] = last_tx_saved
