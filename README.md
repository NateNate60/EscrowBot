# EscrowBot

## Are you interested in having this bot run on your subreddit?

Contact me using the information below! Hosting is provided by me, free of charge. The bot runs in a US datacentre and the server receives regular security updates.

You are also free to clone the code and run it yourself!

Dependencies:

- Bit (`pip3 install bit`). Bitcoin library.
- Bitcash (`pip3 install bitcash`). Bitcoin Cash library.
- Bitcoinlib (`pip3 install bitcoinlib`). Used for its Litecoin functionality and fee estimation. The Bitcoin functionality is not actually used
- Web3 (`pip3 install web3`). Ethereum library
- Hashlib. IDs are generated using SHA-1 hashes. SHA-1 is faster than SHA-2 and these don't need to be resistent to attacks because they're only used for ID purposes

**PLEASE FEEL FREE TO PERUSE MY CODE AND POINT OUT MISTAKES, BUGS, OR SECURITY FLAWS**

If you spot a security flaw, either open an issue to bring it to my attention or fix it yourself and open a pull request. For particularly serious problems, please see my contact info at the bottom and send me a message in private. If the bug can be easily exploited in a way that could cause money to be lost or stolen, I will personally pay you a small bug bounty.

Also, if you're wondering why I only use `bitcoinlib` for Litecoin and not for Bitcoin as well, it's because `bitcoinlib` is stupidly slow to run. `bit` is much faster than `bitcoinlib`, no contest.

## Donations welcome!

If I get enough in donations then we probably won't need to collect any escrow fees. I'm not doing this for profit.

- btc: 3BzrZKHv1F5qNZK45vUkZMBZUrpF1vtgD9
- bch: qzj3km6zfqlul8utf2kepwxncmadp5j80qg7dp0m3g
- ltc: MWXZLvyL7rE5zarAxz6i34iqwVFJzZ978o
- eth: 0xC50840e9fec8d5F6c696896362393a0Ac3d1A8b6


## To-do list

- add XLM support
- add DOGE support
- maybe stablecoins too

## Contact info

For disputes with a particular transaction, please contact the r/Cash4Cash moderators. For anything else, here's my info:

- Reddit: [u/NateNate60](https://reddit.com/u/NateNate60)
- Email: natenate60@yahoo.com
- Discord: NateNate60\#2439
