#Robo_bobo_bot
#TODO:
# !topbits
# allow for channel points to request a song

#To run the bot, click the green run button on the top right 

import os
import sys
import pickle
from dotenv import load_dotenv
import random
#twitch bot imports
import irc.bot
from pip._vendor import requests
#imports to process time and current uptime
from datetime import datetime
from dateutil import parser
from dateutil import tz
#youtube imports 
import urllib.parse as urlparse
#Google API imports for youtube playlist requests
from google.auth.transport.requests import Request
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

#youtube scopes
yt_scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
tw_scopes = '&channel:edit:commercial%20channel:manage:redemptions'

#discord join link
discord_link = 'https://discord.gg/Za5ngC9QsE'

class RoboBoboBot(irc.bot.SingleServerIRCBot):
    #conduct youtube authorization and return a youtube object to conduct calls with
    #the credentials are not stored as a class var (only local var) for safety and are deleted after initialization
    def yt_authorization(self):
        #check if a pickle exists with the token
        if os.path.exists('yt_token.pickle'):
            print('Loading Youtube Credentials From File...')
            with open('yt_token.pickle', 'rb') as token:
                yt_credentials = pickle.load(token)
        else:
            yt_credentials = None

        # If there are no valid credentials available, then either refresh the token or log in.
        if not yt_credentials or not yt_credentials.valid:
            if yt_credentials and yt_credentials.expired and yt_credentials.refresh_token:
                print('Refreshing Youtube Access Token...')
                yt_credentials.refresh(Request())
            else:
                print('Fetching New Tokens...')
                client_secrets_file = "client_id.json"
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, yt_scopes)
                flow.run_local_server(port=8080, prompt='consent',
                                    authorization_prompt_message='')
                yt_credentials = flow.credentials

                # Save the credentials for the next run
                with open('yt_token.pickle', 'wb') as f:
                    print('Saving Credentials for Future Use...')
                    pickle.dump(yt_credentials, f)

        api_service_name = "youtube"
        api_version = "v3"
        self.youtube = googleapiclient.discovery.build(api_service_name, api_version, credentials=yt_credentials)
    
    def tw_authentication(self):
        #check if previously given access token is stored
        if os.path.exists('tw_token.pickle'):
            print('Loading Twitch Access Token From File...')
            with open('tw_token.pickle', 'rb') as token:
                self.token = pickle.load(token)
            #once we got the previously gotten token, send a validation request to twitch to see if its still active
            self.validateToken()
        else:
            self.refresh_token()

    #if token is expired, request a new token using the refresh token
    def refresh_token(self):
        url = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token='+os.getenv('TW_REFRESH_TOKEN')+'&client_id='+self.client_id+'&client_secret='+os.getenv('TWITCH_CLIENT_SECRET')+'&scope='+tw_scopes
        r = requests.post(url).json()
        if 'access_token' in r:
            self.token = r['access_token']
            print('Access Token Granted')

            # Save the credentials for the next run
            with open('tw_token.pickle', 'wb') as f:
                print('Saving Credentials for Future Use...')
                pickle.dump(self.token, f)
        else: #if failed, exit
            print('Refresh request failed')
            exit()

    #for validating the token
    def validateToken(self):
        print('Validating OAuth Token')
        headers = {'Authorization': 'OAuth %s' %(self.token)}
        r = requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
        print(r.json())
        #if the response from the validation request is not 200, then refresh the access token and validate again
        if not(r.ok):
            self.refresh_token()
            self.validateToken()

    def __init__(self):
        #load env stuff
        load_dotenv()
        self.username = 'robo_bobo_bot'
        self.death_counter = 0
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.channel_id = os.getenv('XROHANTV_ID')
        self.channel = '#xrohantv'

        #time vars
        self.time_last_checked = datetime.now(tz.UTC)
        self.start_time = None

        #giveaway trackers
        self.giveaway_entries = []
        self.giveaway_on = False

        #list of songs in the playlist
        self.song_names = []
        self.song_ids = []
        self.banned_songs = []

        # Youtube Authentication
        self.yt_authorization()
        self.tw_authentication()

        # Create IRC bot connection
        server = 'irc.chat.twitch.tv'
        port = 6667
        print('Connecting to ' + server + ' on port ' + str(port) + '...')
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+os.getenv('BOT_OAUTH_TOKEN'))], self.username, self.username)

    #using the search term, search for the top result from youtube, and get it's song id and name, then add it to the queue
    def searchSong(self, search_term):
        request = self.youtube.search().list(part="snippet", maxResults=1, q=search_term)
        response = request.execute()  #request top result from youtube
        try:
            req_song_id = response['items'][0]['id']['videoId']
            song_name = response['items'][0]['snippet']['title'] 
        except:
            req_song_id = None
            song_name = None
        return song_name, req_song_id

    #using the song id, add it to the youtube playlist
    def queueSong(self, request_song_id):
        request = self.youtube.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": "PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf",
            "position": 100, #arbitrarily set position to 100 to add to end of playlist
            "resourceId": {
              "kind": "youtube#video",
              "videoId": request_song_id
            }
          }})
        response = request.execute()
        song_name = response['snippet']['title']
        print('Queueing song: ' + song_name)
        return song_name
    
    #update the bot's local list of songs
    def updateSongList(self):
        request = self.youtube.playlistItems().list(part="snippet", maxResults=50, playlistId="PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf")
        response = request.execute()

        #delete any previous info (may be outdated)
        self.song_ids = []
        self.song_names = []
        for x in range(0, len(response['items'])): 
            self.song_ids.append(response['items'][x]['id'])
            self.song_names.append(response['items'][x]['snippet']['title'])
    
    #using song id, remove it from the playlist
    def deleteSong(self, del_song_id):
        request = self.youtube.playlistItems().delete(id = del_song_id)
        request.execute()

    def repeatMsg(self, message, arg_length = 1):
        c = self.connection
        if int(arg_length) > 5:
            length = 5
        else:
            length = int(arg_length)
        for _ in range(0, length):
            c.privmsg(self.channel, message)
    
    #allows for detection of bigfollows and tries to ban the user
    def spamDetection(self, message, name):
        c = self.connection
        if 'bigfollows' in message:
            c.privsmsg(self.channel, '/ban %s' %(name))
        
    def on_welcome(self, c, e):
        print('Joining ' + self.channel)

        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        current_time = datetime.now(tz.UTC)
        #find the time difference
        time_difference = str(current_time - self.time_last_checked).split(':')
        hours = int(time_difference[0]) #get number of hours since last validation
        if hours > 1:
            self.validateToken()
            c.privmsg(self.channel, 'Join the xRohanTV community discord at: ' + discord_link)
            self.time_last_checked = current_time

        mod = False
        #get the name of the chatter
        name = e.source.split('!')[0]
        # If a chat message starts with an exclamation point, try to run it as a command
        if e.arguments[0][:1] == '!':
            if len(e.arguments[0].split(' ')) > 1: #if multi-phrase commmand (ex: !ad 30)
                args = e.arguments[0].split(' ')[1:]
            else:
                args = None
            cmd = e.arguments[0].split(' ')[0][1:]
            #check if user is a mod
            for _, value in e.tags[-1].items():
                if value == 'mod' or name == 'xrohantv':
                    mod = True
            if args != None:
                print('Received command: ' + cmd + ' ' + args[0])
            else:
                print('Received command: ' + cmd)
            cmd = cmd.lower()
            self.do_command(e, cmd, args, mod, name)

        #allow for simple commands without '!' prefix
        elif e.arguments[0].lower() == 'f':
            c.privmsg(self.channel, 'Press F to pay respects BibleThump')
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
                message = "Rohan has died %d times. What a loser!" %int(self.death_counter)
                c.privmsg(self.channel, message)
            elif args[0] == 'help':
                c.privmsg(self.channel, '!death will provide the current death count, and mods can do !death +/-/set <#>/reset to change the current count')
            elif args[0] == "+" or args[0] == 'add':
                if mod:
                    self.death_counter = self.death_counter+1
                    if self.death_counter == 69:
                        message = 'Rohan died 69 times. Nice ;)'
                    else:
                        message = "Rohan just died. That's death #%d. What a loser!" %int(self.death_counter)
                    c.privmsg(self.channel, message)
            elif args[0] == "-" or args[0] == 'undo':
                if mod:
                    self.death_counter = self.death_counter - 1
            elif args[0] == 'set':
                if mod:
                    if args[1] != None:
                        self.death_counter = int(args[1])
                        message = "That's death #%d. What a loser!" %int(self.death_counter)
                        c.privmsg(self.channel, message)
                    else:
                        c.privmsg(self.channel, 'Please input a value to set to')
            elif args[0] == 'reset':
                    self.death_counter = 0
                    c.privmsg(self.channel, 'Death counter reset')

        #run an ad
        elif cmd == "ad":
            if mod:
                if args[0] == 'help':
                    c.privmsg(self.channel, '(Mod Only) Send !ad <length> to request an ad. Length can be 30/60/90/120/150/180.')
                elif args != None: #round their given length
                    try:
                        length = round(int(args[0])/30)*30 #div by 30 then round to nearest number, then *30 to get multiple of 30 length
                        if length > 180: #if length is greater than max length (3 mins), then set to 3 mins
                            length = 180
                    except:
                        c.privmsg(self.channel, 'Please input a valid ad length')
                        return
                else:  #if no length given, default to 60 sec
                    length = 60
                url = 'https://api.twitch.tv/helix/channels/commercial' 
                headers = {'Client-Id': self.client_id, 'Content-Type': 'application/json',  'Authorization': 'Bearer ' + self.token}
                raw_data = '{ "broadcaster_id": "%s", "length": %d }' %(self.channel_id, length)
                r = requests.post(url, data=raw_data, headers=headers).json()
                try:
                    length = test['data'][0]['length']
                    c.privmsg(self.channel, 'Running a %d sec ad' %length) 
                except:
                    self.refresh_token()
                    self.do_command(e, cmd, args, mod, name)
            else:
                c.privmsg(self.channel, 'This is a mod only command')

        #Youtube Playlist Queue
        elif cmd == 'songs' or cmd == 'song':
            if args == None or args[0] == 'link' or args[0] == 'playlist': #check for empty request: !songs to provide the link
                c.privmsg(self.channel, 'Listen along at https://www.youtube.com/playlist?list=PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf')
            elif args[0] == 'help':
                c.privmsg(self.channel, 'To request a song, use the song request channel points reward and type: "!song request <link or song name>"')
            elif args[0] == 'play' or args[0] == 'request' or args[0] == 'queue':
                song_name = ""
                if len(args) > 2: #searching for song name
                    search_term = ""
                    for i in range(1, len(args)):
                        search_term = search_term + args[i] + ' ' #combine split terms by appending the search term to the end
                    req_song_name, video_id = self.searchSong(search_term)
                elif len(args) == 1: #check for !songs play/request/queue without search term
                    c.privmsg(self.channel, "Please provide valid youtube link or song name")
                else: #either has a link, song_id, or a single term search phrase
                    url_data = urlparse.urlparse(args[1]) #check if it's a link, then parse the id from it
                    if url_data[1] == 'www.youtube.com':
                        query = urlparse.parse_qs(url_data.query)
                        video_id = query["v"][0]
                        print('Video ID = ' + video_id)
                        req_song_name, video_id = self.searchSong(video_id) #searching the song id returns it on top result
                    elif url_data[1] == 'youtu.be':
                        video_id = url_data[1][1:]
                        print('Video ID = ' + video_id)
                        req_song_name, video_id = self.searchSong(video_id)
                    else: #if it was not a link, search for the term (YT will return first search result - Searching ID works)
                        req_song_name, video_id = self.searchSong(args[1])
                self.updateSongList()
                if req_song_name in self.song_names: #if song is already inside the playlist
                    c.privmsg(self.channel, 'Song is already in the playlist')
                    return
                elif req_song_name in self.banned_songs:
                    c.privmsg(self.channel, 'Song is banned lol :p')
                    return
                else:
                    song_name = self.queueSong(video_id)
                    message = 'Queued: ' + song_name
                    c.privmsg(self.channel, message)
                    self.updateSongList()
            elif args[0] == 'delete': #params: position, deletes the song at pos
                if mod:
                    search_term = ""
                    self.updateSongList()                           #get an updated list of songs
                    for i in range(1, len(args)): #concatenate search term
                        search_term = search_term + args[i] + ' '
                    del_song_name, _ = self.searchSong(search_term) #get the name of the video through search
                    print('Trying to delete: ' + del_song_name)
                    try: #if the song is in the list (no error caught), then delete it
                        index = self.song_names.index(del_song_name)    #find the name inside the list of song_names and its index
                        del_song_id = self.song_ids[index]              #find the playlist item ID using the index ^
                        self.deleteSong(del_song_id)                    #delete the song using a delete request
                        c.privmsg(self.channel, 'Deleted: ' + del_song_name)
                    except:
                        c.privmsg(self.channel, 'Could not delete the video - Video not found')
                        return
            elif args[0] == 'ban':      
                if mod:
                    search_term = ""
                    self.updateSongList()                           #get an updated list of songs
                    for i in range(1, len(args)):                   #concatenate search term
                        search_term = search_term + args[i] + ' '
                    ban_song_name, _ = self.searchSong(search_term) #get the name of the video through search
                    if not(ban_song_name in self.banned_songs):      #if its not already in the banned list
                        print('Banned: ' + ban_song_name)
                        self.banned_songs.append(ban_song_name)
                        c.privmsg(self.channel, 'Banned: ' + ban_song_name)
                        self.updateSongList()
                    else:
                        c.privsmsg(self.channel, ban_song_name + ' is already banned')

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
            c.privmsg(self.channel, 'Join the xRohanTV community discord at: ' + discord_link)

        #find current uptime
        elif cmd == 'uptime':
            url = 'https://api.twitch.tv/helix/search/channels?query=xrohantv'
            headers = {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            index = -1
            try:
                for i in range(0, len(r['data']) - 1):
                    if r['data'][i]['broadcaster_login'] == 'xrohantv':
                        index = i
                        break
                if r['data'][index]['started_at'] != "" and index != -1: #check if started at is empty (Rohan isn't streaming), if index = -1, then it couldn't find xRohanTV
                    self.start_time = parser.parse(r['data'][index]['started_at'])
                    current_time = datetime.now(tz.UTC)
                    time_difference = str(current_time - self.start_time).split(':')
                    hours = time_difference[0]
                    minutes = time_difference[1]
                    seconds = time_difference[2][0:2]
                    c.privmsg(self.channel, "Rohan's been streaming for " + hours + ' hours, ' + minutes + ' minutes, and ' + seconds + ' seconds.')
                else:
                    print('Channel is not live')
            except:
                self.refresh_token()
                self.do_command(e, cmd, args, mod, name)

        elif cmd == 'coin' or cmd == 'coins':
            flip = random.randint(0,1)
            if flip == 1:
                c.privmsg(self.channel, "It's Heads!")
            else:
                c.privmsg(self.channel, "It's Tails!")
        
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

        # Simple Bot Commands #
        elif cmd == 'f':
            c.privmsg(self.channel, 'Press F to pay respects BibleThump')
        elif cmd == "schedule":           
            c.privmsg(self.channel, "Hah! You think Rohan has an actual streaming schedule? LOL Join the xRohanTV discord (!Discord) to be in the know :)")
        elif cmd == 'cap':
            c.privmsg(self.channel, "That's CAP! 🧢🧢🧢")
        elif cmd == 'gone':
            c.privmsg(self.channel, '🦀🦀🦀 ROHAN IS GONE 🦀🦀🦀')
        elif cmd == 'pog' or cmd == 'poggers':
            c.privmsg(self.channel, 'POGGERS PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp')
        elif cmd == 'cheese':
            c.privmsg(self.channel, '🧀🧀🧀 THATS SOME CHEESE🧀🧀🧀 https://www.twitch.tv/xrohantv/clip/CrepuscularExuberantShrewPoooound')
        elif cmd == 'cheeseless':
            c.privmsg(self.channel, 'Your prayers to The Cheese God remain unanswered... BibleThump https://clips.twitch.tv/AcceptableHorribleAmazonStrawBeary-wAZaHhkwkKh0xmLK')
        elif cmd == 'defeat':
            c.privmsg(self.channel, 'Remember Rohan, Hesitation is Defeat')
        elif cmd == 'djkhaled' or cmd == 'khaled' or cmd == 'onemore':
            c.privmsg(self.channel, 'As DJ Khaled famously said, "ONE MORE"')
        elif cmd == 'robert':
            c.privmsg(self.channel, "ROBERTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT!!!!!!!!!!!!!!!!!!")
        elif cmd == 'plague':
            message = 'Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper'
            self.repeatMsg(message, args[0])
        elif cmd == 'BOBO':
            message = 'xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO xrohanBOBO '
            self.repeatMsg(message, args[0])
        elif cmd == 'pmg' or cmd == 'poomg':
            c.privmsg(self.channel, 'Poops McGee Strikes Again!')
        #cmd for list of current commands
        elif cmd == 'help':
            c.privmsg(self.channel, 'The current commands are: ad, game, title, death, song, discord, uptime, giveaway, schedule, coin, dice <#>, F, CAP, POG')
            c.privmsg(self.channel, 'You can type help after certain commands to get more info (ex: !ad help)')
        # The command was not recognized
        else:
            print("Did not understand command: " + cmd)

def main():
    bot = RoboBoboBot()
    bot.start()

if __name__ == "__main__":
    main()