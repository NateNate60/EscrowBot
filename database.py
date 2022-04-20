"""
This file contains the framework for interacting with
the database of escrows
"""

import sqlite3
import crypto
import config
from time import time
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
                    " privkey TEXT NOT NULL," +
                    " time INTEGER NOT NULL"
                    ");")
            self.db.commit()

    def lookup (self, id: str) -> crypto.Escrow :
        """
        Look up a given escrow transaction by ID
        Returns the escrow object, or None if the escrow ID does not exist
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id=?;", (id,))
        rows = cursor.fetchall()
        if (len(rows) == 0) :
            return None
        return self._decode(rows[0])

    def add (self, escrow: crypto.Escrow) :
        """
        Add an escrow transaction to the database
        Overwrite existing records
        """
        if (escrow == None) :
            return
        if (escrow.coin == "eth") :
            escrow.value = escrow.value.quantize(Decimal("0.00001")).normalize()
        elif (escrow.coin == "usdt") :
            escrow.value = escrow.value.quantize(Decimal("0.01")).normalize()
        else :
            escrow.value = escrow.value.quantize(Decimal("0.00000001")).normalize()
        print ("adding", escrow.id)
        self.db.execute("DELETE FROM transactions WHERE id=?;", (escrow.id,))
        self.db.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (escrow.id, escrow.sender, escrow.recipient, escrow.state, escrow.coin, str(escrow.value), escrow.contract, escrow.privkey, int(time())))
        self.db.commit()
    
    def bump (self, id: str) :
        """
        Increase the state of an escrow transaction by 1
        """
        self.db.execute("UPDATE transactions SET state = state + 1 WHERE id=?;", (id,))
        self.db.commit()
    
    def read (self) -> list :
        """
        Read all active escrows that must be monitored for payment
        """
        cursor = self.db.execute("SELECT * FROM transactions WHERE state=1;")
        element = cursor.fetchall()
        lis = []
        for i in element :
            if (i[3] == 1) :
                lis.append(self._decode(i))
        return lis

    def detectduplicate (self, amount: Decimal, coin: str) -> bool :
        """
        Detect whether an open escrow already exists for the amount and coin specified
        This is because for account-based coins, we can only have one open escrow transaction at a time for any given amount
        Completed or failed transactions are ignored.
        """
        cursor = self.db.execute("SELECT * FROM transactions WHERE value = ? AND coin = ? AND state = 1", (str(amount), coin,))
        element = cursor.fetchall()
        return len(element) > 0

    def latest (self) -> list :
        """
        Returns a list of all Escrow objects with a lasttime within the past 30 days
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM transactions WHERE time > ?;", (int(time()) - 2592000,))
        rows = cursor.fetchall()
        l = []
        for i in rows :
            l.append(self._decode(i))
        l.reverse()
        return l

    def _decode (*args) -> crypto.Escrow :
        """
        Decode a tuple that represents the data fetched by SQLite
        from a row 
        """
        e = args[1]
        if (len(e) == 0) :
            return None
        escrow = crypto.Escrow(e[4])
        escrow.id = e[0]
        escrow.sender = e[1]
        escrow.recipient = e[2]
        escrow.state = e[3]
        escrow.value = Decimal(e[5])
        escrow.contract = e[6]
        escrow.privkey = e[7]
        escrow.lasttime = e[8]
        return escrow


def monitorpayment (r, elist: list, db: Database) -> list :
    """
    Monitor a list of escrows for payment.
    If payment is detected, the transaction is marked paid, parties notified, and
    the transaction is removed from the monitor list
    Returns the new monitor list

    NOTE: If an escrow goes 24 hours without payment, it will be considered "abandoned"
    and will be dropped from the list.
    """
    relist = []
    for tx in elist :
        #If more than 24h without payment, it's abandoned.
        if (int(time()) - tx.lasttime > 86400) :
            r.redditor(tx.sender).message("Escrow funding failed", "Payment to fund the escrow with ID " + tx.id + " has failed or was not confirmed by the network" +
                                          " within 24 hours. This escrow transaction is now closed. You can start a new transaction " + 
                                          "[here](https://reddit.com/message/compose?to=C4C_Bot&subject=Escrow&message=--NEW%20TRANSACTION--%0APartner:%20yourtradepartnersusername%0AAmount:%200.12345%20BTC/BCH%0A--CONTRACT--%0AWrite%20whatever%20you%20want%20here.%20What%20are%20the%20parties%20agreeing%20to%3F%0AAbout%20this%20service:%20https://www.reddit.com/r/Cash4Cash/wiki/edit/index/escrow)." + 
                                          " If you did send payment and the transaction has not confirmed for some reason, please contact the moderators of r/Cash4Cash." + 
                                          config.signature())
            r.redditor(tx.recipient).message("Escrow funding failed", "The sender for the escrow with ID " + tx.id + " did not make payment " +
                                             "within 24 hours or their payment did not confirm in time. The transaction has been cancelled. "+
                                             "If they did send payment, but it was not detected, please contact the mods of r/Cash4Cash." +
                                             config.signature())
            tx.state = -9
            db.add(tx)
            continue
        if tx.funded() :
            tx.state = 2
            r.redditor(tx.sender).message("Escrow fully funded", "The escrow with ID " + tx.id + " has been fully funded. They money is locked in the escrow until you release the escrow. The recipient has been informed to complete the service " +
                                          "or send the goods as agreed. When and only when you are satisfied that the other party has kept their end of the bargain, reply with " +
                                          "`!release`.\n\n**Do not release the escrow early under any circumstances.** Anyone who directs you to release the escrow before "+
                                          "they complete their end of the bargain is a scammer. If you release the escrow, the funds will be immediately made available to the other party for withdrawal." +
                                          " If you encounter any issues or have a dispute, please report the problem to the r/Cash4Cash moderators." + config.signature(True))
            r.redditor(tx.recipient).message("Escrow fully funded", "The escrow with ID " + tx.id + " has been fully funded. The money has been received and is locked until the sender releases the escrow. Please provide the goods or services as agreed. If you wish " +
                                             "to issue a refund to the sender, reply with `!refund " + tx.id +"`. If you refund the escrow. the money will immediately be made available to the other "+ 
                                             "party for withdrawal. If you encounter any issues or have a dispute, please report the problem to the r/Cash4Cash moderators." + config.signature(True))
            db.add(tx)
        else :
            relist.append(tx)
    return relist
