#Robo_bobo_bot
# TODO:
# !topbits
# allow for channel points to request a song
# banned words filter: if a user says a banned word, then robo bobo will ban them from the chat
# Shoutout @name to say thanks etc.
# Use custom reward API to do song requests?
#To run the bot, click the green run button on the top right 

import os
import sys
import pickle
import json
from dotenv import load_dotenv
import random
#twitch bot imports
import irc.bot
from pip._vendor import requests
#imports to process time and current uptime
from datetime import datetime
from dateutil import parser
from dateutil import tz
#import separate youtube module for playlists
from youtube import yt_Module
from helper import helper_Module as hp

#API scopes
TW_SCOPES = ['channel:edit:commercial','channel:manage:redemptions','channel:read:redemptions','channel:manage:polls','channel:manage:predictions']
#TW_SCOPES = ['']

#discord join link
DISCORD_LINK = 'https://discord.gg/Za5ngC9QsE'

#some necessary functions to allow for pyinstaller (it's a bug with requests)
def override_where():
    """ overrides certifi.core.where to return actual location of cacert.pem"""
    # change this to match the location of cacert.pem
    return os.path.abspath("cacert.pem")

# is the program compiled?
if hasattr(sys, "frozen"):
    import certifi.core

    os.environ["REQUESTS_CA_BUNDLE"] = override_where()
    certifi.core.where = override_where

    # delay importing until after where() has been replaced
    import requests.utils
    import requests.adapters
    # replace these variables in case these modules were
    # imported before we replaced certifi.core.where
    requests.utils.DEFAULT_CA_BUNDLE_PATH = override_where()
    requests.adapters.DEFAULT_CA_BUNDLE_PATH = override_where()

class RoboBoboBot(irc.bot.SingleServerIRCBot):
    def tw_authentication(self):
        #check if previously given access token is stored
        if os.path.exists(self.name+'/tw_token.pickle'):
            print('Loading Twitch Access Token From File...')
            with open(self.name+'/tw_token.pickle', 'rb') as token:
                try:
                    self.token, self.refresh_token = pickle.load(token)
                except:
                    self.reAuthenticate()
            if self.refresh_token == None or self.token == None:
                self.reAuthenticate()
            #once we got the previously gotten token, send a validation request to twitch to see if its still active
            self.validateToken()
        else:
            self.refreshToken()
            self.validateToken()
    
    def reAuthenticate(self):
        print('Follow link: ')
        url = 'https://id.twitch.tv/oauth2/authorize?client_id='+self.client_id+'&redirect_uri=http://localhost&response_type=code&scope='+self.req_scopes
        print(url)
        auth_code = input('Enter Authorization Code')
        url = 'https://id.twitch.tv/oauth2/token?client_id='+self.client_id+'&client_secret='+os.getenv('TWITCH_CLIENT_SECRET')+'&code='+auth_code+'&grant_type=authorization_code&redirect_uri=http://localhost'
        r = requests.post(url).json()
        if 'access_token' in r and 'refresh_token' in r:
            self.token = r['access_token']
            self.refresh_token = r['refresh_token']
            print('New Twitch Access Token Granted')

            # Save the credentials for the next run
            with open(self.name+'/tw_token.pickle', 'wb') as f:
                print('Saving Twitch Credentials for Future Use...')
                pickle.dump([self.token, self.refresh_token], f)
        else: #if failed, exit
            print('Reauthentication failed')
            exit()
    #if token is expired, request a new token using the refresh token
    def refreshToken(self):
        if self.refresh_token == None or self.token == None:
            self.reAuthenticate()
        else:
            url = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token='+self.refresh_token+'&client_id='+self.client_id+'&client_secret='+os.getenv('TWITCH_CLIENT_SECRET')+'&scope='+self.req_scopes
            r = requests.post(url).json()
            print(r)
            #if the scope in the current access token is not the same as the requested scopes, reauthenticate
            if 'scope' in r and r['scope'] != TW_SCOPES:
                self.reAuthenticate()
            elif 'access_token' in r and 'refresh_token' in r:
                self.token = r['access_token']
                self.refresh_token = r['refresh_token']
                print('New Twitch Access Token Granted')

                # Save the credentials for the next run
                with open(self.name+'/tw_token.pickle', 'wb') as f:
                    print('Saving Twitch Credentials for Future Use...')
                    pickle.dump([self.token, self.refresh_token], f)
            else: #if failed, exit
                print('Refresh request failed')
                exit()

    #for validating the token
    def validateToken(self):
        print('Validating OAuth Token...')
        headers = {'Authorization': 'OAuth %s' %(self.token)}
        r = requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
        print(r.json())
        #if the response from the validation request is not 200, then refresh the access token and validate again
        if not(r.ok):
            print('Oauth Token not valid')
            self.refreshToken()
            self.validateToken()
        else:
            self.channel = '#'+r.json()['login']
            self.channel_id = r.json()['user_id']

    def __init__(self, input_name = 'rohan'):
        #load env stuff
        load_dotenv()
        self.username = 'robo_bobo_bot'
        self.death_counter = 0
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.channel_id = None
        self.channel = None
        self.name = input_name

        #time vars
        self.last_hourly_check = datetime.now(tz.UTC)
        self.last_ad_run = datetime.now(tz.UTC)
        self.start_time = None

        #giveaway trackers
        self.giveaway_entries = []
        self.giveaway_on = False

        #dict to store simple commands, with loading
        if not(os.path.isdir(self.name)):
            os.mkdir(self.name)
        if os.path.exists(self.name+'/cmds.pickle'):
            print('Loading Commands From File...')
            with open(self.name+'/cmds.pickle', 'rb') as token:
                self.cmds = pickle.load(token)
            print('Loaded Commands: ' + ', '.join(map(str, list(self.cmds.keys()))))
        else:
            self.cmds = {}

        # Create Youtube Playlist Manager for itself
        self.yt = yt_Module.YoutubePlaylistManager()

        # Authenticate through Twitch
        self.req_scopes = hp.concatenateArgs(TW_SCOPES, 0, '%20')
        self.token = None
        self.refresh_token = None
        self.tw_authentication()

        # Create IRC bot connection
        server = 'irc.chat.twitch.tv'
        port = 6667
        print('Connecting to ' + server + ' on port ' + str(port) + '...')
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+os.getenv('BOT_OAUTH_TOKEN'))], self.username, self.username)

    
    # def repeatMsg(self, message, arg_length = 1):
    #     c = self.connection
    #     if int(arg_length) > 5:
    #         length = 5
    #     else:
    #         length = int(arg_length)
    #     for _ in range(0, length):
    #         c.privmsg(self.channel, message)
    
    #allows for detection of bigfollows and tries to ban the user
    def spamDetection(self, message, name):
        c = self.connection
        if 'bigfollows' in message:
            c.privsmsg(self.channel, '/ban %s' %(name))

    #if the cmd is within the split list, return the key for that item
    def findExistingCmd(self, cmd):
        #split the existing commands into a list (ex: if !cmd add song/songs/youtube <...>,
        #then searchList = [song, songs, youtube])
        searchList = cmd.split('/')
        #search for each term in the cmd list (out of existing commands)
        for i in range(0, len(self.cmds)):
            #split the i'th command into its parts
            cmdList = list(self.cmds.keys())[i].split('/')
            #for each term in the searchList, and try to find it in cmdList
            for j in range(0, len(searchList)):
                if cmd in cmdList:
                    return list(self.cmds.keys())[i]
                    print(self.cmds)
        #if nothing was found, raise an exception
        raise Exception('Command Not Found')

    def runAd(self, req_length):
        c = self.connection
        if req_length != None: #round their given length
            length = req_length.split(' ')[0]
            try:
                length = round(int(length)/30)*30 #div by 30 then round to nearest number, then *30 to get multiple of 30 length
                if length > 180: #if length is greater than max length (3 mins), then set to 3 mins
                    length = 180
            except:
                c.privmsg(self.channel, 'Please input a valid ad length')
                return
        url = 'https://api.twitch.tv/helix/channels/commercial' 
        headers = {'Client-Id': self.client_id, 'Content-Type': 'application/json',  'Authorization': 'Bearer ' + self.token}
        raw_data = '{ "broadcaster_id": "%s", "length": %d }' %(self.channel_id, length)
        r = requests.post(url, data=raw_data, headers=headers)
        if(r.ok):
            length = r['data'][0]['length']
            c.privmsg(self.channel, 'Running a %d sec ad' %length) 
        else:
            c.privmsg(self.channel, 'Ad failed :(')

    def on_welcome(self, c, e):
        print('Joining ' + self.channel)
        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        current_time = datetime.now(tz.UTC)
        #find the time difference, the difference would be a HH:MM:SS string, so split it by ':' to get a HH, MM, SS list.
        hour_difference = str(current_time - self.last_hourly_check).split(':')
        time_since_last_ad = str(current_time - self.last_ad_run).split(':')
        #get difference[0] would be hours, [1] = minutes, [2] = seconds
        if int(hour_difference[0]) > 1:
            self.validateToken()
            c.privmsg(self.channel, 'Join the xRohanTV community discord at: ' + DISCORD_LINK)
            self.last_hourly_check = current_time
        if int(time_since_last_ad[1]) > 45: #if it's been 45 minutes since last ad was run, run a 60 sec ad.
            self.runAd('60')

        mod = False
        #get the name of the chatter
        name = e.source.split('!')[0]
        # If a chat message starts with an exclamation point, try to run it as a command
        if e.arguments[0][:1] == '!':
            if len(e.arguments[0].split(' ')) > 1: #if multi-phrase commmand (ex: !ad 30)
                args = e.arguments[0].split(' ')[1:]
                args[0] = args[0].lower() #convert first arg to lowercase
            else:
                args = None
            cmd = e.arguments[0].split(' ')[0][1:]
            #check if user is a mod
            for _, value in e.tags[-1].items():
                if value == 'mod' or name == self.channel[1:]:
                    mod = True
            if args != None:
                print('Received command: ' + cmd + ' ' + args[0])
            else:
                print('Received command: ' + cmd)
            #convert cmd to lowercase
            cmd = cmd.lower()
            self.do_command(e, cmd, args, mod, name)

        #allow for simple commands without '!' prefix
        elif e.arguments[0].lower() == 'f':
            c.privmsg(self.channel, 'Press F to pay respects BibleThump')
        
        #call the spam detection function for every message
        self.spamDetection(e.arguments[0], name)
        return

    #cmd is the first word after !, and args is the 2nd word afterwords (ex: !ad 30, cmd = 'ad', args = 30)
    #mod is a bool on whether the one calling the command is a mod
    def do_command(self, e, cmd, args, mod, name):
        c = self.connection
        # Poll the API to get current game.
        if cmd == "game":
            url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + self.channel_id
            headers = {'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            try: #see if the request was successful
                r = r['data'][0]
            except:
                #if the request was not successful, refresh the token and rerun the command (is this dangerous?)
                print('Command Failed, Refreshing Token and Retrying')
                self.refresh_token()
                self.do_command(e, cmd, args, mod, name)
            c.privmsg(self.channel, r["broadcaster_name"] + ' is currently playing ' + r['game_name'] + '.')

        # Poll the API the get the current status of the stream
        elif cmd == "title":
            url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + self.channel_id
            headers = {'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            try: #see if the request was successful
                r = r['data'][0]
            except:
                #if the request was not successful, refresh the token and rerun the command (is this dangerous?)
                self.refresh_token()
                self.do_command(e, cmd, args, mod, name)
            c.privmsg(self.channel, r['broadcaster_name'] + ' channel title is currently ' + r['title'] + '.')

        #death counter commands
        elif cmd == "deaths" or cmd == 'death':
            if args == None:
                message = self.name + " has died %d times. What a loser!" %int(self.death_counter)
                c.privmsg(self.channel, message)
            elif args[0] == 'help':
                c.privmsg(self.channel, '!death will provide the current death count, and mods can do !death +/-/set <#>/reset to change the current count')
            elif args[0] == "+" or args[0] == 'add':
                if mod:
                    self.death_counter = self.death_counter+1
                    if self.death_counter == 69:
                        message = self.name + " died 69 times. Nice"
                    else:
                        message = self.name + " just died. That's death #%d. What a loser!" %int(self.death_counter)
                    c.privmsg(self.channel, message)
            elif args[0] == "-" or args[0] == 'undo':
                if mod:
                    self.death_counter = self.death_counter - 1
            elif args[0] == 'set':
                if mod:
                    try: #test for a valid input
                        self.death_counter = int(args[1])
                        message = "That's death #%d. What a loser!" %int(self.death_counter)
                        c.privmsg(self.channel, message)
                    except:
                        c.privmsg(self.channel, 'Please input a value to set to')
            elif args[0] == 'reset':
                    self.death_counter = 0
                    c.privmsg(self.channel, 'Death counter reset')

        #run an ad
        elif cmd == "ad":
            if mod:
                if args == None:
                    self.runAd('60')
                elif args[0] == 'help':
                    c.privmsg(self.channel, '(Mod Only) Send !ad <length> to request an ad. Length can be 30/60/90/120/150/180.')
                else:
                    self.runAd(args)
                    
            else:
                c.privmsg(self.channel, 'This is a mod only command')

        #Youtube Playlist Queue
        elif cmd == 'songs' or cmd == 'song':
            if args == None or args[0] == 'link' or args[0] == 'playlist': #check for empty request: !songs to provide the link
                c.privmsg(self.channel, 'Listen along at https://www.youtube.com/playlist?list=PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf')
            elif args[0] == 'help':
                c.privmsg(self.channel, 'To request a song, use the song request channel points reward and type: "!song request <link or song name>"')
            elif args[0] == 'play' or args[0] == 'request' or args[0] == 'queue':
                response = self.yt.parseSongRequest(args)
                c.privmsg(self.channel, response)
            elif args[0] == 'delete': #params: position, deletes the song at pos
                if mod:
                    response = self.yt.deleteSong(args)
                    c.privmsg(self.channel, response)
            elif args[0] == 'ban':      
                if mod:
                    response = self.yt.banSong(args)
                    c.privmsg(self.channel, response)

        #Raffle or Giveaway system
        elif cmd == 'raffle' or cmd == 'giveaway':
            #TODO: Implement channel points/bits to increase chances
            if args == None:
                if self.giveaway_on and not(name in self.giveaway_entries): #if a giveaway is running, and they are already not already entered
                    self.giveaway_entries.append(name) #add that name to an array
            elif args[0] == 'help':
                c.privsmsg(self.channel, '(mod only) To start a giveaway, send !giveaway start. To finish it, send !giveaway end, and the winner will be chosen.')
            elif args[0] == 'start' or args[0] == 'begin':
                if mod and self.giveaway_on == False:
                    self.giveaway_on = True
                    self.giveaway_entries = []
                    c.privmsg(self.channel, 'The giveaway has started! Chat !giveaway to enter!!!')
            elif args[0] == 'end':
                if mod and self.giveaway_on:
                    print(self.giveaway_entries)
                    winner = random.randint(0, len(self.giveaway_entries) - 1)
                    c.privmsg(self.channel, 'The winner is: ' + self.giveaway_entries[winner] + "! Congratulations")
                    self.giveaway_on = False
                    self.giveaway_entries = []
            
        #plug discord server
        elif cmd == 'discord' or cmd == 'socials':
            c.privmsg(self.channel, 'Join the xRohanTV community discord at: ' + DISCORD_LINK)

        #find current uptime
        elif cmd == 'uptime':
            url = 'https://api.twitch.tv/helix/search/channels?query='+self.channel[1:]
            headers = {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            index = -1
            for i in range(0, len(r['data']) - 1):
                if r['data'][i]['broadcaster_login'] == self.channel[1:]:
                    index = i
                    break
            if index != -1 and r['data'][index]['started_at'] != "" : #check if started at is empty (Rohan isn't streaming), if index = -1, then it couldn't find xRohanTV
                self.start_time = parser.parse(r['data'][index]['started_at'])
                current_time = datetime.now(tz.UTC)
                time_difference = str(current_time - self.start_time).split(':')
                hours = time_difference[0]
                minutes = time_difference[1]
                seconds = time_difference[2][0:2]
                c.privmsg(self.channel, self.name + "'s been running for " + hours + ' hours, ' + minutes + ' minutes, and ' + seconds + ' seconds.')
            else:
                c.privmsg(self.channel, 'Channel is not live')

        #toss a coin
        elif cmd == 'coin' or cmd == 'coins':
            flip = random.randint(0,1)
            if flip == 1:
                c.privmsg(self.channel, "It's Heads!")
            else:
                c.privmsg(self.channel, "It's Tails!")
        
        #toss a dice
        elif cmd == 'dice':
            if args == None:
                sides = 6
            elif args[0] == 'help':
                c.privmsg(self.channel, "To use, send !dice <number of sides>. If no number is given, it'll default to a 6 sided die")
                return
            else:
                try:
                    sides = int(args[0])
                except:
                    c.privmsg(self.channel, 'Please provide valid number of sides')
                    return
            num = random.randint(1, sides)
            c.privmsg(self.channel, "It's " + str(num))

        #simple commands add/edit/delete
        elif cmd == 'cmd' or cmd == 'cmds':
            if args == None:
                return
            elif args[0] == 'help':
                c.privmsg(self.channel, 'To add or edit commands, type !cmd add/edit <command_name/alt_name> <command response>. Note: Command names must be 1 word.')
                c.privmsg(self.channel, "To delete a command, type !cmd delete <command_name>. It'll also delete any alt names for that command.")
                c.privmsg(self.channel, "Type !cmd list to get a list of the current simple commands.")

            #list out current commands
            elif args[0] == 'list':
                c.privmsg(self.channel, 'Current custom commands are: ' + ', '.join(map(str, list(self.cmds.keys()))))

            #add a new command
            elif args[0] == 'add' or args[0] == 'edit':
                if len(args) >= 3 and mod == True:
                    #args[1] is the name of the cmd so it should be converted to lowercase
                    args[1] = args[1].lower()

                    try:
                        #use helper function to find if given search term is part of an existing command
                        existingCmd = self.findExistingCmd(args[1])
                        #if it is, then update that dict value with the concatenated command response
                        self.cmds[existingCmd] = hp.concatenateArgs(args, 2)
                        c.privmsg(self.channel, '!' + existingCmd + ' has been updated.')
                    except:
                        #if it's not an existing command (Exception raised by findExistingCmd), then add it to the dict
                        self.cmds[args[1]] = hp.concatenateArgs(args, 2)
                        c.privmsg(self.channel, '!' + args[1] + ' has been added.')
                else:
                    print('Invalid Request/ Not a mod')

            #delete an existing command
            elif args[0] == 'delete':
                if len(args) >= 2 and mod == True:
                    #args[1] is the name of the cmd so it should be converted to lowercase
                    args[1] = args[1].lower()
                    try:
                        #use helper function to find if given search term is part of an existing command
                        existingCmd = self.findExistingCmd(args[1])
                        #if it is, then pop the command
                        self.cmds.pop(existingCmd)
                        c.privmsg(self.channel, '!' + existingCmd + ' has been deleted')
                    except:
                        #if it's not an existing command (Exception raised by findExistingCmd)
                        c.privmsg(self.channel, '!' + args[1] + ' is not an existing command.')
                else:
                    print('Invalid Request/ Not a mod')

            # Save the commands for the next run
            with open(self.name + '_cmds.pickle', 'wb') as f:
                print('Saving Commands for Future Use...')
                pickle.dump(self.cmds, f)

        else:
            try:
                print('Searching for existing command: ' + cmd)
                existingCmd = self.findExistingCmd(cmd)
                print('Found existing cmd: ' + existingCmd)
                cmdResponse = self.cmds.get(existingCmd)
                c.privmsg(self.channel, cmdResponse)
            except:
                print("Did not understand command: " + cmd)

        # obsolete custom commands
        # elif cmd == 'defeat':
        #     c.privmsg(self.channel, 'Hesitation is Defeat')
        # elif cmd == 'robert':
        #     c.privmsg(self.channel, "ROBERTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT!!!!!!!!!!!!!!!!!!")
        # elif cmd == 'plague':
        #     message = 'Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper'
        #     self.repeatMsg(message, args[0])
        # elif cmd == 'BOBO':
        #     message = 'xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO '
        #     self.repeatMsg(message, args[0])

def main():
    if len(sys.argv) > 1:
        name = sys.argv[1].lower()
        bot = RoboBoboBot(name)
    else:
        bot = RoboBoboBot()
    bot.start()

if __name__ == '__main__':
    main()