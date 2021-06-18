# EscrowBot


**I NEED BCH TESTNET FOR TESTING**. Please send me some BCH testnet if you have some: bchtest:qz5eur3prqyvd8u77m6fzf9z6cruz9q7vq4qvgdnuk

Dependencies:

- Bit (`pip3 install bit`). Bitcoin library.
- Bitcash (`pip3 install bitcash`). Bitcoin Cash library.
- Lit (`pip3 install lit`). Litecoin library, although not sure it works since it looks like it's been abandoned for years
- Web4 (`pip3 install web3`). Ethereum library, although I have not implemented this functionality yet
- Hashlib. IDs are generated using SHA-1 hashes. SHA-1 is faster than SHA-2 and these don't need to be resistent to attacks because they're only used for ID purposes

**PLEASE FEEL FREE TO PERUSE MY CODE AND POINT OUT MISTAKES, BUGS, OR SECURITY FLAWS**

If you spot a security flaw, either open an issue to bring it to my attention or fix it yourself and open a pull request. **This code is not for production use and is probably still very buggy. I did not test it yet.** This code is not and should not be used anywhere until I make sure everything's all good and secure.

## Donations welcome!

If I get enough in donations then we probably won't need to collect any escrow fees. I'm not doing this for profit.

- btc: 3BzrZKHv1F5qNZK45vUkZMBZUrpF1vtgD9
- bch: qplz54sn699hwjfk6ycdglew4ac2fj77dsrzswdmrt
- ltc: MUdgxeRpwoj43ima87kWnhsvQpMJBSBPrD


## To-do list

- debug and make sure it actually works
- find replacement for `lit` since the odds of that library actually working are low
- add ETH support
- add XLM support
- add DOGE support
- maybe stablecoins too
