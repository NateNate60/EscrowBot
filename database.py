"""
This file contains the framework for interacting with
the database of escrows
"""

import sqlite3
import crypto
from decimal import Decimal

class Database :
    def __init__ (self) :
        self.db = sqlite3.connect("database.sqlite3")
        with self.db :
            self.db.execute("CREATE TABLE IF NOT EXISTS transactions " +
                    "(id TEXT NOT NULL PRIMARY KEY, " +
                    " sender TEXT NOT NULL," +
                    " recipient TEXT NOT NULL," +
                    " state INTEGER NOT NULL," +
                    " coin TEXT NOT NULL," +
                    " value TEXT NOT NULL," +
                    " contract TEXT," +
                    " privkey TEXT NOT NULL"
                    ")")
            self.db.commit()

    def lookup (self, id: str) -> crypto.Escrow :
        """
        Look up a given escrow transaction by ID
        Returns the escrow object, or None if the escrow ID does not exist
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id=?", (id,))
        rows = cursor.fetchall()
        if (len(rows) == 0) :
            return None
        escrow = crypto.Escrow(rows[0][4])
        escrow.id = rows[0][0]
        escrow.sender = rows[0][1]
        escrow.recipient = rows[0][2]
        escrow.state = rows[0][3]
        escrow.value = Decimal(rows[0][5])
        escrow.contract = rows[0][6]
        escrow.privkey = rows[0][7]
        return escrow

    def add (self, escrow: crypto.Escrow) :
        """
        Add an escrow transaction to the database
        Overwrite existing records
        """
        self.db.execute("DELETE FROM transactions WHERE id=?", (escrow.id,))
        self.db.execute("INSERT INTO transactions VALUES (" + escrow.id + "," + escrow.sender + "," + escrow.recipient + "," + escrow.state + "," + escrow.coin + "," + str(escrow.value) + "," + escrow.contract + "," + escrow.privkey + ")")
        self.db.commit()
    
    def bump (self, id: str) :
        """
        Increase the state of an escrow transaction by 1
        """
        self.db.execute("UPDATE transactions SET state = state + 1 WHERE id=?", (id,))
        self.db.commit()


def monitorpayment (r, elist: list, db: Database) -> list :
    """
    Monitor a list of escrows for payment.
    If payment is detected, the transaction is marked paid, parties notified, and
    the transaction is removed from the monitor list
    Returns the new monitor list
    """
    relist = []
    for tx in elist :
        if tx.funded() :
            tx.state = 2
            r.redditor(tx.sender).message("Escrow fully funded", "The escrow with ID " + tx.id + " has been fully funded. The recipient has been informed to complete the service " +
                                          "or send the goods as agreed. When and only when you are satisfied that the other party has kept their end of the bargain, reply with " +
                                          "`!release " + tx.id + "`.\n\n**Do not release the escrow early under any circumstances.** Anyone who directs you to release the escrow before "+
                                          "they complete their end of the bargain is a scammer. If you release the escrow, the funds will be immediately made available to the other party for withdrawal." +
                                          " If you encounter any issues or have a dispute, please report the problem to the r/Cash4Cash moderators." + config.signature)
            r.redditor(tx.recipient).message("Escrow fully funded", "The escrow with ID " + tx.id + " has been fully funded. Please provide the goods or services as agreed. If you wish " +
                                             "to issue a refund to the sender, reply with `!refund " + tx.id +"`. If you refund the escrow. the money will immediately be made available to the other "+ 
                                             "party for withdrawl. If you encounter any issues or have a dispute, please report the problem to the r/Cash4Cash moderators." + config.signature)
            db.add(tx)
        else :
            relist.append(tx)
    return relist