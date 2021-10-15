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
from etherscan import Etherscan
from decimal import Decimal


# Global variable section (loud booing in background)
etherscan = Etherscan(config.etherscankey, net="main")
w3 = web3.Web3(web3.Web3.HTTPProvider(config.infuraurl))
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
        h = hashlib.sha256()
        h.update((str(time.time()) + str(random.random())).encode('utf-8'))
        self.id = "c4cid" + h.hexdigest()[:16]

        #state of the escrow. 0 = waiting approval, 1 = waiting deposit, 2 = funded & held, 3 = released, 4 = complete, -1 = refunded
        self.state = 0
        
        #which coin the escrow is holding (ex. "btc")
        coin = coin[:3]
        if (coin not in config.coins) :
            raise UnsupportedCoin
        else :
            if (coin == "dog") : #doge is 4 letters
                coin = "doge"
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
        elif (self.coin == 'doge') :
            k = bitcoinlib.keys.Key(network='dogecoin')
            self.privkey = k.wif()
        elif (self.coin == "eth") :
            #Since ETH is not uxto-based, self.privkey instead stores a random 3-digit identifier.
            self.privkey = '000'
            while (self.privkey == '000') : #identifier should not be 000
                self.privkey = str(int(random.random() * 1000))


    def pay (self, addr: str, feerate: int = 0 ) -> str :
        """
        Send the funds to addr with a given feerate
        """
        if (feerate == 0) :
            fee = bitcoinlib.services.services.Service(network="bitcoin")
            feerate = fee.estimatefee(2) // 1000
        self.lasttime = int(time.time())
        try :
            txid = ""
            if (self.coin == 'btc') :
                if (config.testnet) :
                    k = bit.PrivateKeyTestnet(self.privkey)
                else :
                    k = bit.Key(self.privkey)
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
                    tx.verify()
                    d = s.sendrawtransaction(tx.raw_hex())
                    txid = d['txid']
                    break
            elif (self.coin == "eth") :
                txs = etherscan.get_normal_txs_by_address(config.ethaddr, 0, 9999999999, "asc")
                nonce = 0
                for tx in txs :
                    if (tx['from'] == config.ethaddr.lower()) :
                        nonce += 1
                transaction = {'to': addr,
                               "value": int(self.value * Decimal('1000000000000000000') - (Decimal('21000') * Decimal(etherscan.get_gas_oracle()['ProposeGasPrice']) * Decimal(1000000000) ) - (Decimal(config.escrowfee["eth"]) * Decimal(1000000000000000000))),
                               "gas": 21000,
                               'gasPrice': int(Decimal(etherscan.get_gas_oracle()['ProposeGasPrice']) * Decimal(1000000000)),
                               'nonce': nonce,
                               'from': config.ethaddr
                               }
                signed = w3.eth.account.sign_transaction(transaction, config.ethpriv)
                txid = w3.eth.send_raw_transaction(signed.rawTransaction).hex()
            elif (self.coin == 'doge') :
                while (True) :
                    k = bitcoinlib.keys.Key(self.privkey, network='dogecoin')
                    s = bitcoinlib.services.services.Service(network='dogecoin')
                    uxtos = s.getutxos(address=k.address())
                    val = bitcoinlib.values.Value(str(self.value - Decimal(config.escrowfee['doge']) - Decimal(1)) + " DOGE")
                    targetout = bitcoinlib.transactions.Output(network='dogecoin', value=val, address=addr)
                    feeout = bitcoinlib.transactions.Output(value=bitcoinlib.values.Value(str(config.escrowfee['doge']) + " DOGE"), network='dogecoin', address=config.leftover['doge'])
                    tx = bitcoinlib.transactions.Transaction(outputs=[targetout, feeout], network='dogecoin', fee=100000000)
                    if (len(uxtos) == 0) :
                        continue
                    for i in uxtos :
                        tx.add_input(i['txid'], i['output_n'])
                    tx.sign(keys=k)
                    tx.verify()
                    d = s.sendrawtransaction(tx.raw_hex())
                    txid = d['txid']
                    break
            return txid
        except (ValueError, TypeError) :
            return None

    def __notifyavailable (self, sender: bool = False) :
        """
        Notify the user of the availability of funds. sender is whether the funds are released to the sender, defaulting to False,
        which releases to recipient
        """
        fee = "1"
        if (self.coin == 'btc') :
            fee = bitcoinlib.services.services.Service(network="bitcoin")
            fee = str(fee.estimatefee(2) // 1000)
        elif (self.coin == 'eth') :
            fee = etherscan.get_gas_oracle()['ProposeGasPrice']
        
        message = (str(self.value) + " " + self.coin.upper() + " was released to you from the escrow with ID " + self.id + " You may withdraw the funds using `!withdraw [address]`." +
                  " If you wish to specify a custom feerate, you may do so by using `!withdraw [escrow ID] [address] [feerate]`.\n\n" +
                  "    ESCROW VALUE: " + str(self.value) + " " + self.coin.upper() + '\n' +
                  "    ESCROW FEE: " + str(Decimal(config.escrowfee[self.coin])) + " " + self.coin.upper() + '\n' +
                  "    TOTAL AVAILABLE (before network fees): " + str(self.value - Decimal(config.escrowfee[self.coin])) + '\n\n' +
                  "    RECOMMENDED NETWORK FEE: " + fee)
        if (self.coin in ['btc', 'ltc', 'bch']) :
            message += " sat/B\n\nNote: You don't have to use the suggested network fee on BTC. You can specify however high (or low) of a fee as you want."
            message += " However, if you choose not to specify a feerate, the suggested feerate will be used, which may be different at the time of withdrawal than it is now."
        elif (self.coin == "eth") :
            message += " gw/gas\n\nNote: Custom feerates are currently not supported on ETH. The suggested feerate will always be used. This is because the ETH network requires transactions be confirmed in order."
        message += config.signature
        if (sender) :
            r.redditor(self.sender).message("Funds available", message)
        else :
            r.redditor(self.recipient).message("Funds available", message)


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
        elif (self.coin == "doge") :
            k = bitcoinlib.keys.Key(self.privkey, network='dogecoin').address()
        #ETH is handled differently because it requires an identifier
        if (self.coin == "eth") :
            r.redditor(self.sender).message("Escrow funding address", "In order to fund the escrow with ID " + self.id + 
                                            ", please send " + str(self.value) + self.privkey + " " + self.coin.upper() +
                                            " to " + config.ethaddr + ".\n\n**IMPORTANT**: You must send _exactly_ this amount, after fees. If too little or too much is received," +
                                            " your payment will not be detected. If you accidentally sent the wrong amount, please reach out to us for help!" + config.signature)
            self.lasttime = int(time.time())
            return
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
        elif (self.coin == "doge") :
            k = bitcoinlib.keys.Key(self.privkey, network='dogecoin')
            if (Decimal(bitcoinlib.services.services.Service('dogecoin').getbalance(k.address_obj.address)) / Decimal(100000000) < self.value) :
                return False
            else :
                txs = bitcoinlib.services.services.Service('dogecoin').gettransactions(bitcoinlib.keys.Key(self.privkey, network='dogecoin').address())
                for tx in txs :
                    if (tx.confirmations == 0) :
                        return False
                return True
        elif (self.coin == "eth") :
            txs = etherscan.get_normal_txs_by_address(config.ethaddr, 0, 9999999999, "dec")
            for tx in txs :
                if (int(tx['confirmations']) < 6) :
                    continue
                precision = Decimal('0.00000001')
                value = Decimal(tx['value']) / Decimal(1000000000000000000)
                value = value.quantize(precision)
                value = str(value)
                if (value[7:] != self.privkey) :
                    continue #identifier does not match
                #else, identifier matches (NOTE: This doesn't mean that the transaction is for this particular escrow!)
                if (Decimal(value[:7]) == self.value) :
                    return True
            return False


        
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

