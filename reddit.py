import crypto
import config
import praw
import database
from decimal import Decimal

r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")


def checkinbox(r: praw.Reddit, db: database.Database) :
    for message in r.inbox.unread() :
        b = message.body

        #New escrow transaction
        if ("--NEW TRANSACTION--" in b) :
            try :
                d = b.split('--CONTRACT--')[0].split('\n')
                escrow = crypto.Escrow(d[2].split(' ')[2].lower())
                escrow.contract = b.split('--CONTRACT--')[1]
                escrow.sender = message.author.name.lower()
                escrow.recipient = d[1].split(' ')[1].lower()
                escrow.value = Decimal(d[2].split(' ')[1])
                try :
                    r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join an escrow transaction.\n\n" +
                                                         "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n'+
                                                         "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                         escrow.contract + "\n\n" +
                                                         "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                         "the terms or the amount, simply ignore this message. You can join again later whenever you want." +
                                                         "**Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                         config.signature)
                    message.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." +
                              " This escrow transaction's ID is " + escrow.id + config.signature)
                    db.add(escrow)
                except Exception:
                    message.reply("An error occured while sending the invitation to the recipient. Please ensure that the recipient actually exists and you typed their username correctly. Do not include the u/ in their username.")
                    continue
            except Exception :
                message.reply("Invalid syntax. Please see [this page](https://www.reddit.com/r/Cash4Cash/wiki/index/escrow) for help." + config.signature)
        elif ("!join" in b) :
            try :
                if ("has invited you to join an escrow transaction" in message.parent().body.lower()) :
                    for word in message.parent().body.lower().split(" ") :
                        if ("c4cid" in word) :
                            escrow = db.lookup(word)
                            if (message.author.name.lower() == escrow.recipient) :
                                if (escrow.state == 0) :
                                    escrow.state += 1
                                    escrow.askpayment()
                                    continue
                                else :
                                    message.reply("This escrow transaction cannot be joined." + config.signature)
                                    continue
                            else :
                                message.reply("You are not the intended recipient to this transaction." + config.signature)
                                continue
                    message.reply("This transaction is not an escrow transaction." + config.signature)
            except Exception :
                message.reply("An error has occured." + config.signature)

