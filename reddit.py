from prawcore import exceptions
import crypto
import config
import praw
import database
from decimal import Decimal
import prawcore

r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")


def checkinbox(r: praw.Reddit, db: database.Database) -> list :

    #list of escrows to monitor for payment
    elist = []

    for message in r.inbox.unread() :
        message.mark_read()
        b = message.body

        #New escrow transaction
        if ("--NEW TRANSACTION--" in b) :
            try :
                d = b.split('--CONTRACT--')[0].split('\n')
                escrow = crypto.Escrow(d[2].split(' ')[2].lower())
                escrow.contract = b.split('--CONTRACT--')[1]
                #Detects SQL injection attempts in the contract field
                #This is only a problem in that field because everything else splits on a space.
                if ("--" in escrow.contract or ";" in escrow.contract) :
                    message.reply("For security reasons, the escrow contract cannot contain double dashes (`--`) or semicolons (`;`)." + config.signature)
                    continue
                escrow.sender = message.author.name.lower()
                escrow.recipient = d[1].split(' ')[1].lower()
                #Round ETH values to 5 decimal places
                if (escrow.coin == "eth") :
                    precision = Decimal("0.00001")
                    val = Decimal(d[2].split(' ')[1])
                    escrow.value = val.quantize(precision)
                else :
                    escrow.value = Decimal(d[2].split(' ')[1])
                if (not exists(r, escrow.recipient)) :
                    message.reply("The recipient's username does not exist." + config.signature)
                    continue
                try :
                    r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id +"\n\n" +
                                                         "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n'+
                                                         "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                         escrow.contract + "\n\n" +
                                                         "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                         "the terms or the amount, simply ignore this message. You can join again later whenever you want." +
                                                         " **Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                         config.signature)
                    if (escrow.coin == "eth") :
                        message.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." +
                                      " This escrow transaction's ID is " + escrow.id + ". **NOTE: ETH escrow values are rounded to the nearest 0.00001." + config.signature)
                    message.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." +
                                  " This escrow transaction's ID is " + escrow.id + config.signature)
                    
                    db.add(escrow)
                except Exception:
                    message.reply("An error occured while sending the invitation to the recipient. Please ensure that the recipient actually exists and you typed their username correctly. Do not include the u/ in their username.")
                    continue
            except crypto.UnsupportedCoin :
                reply = "Sorry, that coin is currently not supported. The bot only supports "
                for coin in config.coins :
                    reply.append(coin.upper() + " ")
                message.reply(reply + "." + config.signature)
            except Exception as e:
                print(e)
                message.reply("Invalid syntax. Please see [this page](https://www.reddit.com/r/Cash4Cash/wiki/index/escrow) for help." + config.signature)
        #Join an escrow transaction as the recipient
        elif ("!join" in b.lower()) :
            escrow = None
            if (isinstance(message, praw.models.Message) and len(b.split(' ')) == 1) :
                try :
                    b = r.inbox.message(message.parent_id[3:]).body.lower()
                    if ("has invited you to join the escrow with id" not in b) :
                        raise ValueError
                    b = b.split('c4cid')[1].split('\n')[0]
                    escrow = db.lookup('c4cid' + b)
                    print('Looking up c4cid' + b)
                except (prawcore.exceptions.Forbidden, ValueError, TypeError) :
                    message.reply("The message you replied to isn't an invitation to join an escrow. Please try again." + config.signature)
                    continue
            elif (len(b.split(' ')) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!join [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature)
                continue
            else :
                if ("c4cid" in b.lower().split(' ')[1]) :
                    escrow = db.lookup(b.lower().split(' ')[1])
            if (escrow == None) :
                message.reply("This escrow transaction does not exist." + config.signature)
                continue
            if (message.author.name.lower() == escrow.recipient) :
                if (escrow.state == 0) :
                    escrow.state += 1
                    escrow.askpayment()
                    db.add(escrow)
                    elist.append(escrow)
                    continue
                else :
                    message.reply("This escrow transaction cannot be joined." + config.signature)
                    continue
            else :
                message.reply("You are not the intended recipient to this transaction." + config.signature)
                continue

        #Release the escrow to the recipient
        elif ("!release" in b.lower()) :
            m = b.split(' ')
            if (len(m) == 1) :
                try :
                    p = r.inbox.message(message.parent_id[3:]).body.lower()
                    p = p.split('c4cid')[1].split(' ')[0]
                    m.append('c4cid' + p)
                except (prawcore.exceptions.Forbidden, TypeError) :
                    message.reply("It appears that you did not respond to a valid escrow funding notification. You can release any escrow using `" + 
                                  "!release [EscrowID]`." + config.signature)
            elif (len(m) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!release [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature)
                continue
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("The provided escrow ID (" + m[1] + ") does not exist. Escrow IDs begin with \"c4cid\"." + config.signature)
                continue
            if (escrow.state != 2) :
                message.reply("Escrow " + escrow.id + " is not fully funded. Only fully funded escrows can be released.")
                continue
            if (message.author.name.lower() == escrow.sender) :
                escrow.release()
                db.add(escrow)
            else :
                message.reply("You are not authorised to release that escrow. Only the sender may release the escrow." + config.signature)
            
            # try :
            #     if ("successfully funded" in message.parent().body.lower()) :
            #         for word in message.parent().body.lower().split(" ") :
            #             if ("c4cid" in word) :
            #                 escrow = db.lookup(word)
            #                 if (escrow.state != 2) :
            #                     message.reply("This escrow cannot be released. Only fully-funded unreleased escrows can be released." + config.signature)
            #                     continue
            #                 if (message.author.name.lower() == escrow.sender) :
            #                     escrow.release()
            #                     db.add(escrow)
            #                     continue
            #         else :
            #             message.reply("This message thread is not an escrow transaction.")
        #Refund the escrow to the sender
        elif ("!refund" in b.lower()) :
            m = b.split(' ')
            if (len(m) == 1) :
                try :
                    p = r.inbox.message(message.parent_id[3:]).body.lower()
                    p = p.split('c4cid')[1].split(' ')[0]
                    m.append('c4cid' + p)
                except (prawcore.exceptions.Forbidden, TypeError) :
                    message.reply("It appears that you did not respond to a valid escrow funding notification. You can refund any escrow using `" + 
                                  "!refund [EscrowID]`." + config.signature)
            elif (len(m) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!refund [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature)
                continue
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("The provided escrow ID (" + m[1] + ") does not exist. Escrow IDs begin with \"c4cid\"." + config.signature)
                continue
            if (escrow.state != 2) :
                message.reply("The escrow with ID " + escrow.id + " is not fully funded. Only fully funded escrows can be released.")
                continue
            if (message.author.name.lower() == escrow.recipient) :
                escrow.refund()
                db.add(escrow)
            else :
                message.reply("You are not authorised to refund that escrow. Only the recipient may release the escrow." + config.signature)
        #Withdraw funds from an escrow
        elif ("!withdraw" in b.lower()) :
            m = b.split(' ')
            if ('c4cid' not in m[1]) :
                try :
                    p = r.inbox.message(message.parent_id[3:]).body.lower()
                    if ("was released to you" not in p) :
                        raise TypeError
                    p = p.split('c4cid')[1].split(' ')[0]
                    m.insert(1, 'c4cid' + p)
                except (TypeError, prawcore.exceptions.Forbidden) :
                    message.reply("The message you replied to is not a funds availability notice. You can also withdraw from any escrow given the escrow ID by using `!withdraw [escrow ID] [address]`" +
                                  config.signature)
                    continue
            if (len(m) != 3 and len(m) != 4) :
                message.reply("Invalid syntax. The correct syntax is `!withdraw [escrow ID] [address]`. Additionally, you may specify your own feerate: `!withdraw [escrow ID] [address] [feerate]`" +
                              config.signature)
                continue
            m.append('0')
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("That escrow ID (" + m[1] + ") does not exist." + config.signature)
                continue
            if ((escrow.recipient != message.author.name.lower() and escrow.state == 3) or (escrow.sender != message.author.name.lower() and escrow.state == -1)) :
                message.reply("You are not authorised to withdraw from this escrow." + config.signature)
                continue
            elif (escrow.state != 3 and escrow.state != -1) :
                print (escrow.id, escrow.state)
                message.reply("This escrow cannot be withdrawn from." + config.signature)
                continue
            try :
                txid = escrow.pay(m[2],int(m[3]))
                if (txid == None) :
                    message.reply("An error occured while sending to that address. Please make sure the address is correct." + config.signature)
                else :
                    message.reply("Sent TXID: " + txid + config.signature)
                    escrow.state = 4
                    db.add(escrow)
            except ValueError as e:
                print (e)
                message.reply("Invalid feerate. Feerate must be a number." + config.signature)
                continue

            
        else :
            #If no command is found, mark it unread.
            #This is so another script can check it for triggers.
            message.mark_read()
    return elist

def checksub(r: praw.Reddit) :
    """
    Check the subreddit for new escrow transactions.
    """
    commentsrepliedto = []
    with open ('comments.txt', 'r') as f :
        s = f.read()
        s.split('\n')
        commentsrepliedto = s

    for comment in r.subreddit(config.subreddit).comments(limit=20) :
        if (comment.id in commentsrepliedto) :
            continue
        b = comment.body.lower()
        if ("!escrow" in b) :
            if (len(b.split(' ')) == 1) :
                comment.reply("`!escrow`: open a new escrow transaction\n\nUsage: `!escrow [partner] [amount] [coin]`" +
                              "\n\nStarts a new escrow transaction with u/`partner` for `[amount]` of `[coin]`. For example, `!escrow NateNate60 0.001 BTC` will open" +
                              " a new escrow transaction with NateNate60 for 0.001 Bitcoin. Additionally, you can put any arbitrary contract text after the command, seperated by a line break." +
                              " So, you can type:\n\n    !escrow NateNate60 0.001 BTC\n    \n    NateNate60 agrees to send me one 50kg crate of potatoes in exchange for\n    0.001 BTC.\n\n" +
                              "For more information, [click here](https://reddit.com/r/Cash4Cash/wiki/index/escrow)." + config.signature)
            else :
                b = b.split('\n\n')
                if (len(b) == 1) :
                    b.append("")
                contract = ""
                for i in range(1, len(b)) :
                    contract += comment.body.split('\n\n')[i]
                    contract += '\n\n'
                if ('--' in contract or ';' in contract) :
                    comment.reply("For security reasons, the contract data may not contain double dashes (`--`) or semicolons (`;`)." + config.signature)
                    continue
                escrow = None
                try :
                    escrow = crypto.Escrow(b[0].split(' ')[3])
                    escrow.contract = contract
                    escrow.recipient = b[0].split(' ')[1]
                    escrow.sender = comment.author.name()
                    escrow.value = Decimal(b[0].split(' ')[2])
                except crypto.UnsupportedCoin :
                    comment.reply(b[0].split(' ')[2] + " is not a supported coin type.")
                except Exception :
                    comment.reply("An error has occured. Please check the syntax and try again." + config.signature)
                try :
                    if (escrow.coin != 'eth') :
                        r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id +"\n\n" +
                                                            "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n'+
                                                            "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                            escrow.contract + "\n\n" +
                                                            "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                            "the terms or the amount, simply ignore this message. You can join again later whenever you want." +
                                                            "\n\n**Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                            config.signature)
                    else :
                        r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id +"\n\n" +
                                                            "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n'+
                                                            "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                            escrow.contract + "\n\n" +
                                                            "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                            "the terms or the amount, simply ignore this message. You can join again later whenever you want. Since this is an ETH escrow, please be aware that " +
                                                            "custom feerates are not supported yet when you withdraw your funds.\n\n"
                                                            " **Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                            config.signature)
                    comment.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." +
                                  " This escrow transaction's ID is " + escrow.id + config.signature)
                    database.add(escrow)
                except Exception:
                    comment.reply("An error occured while sending the invitation to the recipient. Please ensure that the recipient actually exists and you typed their username correctly. Do not include the u/ in their username.")
                    continue
    with open ('comments.txt', 'w') as f :
        write = ""
        for c in commentsrepliedto :
            write += c + '\n'
        f.write(write)


def exists(r: praw.Reddit, username: str) :
    """
    Returns whether a Reddit user exists
    """
    try :
        r.redditor(username).id
    except prawcore.exceptions.NotFound :
        return False
    return True