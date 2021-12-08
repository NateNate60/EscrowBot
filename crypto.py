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
import requests
import tronpy
import json

# Global variable section (loud booing in background)
etherscan = Etherscan(config.etherscankey, net="main")
w3 = web3.Web3(web3.Web3.HTTPProvider(config.infuraurl))
r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")
client = tronpy.Tron()

class UnsupportedCoin (Exception) :
    """
    Class for an unsupported coin
    """
    pass

def estimatefee () -> int :
    """
    Fetches the current recommended BTC feerate (sat/B) from mempool.space
    """
    return requests.get("https://mempool.space/api/v1/fees/recommended/").json()['fastestFee']

def readclaimed () -> list :
    """
    Reads a list of claimed txids from file. Returns list of str
    """
    with open ("claimed.json", 'r') as f :
        return json.load(f)

def writeclaimed (txids: list) -> None :
    """
    Writes a list of claimed txids to the claimed.json file
    """
    with open ("claimed.json", 'w') as f :
        json.dump(txids, f)

def tronstake () -> None :
    """
    Checks the TRON wallet for any unstaked TRX and stakes it for 3 days to get energy.
    This function will leave 30 TRX unstaked in order to cover network fees if the 
    energy/bandwidth from staking doesn't cover it.

    There is only a 1% chance this function will actually do anything at all.
    This is to deal with the API limits.
    """
    if (random.random() < 0.99) :
        return
    bal = client.get_account(config.tronaddr)['balance']
    if (bal > 31000000) :
        #does not attempt to stake if it would stake less than 1 TRX
        client.trx.freeze_balance(config.tronaddr, bal - 30000000, "ENERGY").build().sign(tronpy.keys.PrivateKey(bytes.fromhex(config.tronpriv))).broadcast()

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
        if (coin == "dog") : #doge is 4 letters
            coin = "doge"
        if (coin == "usd") : #usdt is 4 letters
            coin = "usdt"
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
        elif (self.coin == 'doge') :
            k = bitcoinlib.keys.Key(network='dogecoin')
            self.privkey = k.wif()
        elif (self.coin == "eth") :
            #Since ETH is not uxto-based, self.privkey instead stores a random 3-digit identifier.
            self.privkey = '000'
            while (self.privkey == '000') : #identifier should not be 000
                self.privkey = str(int(random.random() * 1000))
        elif (self.coin == "usdt") :
            self.privkey = "000"
            pass #Privkey not needed for USDT TRC-20


    def pay (self, addr: str, feerate: int = 0 ) -> str :
        """
        Send the funds to addr with a given feerate
        """
        if ("[" in addr) : #correct users accidentally providing address in brackets
            addr = addr[1:-1]
        if (feerate == 0) :
            feerate = estimatefee()
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
            elif (self.coin == 'usdt') :
                if (not client.is_base58check_address(addr)) :
                    raise ValueError #address provided is invalid
                contract = client.get_contract("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t") #fetch USDT TRC-20 contract. Hard-coded contract address.
                privkey = tronpy.keys.PrivateKey((bytes.fromhex(config.tronpriv)))
                tx = (contract.functions.transfer(addr, int(self.value * Decimal(1000000))).with_owner(config.tronaddr).fee_limit(5000000).build().sign(privkey))
                txid = tx.txid
                tx.broadcast()
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
            fee = str(estimatefee())
        elif (self.coin == 'eth') :
            fee = etherscan.get_gas_oracle()['ProposeGasPrice']
        elif (self.coin == "usdt") :
            fee = "0.00"
        
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
        elif (self.coin == "usdt") :
            message += " USDT\n\n Note: The escrow fee also covers the network fee."
        message += config.signature()
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
                                            " to " + config.ethaddr + ".\n\n**IMPORTANT**: You must send _exactly_ this amount, after network fees. If too little or too much is received," +
                                            " your payment will not be detected. If you accidentally sent the wrong amount, please reach out to us for help!" + config.signature())
            self.lasttime = int(time.time())
            return
        elif (self.coin == "usdt") :
            r.redditor(self.sender).message("Escrow funding address", "In order to fund the escrow with ID " + self.id + 
                                            ", please send " + str(self.value) + " " + self.coin.upper() +
                                            " to " + config.tronaddr + "\n\n**IMPORTANT**: This is a TRON address. Do not send USDT ERC-20 or USDT BEP-20. " +
                                            "Sending any coin other than USDT TRC-20 will result in loss of funds. You must send _exactly_ this amount. " +
                                            "If you accidentally send too little or too much, please reach out to us for help!")
            self.lasttime = int(time.time())
            return
        r.redditor(self.sender).message("Escrow funding address", "In order to fund the escrow with ID " + self.id + ", please send " + str(self.value) + " " + self.coin.upper() +
                                        " to " + k + "\n\n**Note:** If you accidentally send too little crypto, you can make another transaction for the difference. Please note that the bot must receive *at least* this amount" + 
                                        " for it to consider the escrow funded. You can send slightly more than requested if your wallet deducts the network fee from the total." + config.signature())
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
            txs = bitcoinlib.services.services.Service('litecoin').gettransactions(k.address())
            value = 0
            for tx in txs :
                if (tx.confirmations == 0) :
                    continue
                for outs in tx.as_dict()['outputs'] :
                    value += outs['value'] if outs['address'] == k.address() else 0
            if (Decimal(value) / Decimal(100000000) < self.value) :
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
        elif (self.coin == "usdt") :
            claimed = readclaimed()
            txs = requests.get('https://apilist.tronscan.org/api/transaction?sort=timestamp&address=' + config.tronaddr).json()
            for tx in txs['data'] :
                if (tx['hash'] in claimed or not tx['confirmed']) :
                    continue
                if ("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" in tx['toAddressList']) : #filter out to only USDT transactions
                    value = Decimal(int(tx['contractData']['data'][-8:], 16)) / Decimal("1000000") #convert hex amount info in data str to Decimal object
                    if (value == self.value) :
                        claimed.append(tx['hash']) #this txid is now "claimed" if it is used to mark an escrow as funded
                        writeclaimed(claimed)
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