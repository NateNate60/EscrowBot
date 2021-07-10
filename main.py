from reddit import checkinbox
import crypto
import reddit
from database import Database, monitorpayment
import config
import praw


def main () :
    r = praw.Reddit(username = config.username, password = config.password, client_id = config.client_id, client_secret = config.client_secret, user_agent = "Nate'sEscrowBot")
    db = Database()
    elist = db.read()
    try :
        while (True) :
            elist += reddit.checkinbox(r, db)
            elist = monitorpayment(r, elist, db)

    except (Exception, KeyboardInterrupt) as e:
        print (e)
        db.db.close()

if (__name__ == '__main__') :
    main()