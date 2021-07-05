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
import bitcoinlib
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
        #in reality just the hash of the current time + random number
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

        #Time since escrow was last interacted with.
        #This is used to detect abandoned escrows.
        self.lasttime = int(time.time())


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
            k = bitcoinlib.keys.Key(network='litecoin')
            self.privkey = k.wif()


    def pay (self, addr: str, feerate: int = 0 ) -> str :
        """
        Send the funds to addr with a given feerate
        """
        if (feerate == 0) :
            feerate = bit.network.get_fee(fast=False)
        self.lasttime = int(time.time())
        try :
            txid = ""
            if (self.coin == 'btc') :
                if (config.testnet) :
                    k = bit.PrivateKeyTestnet(self.privkey)
                else :
                    k = bit.Key(self.privkey)
                if (feerate == 0) :
                    txid = k.send([(addr, float(self.value - Decimal(config.escrowfee['btc']) - Decimal(feerate * .00000227)), 'btc')], leftover=config.leftover['btc'])
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
                while (True) :
                    k = bitcoinlib.keys.Key(self.privkey, network='litecoin')
                    s = bitcoinlib.services.services.Service(network='litecoin')
                    uxtos = s.getutxos(address=k.address())
                    val = bitcoinlib.values.Value(str(self.value - Decimal(config.escrowfee['ltc']) - Decimal(.000008)) + " LTC")
                    targetout = bitcoinlib.transactions.Output(network='litecoin', value=val, address=addr)
                    feeout = bitcoinlib.transactions.Output(value=bitcoinlib.values.Value(str(config.escrowfee['ltc']) + " LTC"), network='litecoin', address=config.leftover['ltc'])
                    tx = bitcoinlib.transactions.Transaction(outputs=[targetout, feeout], network='litecoin', fee=800)
                    if (len(uxtos) == 0) :
                        continue
                    for i in uxtos :
                        tx.add_input(i['txid'], i['output_n'])
                    tx.sign(keys=k)
                    txid = tx.txhash
                    tx.verify()
                    s.sendrawtransaction(tx.raw_hex())
                    break
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
            r.redditor(self.recipient).message("Funds available", str(self.value) + " " + self.coin.upper() + " was released to you from the escrow with ID " + self.id + " You may withdraw the funds using `!withdraw [address]`." +
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
        self.lasttime = int(time.time())
        self.__notifyavailable(True)

    def release (self) :
        """
        Mark the escrow as released. The recipient will be able to withdraw their funds.config
        """
        self.lasttime = int(time.time())
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
            k = bitcoinlib.keys.Key(self.privkey, network='litecoin').address()
        r.redditor(self.sender).message("Escrow funding address", "In order to fund the escrow with ID " + self.id + ", please send " + str(self.value) + " " + self.coin.upper() +
                                        " to " + k + config.signature)
        self.lasttime = int(time.time())
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
            k = bitcoinlib.keys.Key(self.privkey, network='litecoin')
            if (Decimal(bitcoinlib.services.services.Service('litecoin').getbalance(k.address_obj.address)) / Decimal(100000000) < self.value) :
                return False
            else :
                txs = bitcoinlib.services.services.Service('litecoin').gettransactions(bitcoinlib.keys.Key(self.privkey, network='litecoin').address())
                for tx in txs :
                    if (tx.confirmations == 0) :
                        return False
                return True

        
        lk = k.get_balance()
        if (Decimal(k.get_balance()) / Decimal('100000000') < self.value) :
            return False
        #not sure why but it otherwise sometimes will think an unconfirmed tx
        #is confirmed and say the escrow is funded when it's really not
        if (len(k.get_unspents()) == 0) :
            return False
        for i in k.get_unspents() :
            if (i.confirmations == 0) :
                return False
        return True

