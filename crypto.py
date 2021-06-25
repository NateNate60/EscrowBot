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

class UnsupportedCoin (Exception) :
    """
    Class for an unsupported coin
    """
    pass

#Class representing an escrow transaction
class Escrow :
    def __init__(self, coin: str) -> None:
        #escrow id
        #in reality just the hash of the current time
        h = hashlib.sha1()
        h.update((str(time.time()) + str(random.random())).encode('utf-8'))
        self.id = "c4cid" + h.hexdigest()

        #state of the escrow. 0 = waiting approval, 1 = waiting deposit, 2 = funded & held, 3 = released, 4 = complete, -1 = refunded
        self.state = 0
        
        #which coin the escrow is holding (ex. "btc")
        if (coin not in config.coins) :
            raise UnsupportedCoin
        else :
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
            k = bitcash.Key()
            self.privkey = k.to_wif()
        elif (self.coin == 'ltc') :
            if (not config.testnet) :
                k = lit.Key()
                self.privkey = k.to_wif()
            else :
                k = lit.PrivateKeyTestnet()
                self.privkey = k.to_wif()


    def pay (self, addr: str, feerate: int = 0 ) -> str :
        """
        Send the funds to addr with a given feerate
        """
        try :
            txid = ""
            if (self.coin == 'btc') :
                if (config.testnet) :
                    k = bit.PrivateKeyTestnet(self.privkey)
                else :
                    k = bit.Key(self.privkey)
                if (feerate == 0) :
                    txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['btc']) - Decimal(bit.network.get_fee(fast=False) * 227. / 100000000.)), 'btc')], leftover=config.leftover['btc'])
                else :
                    txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['btc']) - Decimal(feerate * .00000227)), 'btc')], leftover=config.leftover['btc'], fee=feerate)
            elif (self.coin == 'bch') :
                k = bitcash.Key(self.privkey)
                k.get_unspents()
                #for somereason the library detects when the address is missing the prefix but does not autocorrect for it
                if ("bitcoincash:" not in addr) :
                    addr = "bitcoincash:" + addr
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['bch']) - Decimal(.000008)), 'bch')], leftover=config.leftover['bch'], fee=1)
            elif (self.coin == 'ltc') :
                k = lit.Key(self.privkey)
                txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['ltc']) - Decimal(800.)), 'ltc')], leftover=config.leftover['ltc'], fee=1)
            return txid
        except ValueError :
            return None

    def __notifyavailable (self, sender: bool = False) :
        """
        Notify the user of the availability of funds. sender is whether the funds are released to the sender, defaulting to False,
        which releases to recipient
        """
        if (sender) :
            r.redditor(self.sender).message("Funds available", str(self.value) + " " + self.coin.upper() + " was released to you from the escrow with ID " + self.id + " You may withdraw the funds using `!withdraw [address]`." +
                                            " If you wish to specify a custom feerate, you may do so by using `!withdraw [escrow ID] [address] [feerate]`.\n\n" +
                                            "    ESCROW VALUE: " + str(self.value) + " " + self.coin.upper() + '\n' +
                                            "    ESCROW FEE: " + str(Decimal(config.escrowfee[self.coin])) + " " + self.coin.upper() + '\n' +
                                            "    TOTAL AVAILABLE (before network fees): " + str(self.value - Decimal(config.escrowfee[self.coin])) +
                                            "    RECOMMENDED BTC NETWORK FEE: " + str(bit.network.get_fee(fast=False)) +
                                            " sat/B\n\nNote: You don't have to specify a BTC network feerate. If you don't, then the recommended feerate at the time of withdrawal," +
                                            " which may be different than it is now, will be used. BCH and LTC transactions always use 1 sat/B." + config.signature)
        else :
            r.redditor(self.recipient).message("Funds available", str(self.value) + " " + self.coin.upper() + " was released to you. You may withdraw the funds using `!withdraw [address]`." +
                                               " If you wish to specify a custom feerate, you may do so by using `!withdraw [escrow ID] [address] [feerate]`.\n\n" +
                                               "    ESCROW VALUE: " + str(self.value) + " " + self.coin.upper() + '\n' +
                                               "    ESCROW FEE: " + str(Decimal(config.escrowfee[self.coin])) + " " + self.coin.upper() + '\n' +
                                               "    TOTAL AVAILABLE (before network fees): " + str(self.value - Decimal(config.escrowfee[self.coin])) +
                                               "    RECOMMENDED BTC NETWORK FEE: " + str(bit.network.get_fee(fast=False)) +
                                               " sat/B\n\nNote: You don't have to specify a BTC network feerate. If you don't, then the recommended feerate at the time of withdrawal," +
                                               " which may be different than it is now, will be used. BCH and LTC transactions always use 1 sat/B." + config.signature)
    
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
        self.state = 3
        self.__notifyavailable()

    def askpayment (self) :
        """
        Ask the sender to fund the escrow
        """
        k = None
        if (self.coin == "btc") :
            if (config.testnet) :
                k = bit.PrivateKeyTestnet(self.privkey).segwit_address
            else :
                k = bit.Key(self.privkey).segwit_address
        elif (self.coin == "bch") :
            k = bitcash.Key(self.privkey).address
        elif (self.coin == "ltc") :
            if (config.testnet) :
                k = lit.PrivateKeyTestnet(self.privkey).address
            else :
                k = lit.Key(self.privkey).address
        r.redditor(self.sender).message("Escrow funding address", "In order to fund the escrow with ID " + self.id + ", please send " + str(self.value) + " " + self.coin.upper() +
                                        " to " + k + config.signature)
    def funded (self) :
        """
        Returns whether the escrow is funded
        """
        k = None
        if (self.coin == "btc") :
            if (config.testnet) :
                k = bit.PrivateKeyTestnet(self.privkey)
            else :
                k = bit.Key(self.privkey)
        elif (self.coin == "bch") :
            k = bitcash.Key(self.privkey)
        elif (self.coin == "ltc") :
            if (config.testnet) :
                k = lit.PrivateKeyTestnet(self.privkey)
            else :
                k = lit.Key(self.privkey)
        
        lk = k.get_balance()
        if (Decimal(k.get_balance()) / Decimal('100000000') < self.value) :
            return False
        for i in k.get_unspents() :
            if (i.confirmations == 0) :
                return False
        return True

