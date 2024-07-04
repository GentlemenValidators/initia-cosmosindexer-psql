import json
import psycopg2
import time

from chain_types import Block, Tx
from util import txraw_to_hash

class Database:
    def __init__(self, dbname, user, password, host, port):
        self.conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        self.cur = self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def create_tables(self):
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS blocks (height SERIAL PRIMARY KEY, time TEXT, txs TEXT)"""
        )
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS txs (id SERIAL PRIMARY KEY, height INTEGER, tx_amino TEXT, msg_types TEXT, tx_json TEXT, address TEXT, tx_hash TEXT)"""
        )
        self.commit()

    def optimize_tables(self):
        self.cur.execute(
            """CREATE INDEX IF NOT EXISTS blocks_height ON blocks (height)"""
        )
        self.cur.execute(
            """CREATE INDEX IF NOT EXISTS txs_data_index ON txs (id, height, address, tx_hash)"""
        )
        self.commit()

    def get_indexes(self):
        self.cur.execute("""SELECT indexname FROM pg_indexes WHERE schemaname = 'public';""")
        return self.cur.fetchall()

    def get_all_tables(self):
        self.cur.execute("""SELECT tablename FROM pg_tables WHERE schemaname = 'public';""")
        return self.cur.fetchall()

    def get_table_schema(self, table: str):
        self.cur.execute(f"""SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';""")
        return self.cur.fetchall()

    def insert_block(self, height: int, time: str, txs_ids: list[int]):
        self.cur.execute(
            """INSERT INTO blocks (height, time, txs) VALUES (%s, %s, %s)""",
            (height, time, json.dumps(txs_ids)),
        )

    def get_block(self, block_height: int) -> Block | None:
        self.cur.execute(
            """SELECT * FROM blocks WHERE height=%s""",
            (block_height,),
        )
        data = self.cur.fetchone()
        if data is None:
            return None
        return Block(data[0], data[1], json.loads(data[2]))

    def get_earliest_block(self) -> Block | None:
        self.cur.execute("""SELECT * FROM blocks ORDER BY height ASC LIMIT 1""")
        data = self.cur.fetchone()
        if data is None:
            return None
        return Block(data[0], data[1], json.loads(data[2]))

    def get_latest_saved_block(self) -> Block | None:
        self.cur.execute("""SELECT * FROM blocks ORDER BY height DESC LIMIT 1""")
        data = self.cur.fetchone()
        if data is None:
            return None
        return Block(data[0], data[1], json.loads(data[2]))

    def get_total_blocks(self) -> int:
        self.cur.execute("""SELECT COUNT(*) FROM blocks""")
        data = self.cur.fetchone()
        if data is None:
            return 0
        return data[0]

    def get_missing_blocks(self, start_height, end_height) -> list[int]:
        self.cur.execute(
            """SELECT height FROM blocks WHERE height BETWEEN %s AND %s""",
            (start_height, end_height),
        )
        data = self.cur.fetchall()
        if data is None:
            return list(range(start_height, end_height + 1))
        found_heights = set(x[0] for x in data)
        missing_heights = [
            height
            for height in range(start_height, end_height + 1)
            if height not in found_heights
        ]
        return missing_heights

    def insert_tx(self, height: int, tx_amino: str):
        tx_hash = txraw_to_hash(tx_amino)
        self.cur.execute(
            """INSERT INTO txs (height, tx_amino, msg_types, tx_json, address, tx_hash) VALUES (%s, %s, %s, %s, %s, %s)""",
            (height, tx_amino, "", "", "", tx_hash),
        )
        return self.cur.lastrowid

    def update_tx(self, _id: int, tx_json: str, msg_types: str, address: str):
        self.cur.execute(
            """UPDATE txs SET tx_json=%s, msg_types=%s, address=%s WHERE id=%s""",
            (tx_json, msg_types, address, _id),
        )

    def update_tx_hash(self, _id: int, tx_hash: str):
        self.cur.execute(
            """UPDATE txs SET tx_hash=%s WHERE id=%s""",
            (tx_hash, _id),
        )

    def get_tx_by_hash(self, tx_hash: str) -> Tx | None:
        self.cur.execute(
            """SELECT id FROM txs WHERE tx_hash=%s""",
            (tx_hash,),
        )
        data = self.cur.fetchone()
        if data is None:
            return None
        return self.get_tx(data[0])

    def get_tx(self, tx_id: int) -> Tx | None:
        self.cur.execute(
            """SELECT * FROM txs WHERE id=%s""",
            (tx_id,),
        )
        data = self.cur.fetchone()
        if data is None:
            return None
        return Tx(data[0], data[1], data[2], data[3], data[4], data[5], data[6] or "")

    def get_tx_specific(self, tx_id: int, fields: list[str]):
        self.cur.execute(
            f"""SELECT {','.join(fields)} FROM txs WHERE id=%s""",
            (tx_id,),
        )
        data = self.cur.fetchone()
        if data is None:
            return None
        tx = {fields[i]: data[i] for i in range(len(fields))}
        for tx_type in Tx.__annotations__.keys():
            if tx_type not in tx:
                tx[tx_type] = ""
        return Tx(**tx)

    def get_txs_from_address_in_range(self, address: str) -> list[dict]:
        txs = []
        self.cur.execute(
            """SELECT height, tx_json FROM txs WHERE address=%s""",
            (address,),
        )
        data = self.cur.fetchall()
        if data is None:
            return txs
        for tx in data:
            txs.append({"height": tx[0], "tx_json": tx[1]})
        return txs

    def get_txs_by_ids(self, tx_lower_id: int, tx_upper_id: int) -> list[Tx]:
        txs = []
        if tx_lower_id == tx_upper_id or tx_lower_id > tx_upper_id:
            return txs
        self.cur.execute(
            """SELECT * FROM txs WHERE id BETWEEN %s AND %s""",
            (tx_lower_id, tx_upper_id),
        )
        data = self.cur.fetchall()
        if data is None:
            return txs
        for tx in data:
            txs.append(Tx(tx[0], tx[1], tx[2], tx[3], tx[4], tx[5], tx[6] or ""))
        return txs

    def get_last_saved_tx(self) -> Tx | None:
        self.cur.execute("""SELECT id FROM txs ORDER BY id DESC LIMIT 1""")
        data = self.cur.fetchone()
        if data is None:
            return None
        return self.get_tx(data[0])

    def get_txs_in_range(self, start_height: int, end_height: int) -> list[Tx]:
        tx_ids = {}
        for block_index in range(start_height, end_height + 1):
            b = self.get_block(block_index)
            if b:
                for tx_id in b.tx_ids:
                    tx_ids[tx_id] = True
        txs = []
        for tx_id in tx_ids:
            _tx = self.get_tx(tx_id)
            if _tx:
                txs.append(_tx)
        return txs

    def get_non_decoded_txs_in_range(self, start_height: int, end_height: int) -> list[Tx]:
        self.cur.execute(
            """SELECT * FROM txs WHERE height BETWEEN %s AND %s""",
            (start_height, end_height),
        )
        data = self.cur.fetchall()
        if data is None:
            return []
        txs = []
        for x in data:
            if len(x[4]) == 0:
                txs.append(Tx(x[0], x[1], x[2], x[3], x[4], x[5], x[6]))
        return txs
