##################################
#   Zeelsterstraat telegram bot
#         Jasper de Graaf
#         September 2020
#              V0.62
############# IMPORTS #############

from dotenv import find_dotenv, load_dotenv
import os
from bs4 import BeautifulSoup
import telepot
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply
import time
import json
import unidecode
from datetime import datetime, timedelta, date
from urllib import request, parse
import schedule
import pandas as pd
import ast
from random import randrange, choice
from pytz import timezone

############# GEHEIME DINGEN ##################
load_dotenv(find_dotenv('.env'))
ZEELSTER_TELEGRAM_SECRET = os.environ['ZEELSTER_TELEGRAM_SECRET']
ZEELSTER_TELEGRAM_GROUP = int(os.environ['ZEELSTER_TELEGRAM_GROUP'])
ZEELSTER_EETLIJST_WACHTWOORD = os.environ['ZEELSTER_EETLIJST_WACHTWOORD']

############# EXTRA FUNCTIES ##################

def getBoodschappenList():
    text = ""
    with open("boodschappen.json", "r") as f:
        boodschappen = json.load(f)
        for boodschap in boodschappen:
            text += "- " + boodschap + "\n"
    if text == "":
        text = "De boodschappenlijst is leeg"
    return text

def addToBoodschappenList(item):
    if item != "":
        boodschappen = None
        with open("boodschappen.json", "r") as f:
            boodschappen = json.load(f)
            # Skip if the item is already on the list
            for boodschap in boodschappen:
                if boodschap == item:
                    return False
        boodschappen.append(item)
        with open("boodschappen.json", "w") as f:
            json.dump(boodschappen, f)
    return True

def removeFromBoodschappenList(item):
    boodschappen = None
    flag = False
    with open("boodschappen.json", "r") as f:
        boodschappen = json.load(f)
    with open("boodschappen.json", "w") as f:
        try:
            boodschappen.remove(item)
            flag = True
        except ValueError:
            pass
        json.dump(boodschappen, f)
    return flag

def gooiMex(chat_id, fname):
    throw_1 = randrange(1,7)
    throw_2 = randrange(1,7)
    if throw_1 == throw_2:
        score = str(throw_1*100)
    elif throw_1 > throw_2:
        score = str(throw_1)+str(throw_2)
    else:
        score = str(throw_2)+str(throw_1)
    if score == "21":
        text = "{:s} heeft {:s} en {:s} gegooid!\nJe hebt Mexx gegooid!!".format(fname, str(throw_1), str(throw_2))
    elif score == "600":
        text = "{:s} heeft {:s} en {:s} gegooid!\nJe score is {:s} dus je bent de Ombudsman\nJe moet drinken bij elk honderdtal!".format(fname, str(throw_1), str(throw_2), score)
    else:
        text = "{:s} heeft {:s} en {:s} gegooid!\nJe score is {:s}!!".format(fname, str(throw_1), str(throw_2), score)
    sendText(chat_id, text)
    return

############# EETLIJST CODE ###################

def getDayCode(soup):
    font_1 = soup.find_all("font", size="1")
    code_str = str(font_1[0].find('a'))
    daycode = code_str[code_str.find("(")+1 : code_str.find(")")]
    return daycode

# Open a session on eetlijst.nl
def openSession():
    global sessionID, sessionURL
    if sessionID == 0:
        payload = {'login': 'zbeneden', 'pass': ZEELSTER_EETLIJST_WACHTWOORD}
        url = 'http://eetlijst.nl/login.php'
        data = parse.urlencode(payload).encode()
        req =  request.Request(url, data=data)
        sessionURL = request.urlopen(req).geturl()
        sessionID = request.urlopen(req).geturl().split('=')[1]
        return sessionURL, sessionID
    else:
        return sessionURL, sessionID

# Get the HTML
def getSoup(url): 
    return BeautifulSoup(request.urlopen(request.Request(url)).read(), 'html.parser')

# Get current day for webcrawl
def getThisDay():
    weekdays = ['ma', 'di', 'wo', 'do', 'vr', 'za', 'zo']
    return str(str(weekdays[datetime.now().weekday()]) + ' ' + str(datetime.now().day) + '-' + str(datetime.now().month))

# Function that reads all eters on eetlijst
def getEtersOpEetlijst(soup):
    eters = []
    for item in soup.find_all('b')[1:-1]:
        eters.append(item.get_text())
    return eters

# Function that reads every meeeter
def getEtersOfDay(soup, inputday):
    counter = 0
    eters = []
    class_r = soup.find_all("td", class_="r") + soup.find_all("td", class_="rblur")
    for item in class_r:
        days = item.find_all("nobr")
        for day in days:
            if inputday in day.get_text():
                dayrow = day.find_parent().find_parent()
                for column in dayrow:
                    # If the column has eet.gif or kook.gif, the person is a meeeter
                    if 'eet.gif' in str(column) or 'kook.gif' in str(column):
                        for img in column.find_all('img'):
                            # Get name of eter
                            eters.append(img['title'].split(' ')[0])
                            # Increment counter
                            counter = counter+1
    return counter, eters

# Function that reads the kok of the day
def getKok(soup, inputday):
    class_r = soup.find_all("td", class_="r") + soup.find_all("td", class_="rblur")
    for item in class_r:
        days = item.find_all("nobr")
        for day in days:
            if inputday in day.get_text():
                dayrow = day.find_parent().find_parent()
                for column in dayrow:
                    if 'kook.gif' in str(column):
                        return str(column.find('img')['title'].split()[0])+" kookt vandaag"
                return 'Er staat nog niemand op koken'

# Function to change the status on eetlijst
def inschrijfRequest(code, number, daycode):
    global sessionID
    url = 'http://eetlijst.nl/k.php?sess='+str(sessionID)+'&day='+daycode+'&who='+str(number)+'&what='+str(code)
    req =  request.Request(url)
    request.urlopen(req)
    return

#################### SCHEDULE JOB ########################



##################### TELEPOT CODE ##########################

def sendNotifyToday(info, chat_id):
    # Initialize empty message
    text = ""
    pinflag = False
    # Add info to message from file
    for item in info:
        if len(item) != 2:
            if item == "r":
                text += "Het restafval moet buiten vandaag\n"
            elif item == "g":
                text += "Het GFT moet buiten vandaag\n"
            elif item == "p":
                text += "Het papier en karton moet buiten vandaag\n"
        elif len(item) == 2:
            pinflag = True
            if item[0] == "Pv":
                text += "{:s} moet het sanitair voor poetsen\n".format(str(item[1]))
            if item[0] == "Pa":
                text += "{:s} moet het sanitair achter poetsen\n".format(str(item[1]))
            if item[0] == "Pk":
                text += "{:s} moet de keuken poetsen\n".format(str(item[1]))
            if item[0] == "Pb":
                text += "{:s} moet het sanitair boven poetsen\n".format(str(item[1]))
            if item[0] == "Bd":
                Bd_text = "Namens het hele huis, van harte gefeliciteerd met je verjaardag {:s}!".format(str(item[1]))
                schedule.every().day.at('10:30').do(sendText, chat_id, Bd_text, True)

    # Send message (if not empty)
    if text != "":
        # Send message
        sendmsg = bot.sendMessage(chat_id, text)
        # Get current chat status (including if message is pinned)
        chat_status = bot.getChat(chat_id)
        # If message is pinned
        if pinflag and "pinned_message" in chat_status:
            # Unpin old
            bot.unpinChatMessage(chat_id)
            # Pin new
            bot.pinChatMessage(chat_id, sendmsg['message_id'], disable_notification=True)
        # If no message is pinned
        elif pinflag and not "pinned_message" in chat_status:
            # Pin new
            bot.pinChatMessage(chat_id, sendmsg['message_id'], disable_notification=True)
        return
    else:
        return

def sendText(chat_id, text, once=False):
    bot.sendMessage(chat_id, text)
    # Remove daily job, it will only execute once
    if once:
        return schedule.CancelJob
    else:
        return

# Receive message and print
def on_message(client, userdata, message):
    print("Message received: {received}".format(received = str(message.payload.decode("utf-8"))))
    return

# Message handler function
def handle(msg):
    global group_chat_id
    global chat_id
    # Chat ID is a unique ID for every telegram chat
    chat_id = msg['chat']['id']
    # The actual message of the sender
    command = msg.get('text', '')
    # Get first name of sender
    fname = msg['from']['first_name']
    # Remove weird chars from name so it matches the ancient code of eetlijst
    fname = unidecode.unidecode(fname)

    if len(command) > 0:
        # Check if chat_id is part of zeelsterstraat group chat to provide access to private bot chat
        try: 
            groupchatmember = bool(bot.getChatMember(group_chat_id, chat_id))
        except: 
            groupchatmember = False

        if (chat_id == group_chat_id or groupchatmember == True) and command[0] == "/":
            # Act on commands
            if command[0:5] == '/Heey': 
                bot.sendMessage(chat_id, 'Alloah')

            elif command[0:5] == "/yeet":
                text = ["Yeet your skeet & beat your meat"]
                bot.sendMessage(chat_id, text[0])

            elif command[0:5] == "/mexx":
                gooiMex(chat_id, fname)
            
            elif command[0:13] == "/uitschrijven":
                # Open session on eetlijst.nl
                [url, ID] = openSession()
                # Get HTML things
                soup = getSoup(url)
                # Get number of user on eetlijst
                number = getEtersOpEetlijst(soup).index(fname)
                # Get code of this day
                daycode = getDayCode(getSoup(url))
                # Perform request
                inschrijfRequest(1, number, daycode)
                inschrijfRequest(0, number, daycode)
                inschrijfRequest(-5, number, daycode)
                bot.sendMessage(chat_id, "{:s} is uitgeschreven voor vandaag".format(fname))

            elif command[0:12] == "/inschrijven":
                # Open session on eetlijst.nl
                [url, ID] = openSession()
                # Get HTML things
                soup = getSoup(url)
                # Get number of user on eetlijst
                number = getEtersOpEetlijst(soup).index(fname)
                # Get code of this day
                daycode = getDayCode(getSoup(url))
                # Perform request
                inschrijfRequest(-1, number, daycode)
                bot.sendMessage(chat_id, "{:s} is ingeschreven voor vandaag".format(fname))

            elif command[0:6] == "/koken":
                # Open session on eetlijst.nl
                [url, ID] = openSession()
                # Get HTML things
                soup = getSoup(url)
                # Get number of user on eetlijst
                number = getEtersOpEetlijst(soup).index(fname)
                # Get code of this day
                daycode = getDayCode(getSoup(url))
                # Perform request
                kok = getKok(soup, getThisDay())
                if kok == 'Er staat nog niemand op koken':
                    inschrijfRequest(-1, number, daycode)
                    inschrijfRequest(1, number, daycode)
                    bot.sendMessage(chat_id, "{:s} kookt vandaag".format(fname))
                else:
                    bot.sendMessage(chat_id, "{:s} al, maar jij kan morgen misschien wel koken!".format(kok))

            elif command[0:20] == "/ishetaltijdvoorbier":
                bot.sendMessage(chat_id, "Water is pas een feest als het langs de brouwer is geweest!")

            elif command[0:4] == "/'Vo" or command[0:4] == "/‘Vo":
                text_arr = ["'Vo voor de praeses!", "Hé Lullo, nog geneukt?", "Ad fundum", "Anti'Vo, Lul", "Goed man lul", "Ga een behoorlijke baan zoeken man!", "Kom dan {:s}".format(fname)]
                randint = randrange(len(text_arr))
                bot.sendMessage(chat_id, text_arr[randint])

            elif command[0:6] == '/eters':
                [url, ID] = openSession()
                soup = getSoup(url)
                # Get number and names of eters
                nof_eters, eters = getEtersOfDay(soup, getThisDay())
                # Create text message
                text = "Er eten {:d} mensen mee\n{:s}".format(nof_eters, ", ".join([str(x) for x in eters]))
                bot.sendMessage(chat_id, text)

            elif command[0:4] == '/kok':
                [url, ID] = openSession()
                soup = getSoup(url)
                bot.sendMessage(chat_id, getKok(soup, getThisDay()))

            elif command[0:13] == '/boodschappen':
                currentlist = getBoodschappenList()
                bot.sendMessage(chat_id, currentlist)

            elif command[0:17] == '/voegboodschaptoe':
                item = command[18:]
                if addToBoodschappenList(item):
                    bot.sendMessage(chat_id, "{:s} is toegevoegd aan de boodschappenlijst!".format(str(item)))
                else: 
                    bot.sendMessage(chat_id, "Die staat er al op, lul.")

            elif command[0:19] == '/verwijderboodschap':
                item = command[20:]
                if removeFromBoodschappenList(item):
                    bot.sendMessage(chat_id, "{:s} is verwijderd van de boodschappenlijst!".format(str(item)))
                else:
                    text = "Die staat er helemaal niet op. Beter typen, kneus.\nKies uit de volgende items:\n"
                    text += getBoodschappenList()
                    bot.sendMessage(chat_id, text)

            else:
                bot.sendMessage(chat_id, "Ik versta d'r geen kloot van.")
        else:
            return
    else:
        return

def get_koffie_woord():
    return choice([
        "koffie",
        "café",
        "een bakkie pleur",
        "het zwarte goud",
        "een bakkie leut",
        "een bakkie troost",
        "咖啡",
        "een bakkie slobber",
        "een bakkie prut",
        "een dosis levenselixer",
        "een meestal warm genuttigde drank, die wordt bereid op basis van water en gedroogde en gebrande pitten van de koffieplant (Coffea spp.) die vanwege hun vorm koffiebonen worden genoemd. Koffie bevat het stimulerende middel cafeïne. De meeste soorten in het geslacht Coffea komen van nature voor in tropisch Afrika en op de eilanden in de Indische Oceaan. Ze vinden hun oorsprong in Ethiopië, Jemen en Soedan."
    ])


def send_koffie_bericht():
    sendText(group_chat_id, "☕ Tijd voor " + get_koffie_woord() + "!")
    return schedule.CancelJob


def schedule_koffie_bericht():
    nl_dt = timezone('Europe/Amsterdam').localize(datetime(2020, 10, 12, 11, 0, 0, 0))
    utc_dt = timezone('UTC').normalize(nl_dt)
    scheduler_time = utc_dt.isoformat().split('T')[1].split('+')[0]
    schedule.every().day.at(scheduler_time).do(send_koffie_bericht)

###################### LOOP ################################
# Global group_chat ID
group_chat_id = ZEELSTER_TELEGRAM_GROUP

# Initialize Telegram bot
bot = telepot.Bot(ZEELSTER_TELEGRAM_SECRET) 
bot.message_loop(handle)

# Initialize some flags
sessionID = 0
sessionURL = 0
increment = 0

# Initialize scheduled job
# schedule.every().day.at("07:30").do(dailyJob, group_chat_id)
# schedule.every().day.at("11:00").do(sendText, group_chat_id, "☕ Tijd voor " + get_koffie_woord() + "!")
schedule.every().day.at("08:00").do(schedule_koffie_bericht)

# sendText(group_chat_id, "Houzee! De chatbot leeft weer!")

# Open while loop for receiving messages
while 1:
    try:
        time.sleep(50)
        increment = increment+1
        schedule.run_pending()
        # Some fix for sessions on eetlijst.nl
        if increment == 2:
            sessionID = 0
            sessionURL = 0
            increment = 0
    except Exception as ಠ_ಠ: 
        print(ಠ_ಠ)