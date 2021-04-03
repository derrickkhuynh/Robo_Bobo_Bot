#Robo_bobo_bot

import os
import sys
from dotenv import load_dotenv
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
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
#youtube scopes
yt_scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

class RoboBoboBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel):
        #load env stuff
        load_dotenv()
        self.username = 'robo_bobo_bot'
        self.death_counter = 0
        #self.death_filepath = "Main\death_counter.txt"
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.channel = '#' + channel

        self.start_time = None
        #Current Song Info
        self.curr_song = ""

        # Youtube Authentication
        client_secrets_file = "Main\client_id.json"
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, yt_scopes)
        self.credentials = flow.run_console()

        #use the refresh token from .env to request a new access token
        url = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token='+os.getenv('REFRESH_TOKEN')+'&client_id='+self.client_id+'&client_secret='+os.getenv('TWITCH_CLIENT_SECRET')+'&scope=channel:edit:commercial'
        r = requests.post(url).json()
        if 'access_token' in r:
            self.token = r['access_token']
            print('Access Token Granted')
        else: #if failed, exit
            print('Refresh request failed')
            exit()

        # Get the channel id for API calls
        url = 'https://api.twitch.tv/helix/search/channels?query=' + channel
        headers = {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.token}
        r = requests.get(url, headers=headers).json()
        self.channel_id = r['data'][0]['id']

        # Create IRC bot connection
        server = 'irc.chat.twitch.tv'
        port = 6667
        print('Connecting to ' + server + ' on port ' + str(port) + '...')
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+os.getenv('BOT_OAUTH_TOKEN'))], self.username, self.username)

    #using the search term, search for the top result from youtube, and get it's song id and name, then add it to the queue
    def searchSong(self, search_term):
        api_service_name = "youtube"
        api_version = "v3"
        youtube = googleapiclient.discovery.build(api_service_name, api_version, credentials=self.credentials)
        request = youtube.search().list(part="snippet", maxResults=1, q=search_term)
        response = request.execute()  #request top result from youtube
        req_song_id = response['items'][0]['id']['videoId']
        return self.queueSong(req_song_id)
        
    #TODO: ADD Duration counter to track current position in the playlist
    #given the requested song's id, add it to the end of the playlist
    def queueSong(self, request_song_id):
        api_service_name = "youtube"
        api_version = "v3"
        youtube = googleapiclient.discovery.build(api_service_name, api_version, credentials=self.credentials)
        request = youtube.playlistItems().insert(
        part="snippet",
        body={
          "snippet": {
            "playlistId": "PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf",
            "position": 100,
            "resourceId": {
              "kind": "youtube#video",
              "videoId": request_song_id
            }
          }
        })
        response = request.execute()
        song_name = response['snippet']['title']
        print('Queueing song: ' + song_name)
        return song_name
        
    def on_welcome(self, c, e):
        print('Joining ' + self.channel)

        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)

        #update death_counter from external file
        # f = open(self.death_filepath,'a+')
        # self.death_counter = f.read()
        # if(os.stat(self.death_filepath).st_size == 0):
        #     self.death_counter = 0
        #     f.write('%d' %self.death_counter)
        #     f.close()

    def on_pubmsg(self, c, e):
        mod = False
        # If a chat message starts with an exclamation point, try to run it as a command
        if e.arguments[0][:1] == '!':
            if len(e.arguments[0].split(' ')) > 1: #if multi-phrase commmand (ex: !ad 30)
                args = e.arguments[0].split(' ')[1:]
            else:
                args = None
            cmd = e.arguments[0].split(' ')[0][1:]
            #check if user is a mod
            for _, value in e.tags[-1].items():
                if value == 'mod':
                    mod = True
                    print('User is a mod')
            print('Received command: ' + cmd)
            if args != None:
                print('With args: ' + args[0])
            self.do_command(e, cmd, args, mod)
        return
    #cmd is the first word after !, and args is the 2nd word afterwords (ex: !ad 30, cmd = 'ad', args = 30)
    #mod is a bool on whether the one calling the command is a mod
    def do_command(self, e, cmd, args, mod):
        c = self.connection
        # Poll the API to get current game.
        if cmd == "game":
            url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + self.channel_id
            headers = {'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            print(r)
            r = r['data'][0]
            print(r)
            c.privmsg(self.channel, r["broadcaster_name"] + ' is currently playing ' + r['game_name'])

        # Poll the API the get the current status of the stream
        elif cmd == "title":
            url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + self.channel_id
            headers = {'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token}
            r = requests.get(url, headers=headers).json()
            r = r['data'][0]
            c.privmsg(self.channel, r['broadcaster_name'] + ' channel title is currently ' + r['title'])

        #death counter commands
        elif cmd == "deaths":
            if args == None:
                message = "Rohan has died %d times. What a loser!" %int(self.death_counter)
                c.privmsg(self.channel, message)
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
            #update the external txt file with current death counter
            # f = open(self.death_filepath,'w')
            # f.write(self.death_counter)
            # f.close()
        #run an ad
        elif cmd == "ad":
            if mod:
                if args != None: #if no length given, default to 60 sec
                    length = round(int(args[0])%30)*30 #take given length (30,60,90, etc), mod-div by 30 then round to nearest number, then *30 to get multiple of 30 length
                    if length > 180: #if length is greater than max length (3 mins), then set to 3 mins
                        length = 180
                else:
                    length = 60
                print('length = ', length)
                url = 'https://api.twitch.tv/helix/channels/commercial' 
                headers = {'Client-Id': self.client_id, 'Content-Type': 'application/json',  'Authorization': 'Bearer ' + self.token}
                raw_data = '{ "broadcaster_id": "%s", "length": %d }' %(self.channel_id, length)
                r = requests.post(url, data=raw_data, headers=headers).json()
                print(r)
                if 'data' in r:
                    c.privmsg(self.channel, 'Running a %d sec ad') %length
                else:
                    print(r)
            else:
                c.privmsg(self.channel, 'This is a mod only command')
        #Youtube Playlist Queue
        elif cmd.lower() == 'songs':
            if args[0] == 'play' or args[0] == 'request' or args[0] == 'queue':
                print('Wait a bit lol')
                song_name = ""
                if len(args) > 2: #searching for song name
                    search_term = ""
                    for i in range(1, len(args)):
                        search_term = search_term + args[i] + ' ' #append the search term to the end
                    song_name = self.searchSong(search_term)
                else: #either has a link, song_id, or a single term search phrase
                    #check if it's a link, then parse the id from it
                    url_data = urlparse.urlparse(args[1])
                    query = urlparse.parse_qs(url_data.query)
                    video_id = query["v"][0]
                    print('Video ID = ' + video_id)
                    song_name = self.queueSong(video_id)
                message = 'Queued: ' + song_name
                c.privmsg(self.channel, message)
        
        #plug discord server
        elif cmd.lower() == 'discord' or cmd.lower() == 'socials':
            c.privmsg(self.channel, 'Join the xRohanTV community discord at: https://discord.gg/Za5ngC9QsE')

        #find current uptime
        elif cmd.lower() == 'uptime':
            if self.start_time == None:
                url = 'https://api.twitch.tv/helix/search/channels?query=' + self.channel[1:] #truncate the initial # from self.channel
                headers = {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.token}
                r = requests.get(url, headers=headers).json()
                if r['data'][0].has('started_at'):
                    self.start_time = parser.parse(r['data'][0]['started_at'])
                else:
                    print('Channel is not live')
            else:
                current_time = datetime.now(tz.UTC)
                time_difference = current_time - self.start_time
                print(time_difference)
        # Simple Bot Commands #
        elif cmd == 'F':
            c.privmsg(self.channel, 'Press F to pay respects BibleThump')
        elif cmd == "schedule":           
            c.privmsg(self.channel, "Hah! You think Rohan has an actual streaming schedule?")
        elif cmd.lower() == 'cap':
            c.privmsg(self.channel, "That's CAP! 🧢🧢🧢")
        elif cmd.lower() == 'gone':
            c.privmsg(self.channel, '🦀🦀🦀 ROHAN IS GONE 🦀🦀🦀')
        elif cmd.lower() == 'pog':
            c.privmsg(self.channel, 'PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp')
        elif cmd.lower() == 'cheese':
            c.privmsg(self.channel, '🧀🧀🧀 THATS SOME CHEESE🧀🧀🧀')
        elif cmd.lower() == 'defeat':
            c.privmsg(self.channel, 'Remember Rohan, Hesitation is Defeat')
        elif cmd.lower() == 'plague':
            if args == None: #if no length given, default to 60 sec
                length = 1
            elif int(args[0]) > 5:
                length = 5
            else:
                length = int(args[0])
            for _ in range(0, length):
                c.privmsg(self.channel, 'Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper')
        #cmd for list of current commands
        elif cmd == 'cmds':
            c.privmsg(self.channel, 'The current commands are: game, title, deaths, discord, schedule, F, cap, gone, pog, cheese, plague <#>')
            c.privmsg(self.channel, 'Mod only commands are: ad <30/60/90...>, deaths +, deaths undo, deaths set <#>')
        # The command was not recognized
        else:
            print("Did not understand command: " + cmd)

def main():
    if len(sys.argv) != 2:
        print("Usage: Robo_bobo_bot <channel>")
        sys.exit(1)

    channel   = sys.argv[1]

    # username = "Robo_bobo_bot"
    # client_id = "5xujdtajog1xaihkd3cvzhyk7f52d8"
    # token = "oauth:rizwucwbkmr1m0lezs30koikliswa7"
    # channel = "xrohantv"

    bot = RoboBoboBot(channel)
    bot.start()

if __name__ == "__main__":
    main()