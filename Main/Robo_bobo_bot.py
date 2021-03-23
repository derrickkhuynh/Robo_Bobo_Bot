#Robo_bobo_bot
#TODO: fix death counter file import/export
#      Fix ad bad request from server / test ad functionality
#      Add additional features
import os
import sys
import irc.bot
from pip._vendor import requests

class RoboBoboBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel):
        self.username = 'robo_bobo_bot'
        self.death_counter = 0
        self.death_filepath = "Main\death_counter.txt"
        self.client_id = '5xujdtajog1xaihkd3cvzhyk7f52d8'
        #self.token = token
        self.refresh_token = 'y564u6bihjtfsvwwv09nud1dlgl66bq8dknosplj76efwdu503'
        self.channel = '#' + channel

        ## Maybe one day create a frontend and allow for seamless authentication? But i'm not a CS major lol
        # #generate a token for itself (IDK if this is correct code flow)
        # url = 'https://id.twitch.tv/oauth2/token' + '?client_id='+client_id+ '&client_secret='+"dig69r7rkevaa69tp6zl2a0sk7wae1"+'&code=kg37hwypnia3iabry9j3i5q4ywdk9w'+'&grant_type=authorization_code'+ '&redirect_uri='+"http://localhost"
        # r = requests.post(url).json()
        # print(r)
        # if 'access_token' in r:
        #     self.token = r['access_token']
        #     self.refresh_token = r['refresh_token']
        # else:
            #if access_token not given, use the refresh token to get a new access token
        url = 'https://id.twitch.tv/oauth2/token?grant_type=refresh_token&refresh_token=y564u6bihjtfsvwwv09nud1dlgl66bq8dknosplj76efwdu503&client_id='+self.client_id+'&client_secret='+'dig69r7rkevaa69tp6zl2a0sk7wae1'+'&scope=channel:edit:commercial'
        r = requests.post(url).json()
        print(r)
        if 'access_token' in r:
            self.token = r['access_token']
        else:
            print('Refresh request failed')

        # Get the channel id for API calls
        url = 'https://api.twitch.tv/helix/search/channels?query=' + channel
        headers = {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.token}
        r = requests.get(url, headers=headers).json()
        self.channel_id = r['data'][0]['id']

        # Create IRC bot connection
        server = 'irc.chat.twitch.tv'
        port = 6667
        print('Connecting to ' + server + ' on port ' + str(port) + '...')
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+'a8g76acsbnp40qcseo9ekxloa233bm')], self.username, self.username)
        
    def on_welcome(self, c, e):
        print('Joining ' + self.channel)

        # You must request specific capabilities before you can use them
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        c.join(self.channel)

        #update death_counter from external file
        f = open(self.death_filepath,'a+')
        self.death_counter = f.read()
        if(os.stat(self.death_filepath).st_size == 0):
            self.death_counter = 0
            f.write('%d' %self.death_counter)
            f.close()

    def on_pubmsg(self, c, e):
        mod = False
        # If a chat message starts with an exclamation point, try to run it as a command
        if e.arguments[0][:1] == '!':
            if len(e.arguments[0].split(' ')) > 1: #if multi-phrase commmand (ex: !ad 30)
                args = e.arguments[0].split(' ')[1]
            else:
                args = None
            cmd = e.arguments[0].split(' ')[0][1:]
            #check if user is a mod
            for _, value in e.tags[-1].items():
                if value == 'mod':
                    mod = True
                    print('User is a mod')
            print('Received command: ' + cmd)
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
            message = "Rohan has died %d times. What a loser!" %self.death_counter
            c.privmsg(self.channel, message)
            #update the external txt file with current death counter
            f = open(self.death_filepath,'w')
            f.write(self.death_counter)
            f.close()
        elif cmd == "deaths+":
            if e.has("mod"):
                self.death_counter = self.death_counter+1
                message = "Rohan just died. That's death #%d. What a loser!" %self.death_counter
                c.privmsg(self.channel, message)
                #update external file
                f = open(self.death_filepath,'w')
                f.write(self.death_counter)
                f.close()
            else:
                c.privmsg(self.channel, "This is a mod only command. Sry")
        elif cmd == "deaths-undo":
            if e.has("mod"):
                self.death_counter = self.death_counter - 1
                f = open(self.death_filepath,'w')
                f.write(self.death_counter)
                f.close()
            else:
                c.privmsg(self.channel, "This is a mod only command.")
        #run an ad
        elif cmd == "ad":
            if mod:
                if args != None: #if no length given, default to 60 sec
                    length = round(int(args)%30)*30 #take given length (30,60,90, etc), mod-div by 30 then round to nearest number, then *30 to get multiple of 30 length
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
        #Bobo has no schedule
        elif cmd == "schedule":
            message = "Hah! You think Rohan has an actual streaming schedule?"            
            c.privmsg(self.channel, message)
        #F for respects
        elif cmd == 'F':
            c.privmsg(self.channel, 'Press F to pay respects BibleThump')
        #BOBO CAP
        elif cmd == 'cap' or cmd == 'CAP':
            c.privmsg(self.channel, "That's CAP! 🧢🧢🧢")
        #BOBO IS GONE 🦀
        elif cmd == 'GONE':
            c.privmsg(self.channel, '🦀🦀🦀 BOBO IS GONE 🦀🦀🦀')
        elif cmd == 'POG':
            c.privmsg(self.channel, 'PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp PogChamp')
        elif cmd == 'plague':
            if args != None: #if no length given, default to 60 sec
                length = 1
            elif int(args) > 5:
                length = 5
            else:
                length = int(args)
            for _ in range(0, length):
                c.privmsg(self.channel, 'Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper Plague of Egypt ResidentSleeper')
        # The command was not recognized
        else:
            print("Did not understand command: " + cmd)

def main():
    if len(sys.argv) != 5:
        print("Usage: twitchbot <username> <client id> <token> <channel>")
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