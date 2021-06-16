"""
This file contains the framework for interacting with the cryptocurrency wallets.
"""

import bit
import bitcash
import hashlib
import time
import random
import config
import web3
import lit
import praw
from decimal import Decimal

w3 = web3.Web3(web3.Web3.HTTPProvider('https://kovan.infura.io/v3/79f3325b70d147d0beda556e812b41d4'))
r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")



#Class representing an escrow transaction
class Escrow :
    def __init__(self, coin: str) -> None:
        #escrow id
        #in reality just the hash of the current time
        h = hashlib.sha1()
        h.update((str(time.time()) + str(random.random())).encode('utf-8'))
        self.id = "c4cid" + h.hexdigest()

        #state of the escrow. 0 = waiting approval, 1 = waiting deposit, 2 = funded & held, 3 = released, -1 = refunded
        self.state = 0
        
        #which coin the escrow is holding (ex. "btc")
        self.coin = coin

        #sender's username (ex. "NateNate60")
        self.sender = ""

        #recipient's username (ex. "NateNate60")
        self.recipient = ""

        #the contract between the parties
        self.contract = ""

        #value of the escrow in crypto (ex. 0.0001)
        self.value = Decimal(0.)

        #the WIF private key for the address holding the escrowed funds
        self.privkey = None
        if (self.coin == 'btc') :
            if (not config.testnet) :
                k = bit.Key()
                self.privkey = k.to_wif()
            else :
                k = bit.PrivateKeyTestnet()
                self.privkey = k.to_wif()
        elif (self.coin == 'bch') :
            if (not config.testnet) :
                k = bitcash.Key()
                self.privkey = h.to_wif()
            else :
                k = bitcash.PrivateKeyTestnet()
                self.privkey = k.to_wif()
        elif (self.coin == 'ltc') :
            if (not config.testnet) :
                k = lit.Key()
                self.privkey = k.to_wif()
            else :
                k = lit.PrivateKeyTestnet()
                self.privkey = k.to_wif()


    def pay (self, addr: str, feerate: int = 0, ) :
        """
        Send the funds to addr with a given feerate
        """
        txid = ""
        if (self.coin == 'btc') :
            k = bit.Key(self.privkey)
            if (feerate == 0) :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['btc'])), 'btc')], leftover=config.leftover['btc'])
            else :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['btc'])), 'btc')], leftover=config.leftover['btc'], fee=feerate)
        elif (self.coin == 'bch') :
            k = bitcash.Key(self.privkey)
            if (feerate == 0) :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['bch'])), 'bch')], leftover=config.leftover['bch'])
            else :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['bch'])), 'bch')], leftover=config.leftover['bch'], fee=feerate)
        elif (self.coin == 'ltc') :
            k = lit.Key(self.privkey)
            if (feerate == 0) :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['ltc'])), 'ltc')], leftover=config.leftover['ltc'])
            else :
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['ltc'])), 'ltc')], leftover=config.leftover['ltc'], fee=feerate)
        return txid

    def __notifyavailable (self, sender: bool = False) :
        """
        Notify the user of the availability of funds. sender is whether the funds are released to the sender, defaulting to False,
        which releases to recipient
        """
        if (sender) :
            r.redditor(self.sender).message("Funds available", str(self.value) + " " + self.coin.upper() + " was released to you. You may withdraw the funds using `!withdraw [address]`." +
                                            " If you wish to specify a custom feerate, you may do so by using `!withdraw [address] [feerate]`.\n\n" +
                                            "    ESCROW VALUE: " + str(self.value) + " " + self.coin.upper() + '\n' +
                                            "    ESCROW FEE: " + str(Decimal(config.escrowfeee[self.coin])) + " " + self.coin.upper() + '\n' +
                                            "    TOTAL AVAILABLE (before network fees): " + str(self.value - Decimal(config.escrowfee['ltc'])))
        else :
            r.redditor(self.recipient).message("Funds available", str(self.value) + " " + self.coin.upper() + " was released to you. You may withdraw the funds using `!withdraw [address]`." +
                                            " If you wish to specify a custom feerate, you may do so by using `!withdraw [address] [feerate]`.\n\n" +
                                            "    ESCROW VALUE: " + str(self.value) + " " + self.coin.upper() + '\n' +
                                            "    ESCROW FEE: " + str(Decimal(config.escrowfeee[self.coin])) + " " + self.coin.upper() + '\n' +
                                            "    TOTAL AVAILABLE (before network fees): " + str(self.value - Decimal(config.escrowfee['ltc'])))
    
    def refund (self) :
        """
        Mark the escrow as refunded. The sender will be able to withdraw their funds.
        """
        self.state = -1
        self.__notifyavailable(True)

    def release (self) :
        """
        Mark the escrow as released. The recipient will be able to withdraw their funds.config
        """
        self.state = 2
        self.__notifyavailable()

    def askpayment(self) :
        """
        Ask the sender to fund the escrow
        """
        if (self.coin == "btc") :
            k = None
            if (config.testnet) :
                k = bit.PrivateKeyTestnet(self.privkey)
            else (config.testnet)
                k.address