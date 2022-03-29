import crypto
import config
import praw
import database
from decimal import Decimal, InvalidOperation
import prawcore
import atexit
from datetime import datetime
from uslapi import uslapi

r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")

#For interacting with the USL
usls = uslapi.UniversalScammerList('bot EscrowBot')
usl = usls.login(config.uslusername, config.uslpassword)

def usllogout():
    """
    Logs out of the USL
    """
    usls.logout(usl)
#Auto-logout USL upon exit
atexit.register(usllogout)

def formatescrowlist (escrowlist: list) -> str :
    """
    Format a list of escrows into Markdown for usage in a Reddit reply
    """
    text = "|Escrow ID|Sender|Recipient|Amount|Coin|State|Last Used (Pacific Time)|\n|---|---|---|---|---|---|---|\n"
    for escrow in escrowlist :
        text += "|" + escrow.id + "|u/" + escrow.sender + "|u/" + escrow.recipient + "|" + str(escrow.value) + "|" + escrow.coin + "|" + crypto.interpretstate(escrow.state) + "|" + datetime.fromtimestamp(escrow.lasttime).strftime('%Y-%m-%d %H:%M:%S') + "|\n"
    return text


def checkinbox(r: praw.Reddit, db: database.Database) -> list :

    #list of escrows to monitor for payment
    elist = []

    for message in r.inbox.unread() :
        b = message.body
        if (message.body[:2] == "! ") :
            b = "!" + message.body[2:]
            message.body = b
        
        if ("!info" in b) :
            if (len(b.split(" " )) == 2) :
                
                escrow = db.lookup(b.split(" ")[1])
                if (escrow == None) :
                    message.reply("The given escrow id of `" + db.lookup(b.split(" ")[1]) + '` does not exist.' + config.signature())
                else :
                    message.reply("Escrow lookup result:\n\n" + formatescrowlist([escrow]) + config.signature())
            else :
                if (message.author.name.lower() in config.mods) :
                    message.reply("Escrow lookup result (last 30 days):\n\n" + formatescrowlist(db.latest()) + config.signature())
                else :
                    message.reply("Only mods can look up all escrows. Please use `!info escrowID` to get information about a specific escrow.")
            message.mark_read()
            continue
            
        if ("!lock" in b) :
            if (len(b.split(" ")) == 2) :
                escrow = db.lookup(b.split(' ')[1])
                if (escrow == None) :
                    message.reply("The given escrow id of `" + db.lookup(b.split(" ")[1]) + '` does not exist.' + config.signature())
                elif (message.author.name.lower() in config.mods) :
                    if (escrow.state == 2 or escrow.state == 3 or escrow.state == -1) :
                        escrow.state = -2
                        db.add(escrow)
                    message.reply("Successfully locked." + config.signature())
                else :
                    message.reply("You are not authorised to do that." + config.signature())
            else :
                message.reply("Invalid syntax. Please provide an escrow ID using `!lock escrowID`")
            message.mark_read()

        if ("!unlock" in b) :
            if (len(b.split(" ")) == 3) :
                escrow = db.lookup(b.split(' ')[1])
                if (escrow == None) :
                    message.reply("The given escrow id of `" + db.lookup(b.split(" ")[1]) + '` does not exist.' + config.signature())
                elif (message.author.name.lower() in config.mods) :
                    if (escrow.state == -2) :
                        escrow.state = 2
                        db.add(escrow)
                    message.reply("Successfully unlocked." + config.signature())
                else :
                    message.reply("You are not authorised to do that." + config.signature())
            else :
                message.reply("Invalid syntax. Please provide an escrow ID using `!unlock escrowID`")
            message.mark_read()

        #Responses to interactive mode
        if (b[:2] == "u/") :
            parent = r.inbox.message(message.parent_id[3:]).body
            if ("**Interactive mode**" in parent) :
                message.reply("**Interactive mode**: Your trade partner is u/" + b.split()[0][2:] + "\n\n- If this is *not correct*, reply with your" +
                              " trade partner's username, including the u/ (such as u/test).\n- If this is *correct*, reply with the amount of crypto that you will " +
                              "send into the escrow, such as `0.001 BTC`." + config.signature())
            message.mark_read()
            continue
        if (len(b.split()) == 2) :
            try :
                parent = r.inbox.message(message.parent_id[3:])
                if ("**Interactive mode**" in parent.body) :
                    try :
                        if (b.split()[1].lower() not in config.coins) :
                            raise InvalidOperation
                        Decimal(b.split()[0])
                        message.reply("**Interactive mode**: Your trade partner is " + parent.body.split()[6] + " and you will send " + message.body +
                                    " into the escrow.\n\n- If everything is *correct*, reply \"done\".\n- If the name of your trade parter is *not correct*, " +
                                    "reply with the username of your trade partner, including the u/ (such as u/test).\n- If the amount of the escrow is *not " +
                                    "correct*, please reply with the amount you will send into the escrow (such as `0.75 LTC`)." + config.signature())
                    except InvalidOperation :
                        message.reply("**Interactive mode**: Your trade partner is " + parent.body.split()[6] + "\n\nWe couldn't detect the amount of the escrow." +
                                    " Please reply with the amount of crypto that you will send into the escrow, such as `0.05 ETH`." + config.signature())
                    message.mark_read()
            except (prawcore.exceptions.Forbidden, TypeError) :
                pass
        if ("done" in b.lower() and len(b) < 7) :
            parent = r.inbox.message(message.parent_id[3:]).body
            b = "--NEW TRANSACTION--\nPartner: " + parent.split()[6][2:] + '\nAmount: ' + parent.split()[11] +' ' + parent.split()[12] + "\n--CONTRACT--\n"

        #New escrow transaction
        if ("--NEW TRANSACTION--" in b) :
            try :
                if ("yourtradepartnersusername" in b or "0.12345 BTC/BCH" in b) :
                    #start interactive mode
                    message.reply("**Interactive mode**: Please reply to this message with the username of the person you'd like to start an escrow transaction with, including the u/. " +
                                  "For example, if your trade partner's username is u/test, reply to this message with `u/test`." + config.signature())
                    message.mark_read()
                    continue
                d = b.split('--CONTRACT--')[0].split('\n')
                escrow = crypto.Escrow(d[2].split(' ')[2].lower())
                escrow.contract = b.split('--CONTRACT--')[1]
                #Detects SQL injection attempts in the contract field
                #This is only a problem in that field because everything else splits on a space.
                if ("--" in escrow.contract or ";" in escrow.contract) :
                    message.reply("For security reasons, the escrow contract cannot contain double dashes (`--`) or semicolons (`;`)." + config.signature())
                    message.mark_read()
                    continue
                escrow.sender = message.author.name.lower()
                escrow.recipient = d[1].split(' ')[1].lower()
                if ('u/' in escrow.recipient) :
                    escrow.recipient = escrow.recipient[2:]
                #Round ETH values to 5 decimal places
                if (escrow.coin == "eth") :
                    precision = Decimal("0.00001")
                    val = Decimal(d[2].split(' ')[1])
                    escrow.value = val.quantize(precision)
                else :
                    escrow.value = Decimal(d[2].split(' ')[1])
                if (not exists(r, escrow.recipient)) :
                    message.reply("The recipient's username does not exist." + config.signature())
                    message.mark_read()
                    continue
                try :
                    #list of the USL status of escrow [sender, recipient]
                    listed = [usls.query(usl, escrow.sender), usls.query(usl, escrow.recipient)]
                    r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id +"\n\n" +
                                                         "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n\n'+
                                                         "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                         escrow.contract + "\n\n" +
                                                         "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                         "the terms or the amount, simply ignore this message. You can join again later whenever you want. Escrows are subject to a small" +
                                                         " fee in order to help pay for server costs. More info about the escrow and the fee schedule can be found on our [wiki page](https://reddit.com/r/cash4cash/wiki/index/escrow)" +
                                                         "\n\n**Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                         "\n\n**Note:** This escrow is for USDT TRC-20."*(escrow.coin == 'usdt') +
                                                         "\n\n**Warning:** The person who initiated this escrow is listed on the Universal Scammer List. Please exercise caution and proceed at your own risk." * listed[0]["banned"] +
                                                         config.signature())
                    if (escrow.coin == "eth") :
                        message.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." +
                                      " This escrow transaction's ID is " + escrow.id + ". **NOTE**: ETH escrow values are rounded to the nearest 0.00001." + "\n\n**Warning:** The person who you're dealing with is listed on the Universal Scammer List. Please exercise caution and proceed at your own risk." * listed[1] + config.signature())
                    message.reply("New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow." + "\n\n**Warning:** The person who you're dealing with is listed on the Universal Scammer List. Please exercise caution and proceed at your own risk." * listed[1]["banned"] +
                                  " This escrow transaction's ID is " + escrow.id + config.signature())
                    
                    db.add(escrow)
                except Exception:
                    message.reply("An error occured while sending the invitation to the recipient. Please ensure that the recipient actually exists and you typed their username correctly. Do not include the u/ in their username.")
                    message.mark_read()
                    continue
            except crypto.UnsupportedCoin :
                reply = "The amount line must specify the amount in cryptocurrency (such as `0.001 BTC` or `0.5 LTC`). The bot supports "
                for coin in config.coins :
                    reply += coin.upper() + " "
                message.reply(reply + "." + config.signature())
            except Exception as e:
                print(e)
                message.reply("**Interactive mode**: We couldn't read the information you provided in the form, but we can still proceed with the escrow. Please reply to this message with the username of the person you'd like to start an escrow transaction with, including the u/. " +
                              "For example, if your trade partner's username is u/test, reply to this message with `u/test`." + config.signature())
            message.mark_read()
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
                except (prawcore.exceptions.Forbidden, ValueError, TypeError, IndexError) :
                    message.reply("The message you replied to isn't an invitation to join an escrow. Please try again." + config.signature())
                    message.mark_read()
                    continue
            elif (len(b.split(' ')) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!join [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature())
                message.mark_read()
                continue
            else :
                if ("c4cid" in b.lower().split(' ')[1]) :
                    escrow = db.lookup(b.lower().split(' ')[1])
            if (escrow == None) :
                message.reply("This escrow transaction does not exist." + config.signature())
                message.mark_read()
                continue
            if (message.author.name.lower() == escrow.recipient) :
                if (escrow.state == 0) :
                    if (escrow.coin == 'usdt') : #if escrow with this value already exists, sub 0.001 USDT until a unique value is found
                        adjusted = False
                        while (db.detectduplicate(escrow.value, "usdt")) :
                            escrow.value -= Decimal('0.001')
                            adjusted = True
                        message.reply("Joined successfully. The sender has been asked to make the payment.\n\n " +
                                      "**Note**: An escrow for this amount already exists in the payment phase. For technical reasons, the amount of this escrow has been slightly reduced by less than 0.01 USDT in order to make the escrow amount unique."*adjusted + 
                                      config.signature())
                    else :
                        message.reply("Joined successfully. The sender has been asked to make the payment." + config.signature())
                    escrow.state += 1
                    askpayment(escrow)
                    db.add(escrow)
                    elist.append(escrow)
                    message.mark_read()
                    continue
                else :
                    message.reply("This escrow transaction cannot be joined." + config.signature())
                    message.mark_read()
                    continue
            else :
                message.reply("You are not the intended recipient to this transaction." + config.signature())
                message.mark_read()
                continue

        #Release the escrow to the recipient
        elif ("!release" in b.lower()) :
            m = b.split(' ')
            if (len(m) == 1) :
                try :
                    p = r.inbox.message(message.parent_id[3:]).body.lower()
                    p = p.split('c4cid')[1].split(' ')[0]
                    m.append('c4cid' + p)
                except (prawcore.exceptions.Forbidden, TypeError, IndexError) :
                    message.reply("It appears that you did not respond to a valid escrow funding notification. You can release any escrow using `" + 
                                  "!release [EscrowID]`." + config.signature())
                    message.mark_read()
                    continue
            elif (len(m) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!release [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature())
                message.mark_read()
                continue
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("The provided escrow ID (`" + m[1] + "`) does not exist. Escrow IDs begin with \"c4cid\"." + config.signature())
                message.mark_read()
                continue
            if (escrow.state != 2) :
                message.reply("Escrow " + escrow.id + " is not fully funded. Only fully funded escrows can be released.")
                message.mark_read()
                continue
            if (message.author.name.lower() == escrow.sender or message.author.name.lower() in config.mods) :
                escrow.release()
                notifyavailable(escrow)
                db.add(escrow)
                message.reply("Successfully released." + config.signature())
                message.mark_read()
            else :
                message.reply("You are not authorised to release that escrow. Only the sender may release the escrow." + config.signature())
            message.mark_read()
            # try :
            #     if ("successfully funded" in message.parent().body.lower()) :
            #         for word in message.parent().body.lower().split(" ") :
            #             if ("c4cid" in word) :
            #                 escrow = db.lookup(word)
            #                 if (escrow.state != 2) :
            #                     message.reply("This escrow cannot be released. Only fully-funded unreleased escrows can be released." + config.signature())
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
                except (prawcore.exceptions.Forbidden, TypeError, IndexError) :
                    message.reply("It appears that you did not respond to a valid escrow funding notification. You can refund any escrow using `" + 
                                  "!refund [EscrowID]`." + config.signature())
                    message.mark_read()
                    continue
            elif (len(m) != 2) :
                message.reply("Invalid syntax. The correct syntax is `!refund [escrow ID]`. Escrow IDs begin with \"c4cid\"." + config.signature())
                message.mark_read()
                continue
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("The provided escrow ID (" + m[1] + ") does not exist. Escrow IDs begin with \"c4cid\"." + config.signature())
                message.mark_read()
                continue
            if (escrow.state != 2) :
                message.reply("The escrow with ID " + escrow.id + " is not fully funded. Only fully funded escrows can be released.")
                message.mark_read()
                continue
            if (message.author.name.lower() == escrow.recipient or message.author.name.lower() in config.mods) :
                escrow.refund()
                notifyavailable(escrow, True)
                db.add(escrow)
                message.reply("Successfully refunded." + config.signature())
            else :
                message.reply("You are not authorised to refund that escrow. Only the recipient may release the escrow. If you are the sender, please note that this is not a bug; it prevents people from sending the money and then refunding it to themselves." + config.signature())
            message.mark_read()
        #Withdraw funds from an escrow
        elif ("!withdraw" in b.lower()) :
            m = message.body.split(' ')
            if ('c4cid' not in m[1]) :
                try :
                    p = r.inbox.message(message.parent_id[3:]).body.lower()
                    if ("was released to you" not in p) :
                        raise TypeError
                    p = p.split('c4cid')[1].split(' ')[0]
                    m.insert(1, 'c4cid' + p)
                except (TypeError, prawcore.exceptions.Forbidden) :
                    message.reply("The message you replied to is not a funds availability notice. You can also withdraw from any escrow given the escrow ID by using `!withdraw [escrow ID] [address]`" +
                                  config.signature())
                    message.mark_read()
                    continue
            if (len(m) != 3 and len(m) != 4) :
                message.reply("Invalid syntax. The correct syntax is `!withdraw [escrow ID] [address]`. Additionally, you may specify your own feerate: `!withdraw [escrow ID] [address] [feerate]`" +
                              config.signature())
                message.mark_read()
                continue
            m.append('0')
            escrow = db.lookup(m[1])
            if (escrow == None) :
                message.reply("That escrow ID (" + m[1] + ") does not exist." + config.signature())
                message.mark_read()
                continue
            if ((escrow.recipient != message.author.name.lower() and escrow.state == 3) or (escrow.sender != message.author.name.lower() and escrow.state == -1)) :
                message.reply("You are not authorised to withdraw from this escrow." + config.signature())
                message.mark_read()
                continue
            elif (escrow.state != 3 and escrow.state != -1) :
                print (escrow.id, escrow.state)
                message.reply("This escrow cannot be withdrawn from." + config.signature())
                message.mark_read()
                continue
            try :
                txid = escrow.pay(m[2],int(m[3]))
                if (txid == None) :
                    message.reply("An error occured while sending to that address. Please make sure the address is correct." + config.signature())
                else :
                    message.reply("Sent TXID: " + txid + config.signature(True))
                    escrow.state = 4
                    db.add(escrow)
            except ValueError as e:
                print (e)
                message.reply("Invalid feerate. Feerate must be a number." + config.signature())
                message.mark_read()
                continue
            message.mark_read()
    return elist

def checksub(r: praw.Reddit, db: database.Database) :
    """
    Check the subreddit for new escrow transactions.
    """
    commentsrepliedto = []
    with open ('comments.txt', 'r') as f :
        s = f.read()
        commentsrepliedto = s.split('\n')
        try :
            while ('' in commentsrepliedto) :
                commentsrepliedto.remove('')
        except ValueError :
            pass

    for comment in r.subreddit(config.subreddit).comments(limit=1000) :
        try :
            if (comment.id in commentsrepliedto or comment.author.name == r.user.me().name or comment.author.name == "AutoModerator") :
                continue
        except AttributeError :
            continue
        b = comment.body.lower()
        if ("!escrow" in b) :
            if (len(b.split(' ')) == 1) :
                comment.reply("`!escrow`: open a new escrow transaction\n\nUsage: `!escrow [partner] [amount] [coin]`" +
                              "\n\nStarts a new escrow transaction with u/`partner` for `[amount]` of `[coin]`. For example, `!escrow NateNate60 0.001 BTC` will open" +
                              " a new escrow transaction with NateNate60 for 0.001 Bitcoin. Additionally, you can put any arbitrary contract text after the command, seperated by a line break." +
                              " So, you can type:\n\n    !escrow NateNate60 0.001 BTC\n    \n    NateNate60 agrees to send me one 50kg crate of potatoes in exchange for\n    0.001 BTC.\n\n" +
                              "For more information, [click here](https://reddit.com/r/Cash4Cash/wiki/index/escrow)." + config.signature())
            else :
                b = b.split('\n\n')
                if (len(b) == 1) :
                    b.append("")
                contract = ""
                try :
                    for i in range(1, len(b)) :
                        contract += comment.body.split('\n\n')[i]
                        contract += '\n\n'
                except IndexError :
                    pass
                if ('--' in contract or ';' in contract) :
                    comment.reply("For security reasons, the contract data may not contain double dashes (`--`) or semicolons (`;`)." + config.signature())
                    continue
                escrow = None
                try :
                    escrow = crypto.Escrow(b[0].split(' ')[3])
                    escrow.contract = contract
                    escrow.recipient = b[0].split(' ')[1]
                    if ('u/' in escrow.recipient) :
                        escrow.recipient = escrow.recipient[2:]
                    escrow.sender = comment.author.name.lower()
                    escrow.value = Decimal(b[0].split(' ')[2])
                except crypto.UnsupportedCoin :
                    comment.reply(b[0].split(' ')[2] + " is not a supported coin type.")
                except InvalidOperation :
                    comment.reply("Invalid amount. Please make sure the amount (" + b[0].split(' ')[2] + ") is correct and is a number.")
                except Exception :
                    comment.reply("An error has occured. Please check the syntax and try again." + config.signature())
                reply = ""
                try :
                    if (escrow.contract == "") :
                        escrow.contract = "*The sender did not supply any contract terms.*"
                    if (escrow.coin != 'eth') :
                        m = (
                        "Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id + "\n\n" +
                        "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n\n'+
                        "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                        escrow.contract + "\n\n" +
                        "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                        "the terms or the amount, simply ignore this message. You can join again later whenever you want. Escrows are subject to a small" +
                        " fee in order to help pay for server costs. More info about the escrow and the fee schedule can be found on our [wiki page](https://reddit.com/r/cash4cash/wiki/index/escrow)" +
                        "\n\n**Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                        "\n\n**Note:** This escrow is for USDT TRC-20."*(escrow.coin == "usdt") +
                        config.signature())
                        r.redditor(escrow.recipient).message(m[0], m[1])
                    else :
                        r.redditor(escrow.recipient).message("Invitation to join escrow", escrow.sender + " has invited you to join the escrow with ID " + escrow.id +"\n\n" +
                                                            "The amount to be escrowed: " + str(escrow.value) + ' ' + escrow.coin.upper() + '\n\n'+
                                                            "If you wish to join the escrow transaction, you must agree to the following terms, as set out by u/" + escrow.sender + ":\n\n" +
                                                            escrow.contract + "\n\n" +
                                                            "If you agree to the terms and would like to join the escrow, reply `!join`. If you DO NOT agree to " +
                                                            "the terms or the amount, simply ignore this message. You can join again later whenever you want. Escrows are subject to a small" +
                                                            " fee in order to help pay for server costs. More info about the escrow and the fee schedule can be found on our [wiki page](https://reddit.com/r/cash4cash/wiki/index/escrow)" +
                                                            "Since this is an ETH escrow, please be aware that " +
                                                            "custom feerates are not supported yet when you withdraw your funds.\n\n" +
                                                            " **Note:** This does not mean that the sender is guaranteed not a scammer. The escrow has not been funded and no money has been sent yet." +
                                                            config.signature())
                    reply = "New escrow transaction opened. We are now waiting for u/" + escrow.recipient + " to agree to the escrow. This escrow transaction's ID is " + escrow.id + config.signature()
                    if (escrow.contract == "*The sender did not supply any contract terms.*") :
                        reply += "\n\nTip: You can add a \"contract\" on a separate line after the line containing `!escrow`. The recipient will be asked to agree to the contract before joining the escrow."
                    db.add(escrow)
                except Exception:
                    reply = "An error occured while sending the invitation to the recipient. Please ensure that the recipient actually exists and you typed their username correctly. Do not include the u/ in their username." + config.signature()
                try :
                    comment.reply(reply)
                except praw.exceptions.RedditAPIException :
                    comment.author.message('Escrow transaction opened', "Due to Reddit rate limits, I couldn't directly reply to your comment. You can help with this by upvoting some of the bot's comments to give it more karma.\n\n" + reply)
        commentsrepliedto.append(comment.id)
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

def notifyavailable (escrow: crypto.Escrow, sender: bool = False) :
        """
        Notify the user of the availability of funds. sender is whether the funds are released to the sender, defaulting to False,
        which releases to recipient
        """
        fee = str(escrow.estimatefee())
        message = (str(escrow.value) + " " + escrow.coin.upper() + " was released to you from the escrow with ID " + escrow.id + " You may withdraw the funds using `!withdraw [address]`." +
                  " If you wish to specify a custom feerate, you may do so by using `!withdraw [escrow ID] [address] [feerate]`.\n\n" +
                  "    ESCROW VALUE: " + str(escrow.value) + " " + escrow.coin.upper() + '\n' +
                  "    ESCROW FEE  : " + str(Decimal(config.escrowfee[escrow.coin])) + " " + escrow.coin.upper() + '\n' +
                  "    AVAILABLE   : " + str(escrow.value - Decimal(config.escrowfee[escrow.coin])) + ' ' + escrow.coin.upper() + '\n\n' +
                  "    RECOMMENDED NETWORK FEE: " + fee)
        if (escrow.coin in ['btc', 'ltc', 'bch']) :
            message += " sat/B\n\n**Note:** You don't have to use the suggested network fee on BTC. You can specify however high (or low) of a fee as you want."
            message += " However, if you choose not to specify a feerate, the suggested feerate will be used, which may be different at the time of withdrawal than it is now."
        elif (escrow.coin == "eth") :
            message += " gw/gas\n\n**Note:** Custom feerates are currently not supported on ETH. The suggested feerate will always be used. This is because the ETH network requires transactions be confirmed in order."
        elif (escrow.coin == "usdt") :
            message += " USDT\n\n**Note:** The escrow fee also covers the network fee."
        message += config.signature()
        if (sender) :
            r.redditor(escrow.sender).message("Funds available", message)
        else :
            r.redditor(escrow.recipient).message("Funds available", message)


def askpayment (escrow: crypto.Escrow) -> str :
        """
        Ask the sender to fund the escrow
        """
        #ETH is handled differently because it requires an identifier
        if (escrow.coin == "eth") :
            r.redditor(escrow.sender).message("Escrow funding address", "In order to fund the escrow with ID " + escrow.id + 
                                            ", please send " + str(escrow.value) + escrow.privkey + " " + escrow.coin.upper() +
                                            " to " + config.ethaddr + ".\n\n**IMPORTANT**: You must send _exactly_ this amount, after network fees. If too little or too much is received," +
                                            " your payment will not be detected. If you accidentally sent the wrong amount, please reach out to us for help!" + config.signature())
            return
        elif (escrow.coin == "usdt") :
            r.redditor(escrow.sender).message("Escrow funding address", "In order to fund the escrow with ID " + escrow.id + 
                                            ", please send " + str(escrow.value) + " " + escrow.coin.upper() +
                                            " to " + config.tronaddr + "\n\n**IMPORTANT**: This is a TRON address. Do not send USDT ERC-20 or USDT BEP-20. " +
                                            "Sending any coin other than USDT TRC-20 will result in loss of funds. You must send _exactly_ this amount. " +
                                            "If you accidentally send too little or too much, please reach out to us for help!")
            return
        r.redditor(escrow.sender).message("Escrow funding address", "In order to fund the escrow with ID " + escrow.id + " please send " + str(escrow.value) + " " + escrow.coin.upper() +
                                        " to " + escrow.getaddress() + "\n\n**Note:** If you send crypto and the bot is not recognising it, please make sure you sent the correct amount." +
                                        " Verify that the amount the bot received *after network fees* is equal to or greater than " + str(escrow.value) + " " + escrow.coin.upper() +
                                        ". If you accidentally sent too little (or your wallet deducted a network fee from the total), you may send another transaction to cover the difference." +
                                        " If you know that your wallet deducts the network fee from the total, you can send a little bit more crypto than requested to mitigate this."
                                        + config.signature())
        