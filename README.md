# EscrowBot

This bot is no longer active due to changes in the regulatory environment.

## List of supported coins

- Bitcoin (+testnet)
- Bitcoin Cash
- Litecoin
- Ethereum
- Dogecoin
- Tether (USDT TRC-20)

Dependencies:

- Bit (`pip3 install bit`). Bitcoin library.
- Bitcash (`pip3 install bitcash`). Bitcoin Cash library.
- Bitcoinlib (`pip3 install bitcoinlib`). Used for its Litecoin functionality. The Bitcoin functionality is not actually used
- Web3 (`pip3 install web3`). Ethereum library
- Hashlib. IDs are generated using SHA-256 hashes, then truncated to 16 hex digits (total hash length = 64 bits, still very unlikely to collide but not so long as to be unweildly)
- PRAW (`pip3 install praw`). The most widely-used Python library to interact with Reddit's API.
- Etherscan (`pip3 install etherscan-python`). Interacts with [Etherscan](https://etherscan.io) for the purposes of fee estimation on ETH and for looking up transactions and account balances.
- [USLAPI](https://github.com/Tjstretchalot/uslapi). Warns users if one of the parties is a [USL](https://universalscammerlist.com)-listed scammer.
- Tronpy (`pip3 install tronpy`). TRON library.
- Requests (`pip3 install requests`). Used to grab info from Mempool.space and Tronscan.

**PLEASE FEEL FREE TO PERUSE MY CODE AND POINT OUT MISTAKES, BUGS, OR SECURITY FLAWS**

If you spot a security flaw, either open an issue to bring it to my attention or fix it yourself and open a pull request. For particularly serious problems, please see my contact info at the bottom and send me a message in private. If the bug can be easily exploited in a way that could cause money to be lost or stolen, I will personally pay you a small bug bounty.

Also, if you're wondering why I only use `bitcoinlib` for Litecoin and not for Bitcoin as well, it's because `bitcoinlib` is stupidly slow to run. `bit` is much faster than `bitcoinlib`, no contest.

## Donations welcome!

- btc: 3EBf6eixSLUB3sh5XzsjAFpk6A5rF37X18
- lightning (feel free to open a channel!): 033a7fca1cb089b33ac232dd73c2c32aeacffe16319b72bec16208f3a9002e6d17
- bch: qp5ne9w8dnnw364vqpz9nknankkw5qsc254qmhr8cz
- ltc: ltc1qnwydu80eh9l8l2ptasz6as04z30dq5ljampvxj
- eth: 0xC50840e9fec8d5F6c696896362393a0Ac3d1A8b6
- doge: DTKnpTnn1JNBRZBibF4L7a9WKDtLcU56Ue
- usdt (trc-20): TDJjy4nRQwpNRFjWg45GZmhbQDaGNUxgEB
- trx: TDJjy4nRQwpNRFjWg45GZmhbQDaGNUxgEB
- xmr: 471QNEmNCjx81duY9NkzBcVezM9Hx1i1XMpRSy9PJdAp6Yrfpcg83syV6PZtk6dctgEex48FqXDdj9ejBnphC7SQ5Tu8WYN
- coinbase: nathanlim2004@gmail.com
- cash app: $NathanQLim


## To-do list

- add XLM support
- maybe stablecoins too

## Contact info

For disputes with a particular transaction, please contact the r/Cash4Cash moderators. For anything else, here's my info:

- Reddit: [u/NateNate60](https://reddit.com/u/NateNate60)
- Email: natenate60@yahoo.com
- Discord: NateNate60\#2439
