import os
import pickle
#youtube imports 
import urllib.parse as urlparse
#Google API imports for youtube playlist requests
from google.auth.transport.requests import Request
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors


from helper import helper_Module as hp

#scopes
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
PLAYLIST_ID = "PLpKWYssZZaRkwTiqBCEytDUNySoREGTPf"


class YoutubePlaylistManager():
    def __init__(self):
        #list of songs in the playlist
        self.song_names = []
        self.song_ids = []

        if os.path.exists('ban_songs.pickle'):
            print('Loading Banned Songs From File...')
            with open('ban_songs.pickle', 'rb') as token:
                self.banned_songs = pickle.load(token)
        else:
            self.banned_songs = []

        try:
            self.yt_authorization()
        except:
            os.remove('ban_songs.pickle')
            self.yt_authorization
        

    #conduct youtube authorization and return a youtube object to conduct calls with
    #the credentials are not stored as a class var (only local var) for safety and are deleted after initialization
    def yt_authorization(self):
        #check if a pickle exists with the token
        if os.path.exists('youtube/yt_token.pickle'):
            print('Loading Youtube Credentials From File...')
            with open('youtube/yt_token.pickle', 'rb') as token:
                yt_credentials = pickle.load(token)
        else:
            yt_credentials = None

        # If there are no valid credentials available, then either refresh the token or log in.
        if not yt_credentials or not yt_credentials.valid:
            if yt_credentials and yt_credentials.expired and yt_credentials.refresh_token:
                print('Refreshing Youtube Access Token...')
                try:
                    yt_credentials.refresh(Request())
                except:
                    os.remove('youtube/yt_token.pickle')
                    yt_credentials.refresh(Request())
            else:
                print('Fetching New Tokens...')
                client_secrets_file = "client_id.json"
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, YT_SCOPES)
                flow.run_local_server(port=8080, prompt='consent',
                                    authorization_prompt_message='')
                yt_credentials = flow.credentials

                # Save the credentials for the next run
                with open('youtube/yt_token.pickle', 'wb') as f:
                    print('Saving Youtube Credentials for Future Use...')
                    pickle.dump(yt_credentials, f)

        api_service_name = "youtube"
        api_version = "v3"
        self.youtube = googleapiclient.discovery.build(api_service_name, api_version, credentials=yt_credentials)

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
            "playlistId": PLAYLIST_ID,
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
        request = self.youtube.playlistItems().list(part="snippet", maxResults=50, playlistId = PLAYLIST_ID)
        response = request.execute()

        #delete any previous info (may be outdated)
        self.song_ids = []
        self.song_names = []
        for x in range(0, len(response['items'])): 
            self.song_ids.append(response['items'][x]['id'])
            self.song_names.append(response['items'][x]['snippet']['title'])
    
    def parseSongRequest(self, req_song):
        song_name = ""
        if len(req_song) == 1: #check for !songs play/request/queue without search term
            return "Please provide valid youtube link or song name"

        #if more than 1 word song search, then it's not a link so search it
        elif len(req_song) > 2: #searching for song name
            search_term = hp.concatenateArgs(req_song, 1)
            req_song_name, video_id = self.searchSong(search_term)

        else: #either has a link, song_id, or a single term search phrase
            url_data = urlparse.urlparse(req_song[1]) #check if it's a link, then parse the id from it
            if url_data[1] == 'www.youtube.com':
                query = urlparse.parse_qs(url_data.query)
                video_id = query["v"][0]
                print('Video ID = ' + video_id)
                req_song_name, video_id = self.searchSong(video_id) #searching the song id returns it on top result

            elif url_data[1] == 'youtu.be':
                video_id = url_data[2][1:]
                print('Video ID = ' + video_id)
                req_song_name, video_id = self.searchSong(video_id)

            else: #if it was not a link, search for the term (YT will return first search result - Searching ID works)
                req_song_name, video_id = self.searchSong(req_song[1])

        self.updateSongList()
        if req_song_name in self.song_names: #if song is already inside the playlist
            return 'Song is already in the playlist'
        #check if song is in banned_songs list
        elif req_song_name in self.banned_songs:
            return 'Song is banned lol :p'
        else:
            song_name = self.queueSong(video_id)
            self.updateSongList()
            return 'Queued: ' + song_name

    #using song id, remove it from the playlist
    def deleteSong(self, req_del_args):
        self.updateSongList()                           #get an updated list of songs
        search_term = hp.concatenateArgs(req_del_args, 1) 
        del_song_name, _ = self.searchSong(search_term) #get the name of the video through search
        print('Trying to delete: ' + del_song_name)
        try: #if the song is in the list (no error caught), then delete it
            index = self.song_names.index(del_song_name)    #find the name inside the list of song_names and its index
            del_song_id = self.song_ids[index]              #find the playlist item ID using the index ^
            request = self.youtube.playlistItems().delete(id = del_song_id)
            request.execute()                    #delete the song using a delete request
            return 'Deleted: ' + del_song_name
        except:
            return 'Could not delete the video - Video not found'

    def banSong(self, req_song):
        self.updateSongList()                           #get an updated list of songs
        search_term = hp.concatenateArgs(req_song, 1)
        ban_song_name, _ = self.searchSong(search_term) #get the name of the video through search
        if not(ban_song_name in self.banned_songs):      #if its not already in the banned list
            print('Banned: ' + ban_song_name)
            self.banned_songs.append(ban_song_name)
            self.updateSongList()

            with open('ban_songs.pickle', 'wb') as f:
                print('Saving banned songs for Future Use...')
                pickle.dump(self.banned_songs, f)

            return 'Banned: ' + ban_song_name
        else:
            return ban_song_name + ' is already banned'  