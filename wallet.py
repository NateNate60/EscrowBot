"""
This file contains the framework for interacting with the cryptocurrency wallets.
"""

import bit
import bitcash
import hashlib
import time
import random
from decimal import Decimal

#Class representing an escrow transaction
class Escrow :
    def __init__(self, id) -> None:
        #escrow id
        #in reality just the hash of the current time
        h = hashlib.sha1()
        h.update((str(time.time()) + str(random.random())).encode('utf-8'))
        self.id = h.hexdigest()

        
        #which coin the escrow is holding (ex. "btc")
        self.coin = ""

        #sender's username (ex. "NateNate60")
        self.sender = ""

        #sender's crypto address
        self.senderaddr = ""

        #recipient's username (ex. "NateNate60")
        self.recipient = ""

        #recipient's crypto address
        self.recipientaddr = ""

        #value of the escrow in crypto (ex. 0.0001)
        self.value = ""

        #whether or not the escrow is considered funded
        self.funded = False

        #the WIF private key for the address holding the escrowed funds
        self.privkey = ""

    def release (self, amount: str = "") :
        """
        Release the escrow to the recipient. amount is the amount to release, defaulting to the entire value.
        If the escrow is partially released, the value is reduced accordingly
        """
        if (Decimal(amount) > Decimal(self.value)) :
            return 1
        else :
            self.value = str(Decimal(self.value) - Decimal(amount))
        

    
    def refund (amount: str = "") :
        """
        Refund the money held in escrow to the sender. amount is the amount to release, defautling to the entire value.
        If the escrow is partially refunded, the value is reduced accordingly
        """
        pass