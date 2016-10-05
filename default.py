
#import rpdb2 
#rpdb2.start_embedded_debugger('pw')
import os, sys, re
import xbmc, xbmcaddon

if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson

__addon__ = xbmcaddon.Addon()
__addonversion__ = __addon__.getAddonInfo('version')
__addonid__ = __addon__.getAddonInfo('id')
__addonname__ = __addon__.getAddonInfo('name')
__addonPath__ = __addon__.getAddonInfo('path')
__addonResourcePath__ = xbmc.translatePath(os.path.join(__addonPath__, 'resources', 'lib'))
__addonIconFile__ = xbmc.translatePath(os.path.join(__addonPath__, 'icon.png'))
sys.path.append(__addonResourcePath__)

from langcodes import *
from prefsettings import settings

settings = settings()

LOG_NONE = 0
LOG_ERROR = 1
LOG_INFO = 2
LOG_DEBUG = 3
    
def log(level, msg):
    if level <= settings.logLevel:
        if level == LOG_ERROR:
            l = xbmc.LOGERROR
        elif level == LOG_INFO:
            l = xbmc.LOGINFO
        elif level == LOG_DEBUG:
            l = xbmc.LOGDEBUG
        xbmc.log("[Language Preference Manager]: " + str(msg), l)


class LangPref_Monitor( xbmc.Monitor ):
  def __init__( self ):
      xbmc.Monitor.__init__( self )
        
  def onSettingsChanged( self ):
      settings.init()
      settings.readSettings()

class Main:
    def __init__( self ):
        self._init_vars()
        if (not settings.service_enabled):
            log(LOG_INFO, "Service not enabled")

        settings.readSettings()
        self._daemon()

    def _init_vars( self ):
        self.Monitor = LangPref_Monitor()
        self.Player = LangPrefMan_Player()

    def _daemon( self ):
        while (not xbmc.abortRequested):
            xbmc.sleep(500)
            

class LangPrefMan_Player(xbmc.Player) :
    
    def __init__ (self):
        xbmc.Player.__init__(self)
        
    def onPlayBackStarted(self):
        if settings.service_enabled and settings.at_least_one_pref_on and self.isPlayingVideo():
            log(LOG_DEBUG, 'Playback started')
            self.audio_changed = False
            # switching an audio track to early leads to a reopen -> start at the beginning
            if settings.delay > 0:
                log(LOG_DEBUG, "Delaying preferences evaluation by {0} ms".format(settings.delay))
                xbmc.sleep(settings.delay)
            log(LOG_DEBUG, 'Getting video properties')
            self.getDetails()
            self.evalPrefs()

    def evalPrefs(self):
        # recognized filename audio or filename subtitle
        fa = False
        fs = False
        if settings.useFilename:
            audio, sub = self.evalFilenamePrefs()
            if (audio >= 0) and audio < len(self.audiostreams):
                log(LOG_INFO, 'Filename preference: Match, selecting audio track {0}'.format(audio))
                self.setAudioStream(audio)
                self.audio_changed = True
                fa = True
            else:
                log(LOG_INFO, 'Filename preference: No match found for audio track ({0})'.format(self.getPlayingFile()))
                
            if (sub >= 0) and sub < len(self.subtitles):
                self.setSubtitleStream(sub)
                fs = True
                log(LOG_INFO, 'Filename preference: Match, selecting subtitle track {0}'.format(sub))
                if settings.turn_subs_on:
                    log(LOG_DEBUG, 'Subtitle: enabling subs' )
                    self.showSubtitles(True)
            else:
                log(LOG_INFO, 'Filename preference: No match found for subtitle track ({0})'.format(self.getPlayingFile()))
                if settings.turn_subs_off:
                    log(LOG_INFO, 'Subtitle: disabling subs' )
                    self.showSubtitles(False)
                    
        if settings.audio_prefs_on and not fa:
            if settings.custom_audio_prefs_on:
                trackIndex = self.evalAudioPrefs(settings.custom_audio)
            else:
                trackIndex = self.evalAudioPrefs(settings.AudioPrefs)
                
            if trackIndex == -2:
                log(LOG_INFO, 'Audio: None of the preferred languages is available' )
            elif trackIndex >= 0:
                self.setAudioStream(trackIndex)
                self.audio_changed = True
            
        if settings.sub_prefs_on and not fs:
            if settings.custom_sub_prefs_on:
                trackIndex = self.evalSubPrefs(settings.custom_subs)
            else:
                trackIndex = self.evalSubPrefs(settings.SubtitlePrefs)
                
            if trackIndex == -2:
                log(LOG_INFO, 'Subtitle: None of the preferred languages is available' )
                if settings.turn_subs_off:
                    log(LOG_INFO, 'Subtitle: disabling subs' )
                    self.showSubtitles(False)
            elif trackIndex >= 0:
                self.setSubtitleStream(trackIndex)
                if settings.turn_subs_on:
                    log(LOG_INFO, 'Subtitle: enabling subs' )
                    self.showSubtitles(True)
                
        if settings.condsub_prefs_on and not fs:
            if settings.custom_condsub_prefs_on:
                trackIndex = self.evalCondSubPrefs(settings.custom_condsub)
            else:
                trackIndex = self.evalCondSubPrefs(settings.CondSubtitlePrefs)

            if trackIndex == -1:
                log(LOG_INFO, 'Conditional subtitle: disabling subs' )
                self.showSubtitles(False)
            if trackIndex == -2:
                log(LOG_INFO, 'Conditional subtitle: None of the preferrences is available' )
                if settings.turn_subs_off:
                    log(LOG_DEBUG, 'Subtitle: disabling subs' )
                    self.showSubtitles(False)
            elif trackIndex >= 0:
                self.setSubtitleStream(trackIndex)
                if settings.turn_subs_on:
                    log(LOG_DEBUG, 'Subtitle: enabling subs' )
                    self.showSubtitles(True)

    def evalFilenamePrefs(self):
        log(LOG_DEBUG, 'Evaluating filename preferences' )
        audio = -1
        sub = -1
        filename = self.getPlayingFile()
        matches = settings.reg.findall(filename)
        fileprefs = []
        for m in matches:
            sp = settings.split.split(m)
            fileprefs.append(sp)

        for pref in fileprefs:
            if len(pref) == 2:
                if (pref[0].lower() == 'audiostream'):
                    audio = int(pref[1])
                    log(LOG_INFO, 'audio track extracted from filename: {0}'.format(audio))
                elif(pref[0].lower() == 'subtitle'):
                    sub = int(pref[1])
                    log(LOG_INFO, 'subtitle track extracted from filename: {0}'.format(sub))
        log(LOG_DEBUG, 'filename: audio: {0}, sub: {1} ({2})'.format(audio, sub, filename))
        return audio, sub
    
    def evalAudioPrefs(self, audio_prefs):
        log(LOG_DEBUG, 'Evaluating audio preferences' )
        i = 0
        for pref in audio_prefs:
            i += 1
            g_t, preferences = pref
            # genre or tags are given (g_t not empty) but none of them matches the video's tags/genres
            if g_t and (not (self.genres_and_tags & g_t)):
                continue

            log(LOG_INFO,'Audio: genre/tag preference {0} met with intersection {1}'.format(g_t, (self.genres_and_tags & g_t)))
            for pref in preferences:
                name, code = pref
                if (code == 'non'):
                    log(LOG_DEBUG,'continue')
                    continue                
                if (self.selected_audio_stream and
                    self.selected_audio_stream.has_key('language') and
                    (code == self.selected_audio_stream['language'] or name == self.selected_audio_stream['language'])):
                        log(LOG_INFO, 'Selected audio language matches preference {0} ({1})'.format(i, name) )
                        return -1
                else:
                    for stream in self.audiostreams:
                        if ((code == stream['language']) or (name == stream['language'])):
                            log(LOG_INFO, 'Audio language of stream {0} matches preference {1} ({2})'.format(stream['index'], i, name) )
                            return stream['index']
                    log(LOG_INFO, 'Audio: preference {0} ({1}:{2}) not available'.format(i, name, code) )
        return -2
                
    def evalSubPrefs(self, sub_prefs):
        log(LOG_DEBUG, 'Evaluating subtitle preferences' )
        i = 0
        for pref in sub_prefs:
            i += 1
            g_t, preferences = pref
            # genre or tags are given (g_t not empty) but none of them matches the video's tags/genres
            if g_t and (not (self.genres_and_tags & g_t)):
                continue

            log(LOG_INFO,'Subtitle: genre/tag preference {0} met with intersection {1}'.format(g_t, (self.genres_and_tags & g_t)))
            for pref in preferences:
                name, code = pref       
                if (code == 'non'):
                    log(LOG_DEBUG,'continue')
                    continue 
                if (self.selected_sub and
                    self.selected_sub.has_key('language') and
                    (code == self.selected_sub['language'] or name == self.selected_sub['language'])):
                        log(LOG_INFO, 'Selected subtitle language matches preference {0} ({1})'.format(i, name) )
                        return -1
                else:
                    for sub in self.subtitles:
                        if ((code == sub['language']) or (name == sub['language'])):
                            log(LOG_INFO, 'Subtitle language of subtitle {0} matches preference {1} ({2})'.format(sub['index'], i, name) )
                            return sub['index']
                    log(LOG_INFO, 'Subtitle: preference {0} ({1}:{2}) not available'.format(i, name, code) )
        return -2

    def evalCondSubPrefs(self, condsub_prefs):
        log(LOG_DEBUG, 'Evaluating conditional subtitle preferences' )
        # if the audio track has been changed wait some time
        if (self.audio_changed and settings.delay > 0):
            log(LOG_DEBUG, "Delaying preferences evaluation by {0} ms".format(4*settings.delay))
            xbmc.sleep(4*settings.delay)
        log(LOG_DEBUG, 'Getting video properties')
        self.getDetails()
        i = 0
        for pref in condsub_prefs:
            i += 1
            g_t, preferences = pref
            # genre or tags are given (g_t not empty) but none of them matches the video's tags/genres
            if g_t and (not (self.genres_and_tags & g_t)):
                continue

            log(LOG_INFO,'Cond Sub: genre/tag preference {0} met with intersection {1}'.format(g_t, (self.genres_and_tags & g_t)))
            for pref in preferences:
                audio_name, audio_code, sub_name, sub_code = pref
                if (audio_code == 'non'):
                    log(LOG_DEBUG,'continue')
                    continue 
                if (self.selected_audio_stream and
                    self.selected_audio_stream.has_key('language') and
                    (audio_code == self.selected_audio_stream['language'] or audio_name == self.selected_audio_stream['language'])):
                        log(LOG_INFO, 'Selected audio language matches conditional preference {0} ({1}:{2})'.format(i, audio_name, sub_name) )
                        if (sub_code == 'non'):
                            return -1
                        else:
                            for sub in self.subtitles:
                                if ((sub_code == sub['language']) or (sub_name == sub['language'])):
                                    log(LOG_INFO, 'Language of subtitle {0} matches conditional preference {1} ({2}:{3})'.format(sub['index'], i, audio_name, sub_name) )
                                    return sub['index']
                            log(LOG_INFO, 'Conditional subtitle: no match found for preference {0} ({1}:{2})'.format(i, audio_name, sub_name) )
        return -2
    
    def getDetails(self):
        activePlayers ='{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
        json_query = xbmc.executeJSONRPC(activePlayers)
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        activePlayerID = json_response['result'][0]['playerid']
        details_query_dict = {  "jsonrpc": "2.0",
                                "method": "Player.GetProperties",
                                "params": { "properties": 
                                            ["currentaudiostream", "audiostreams", "subtitleenabled",
                                             "currentsubtitle", "subtitles" ],
                                            "playerid": activePlayerID },
                                "id": 1}
        details_query_string = simplejson.dumps(details_query_dict)
        json_query = xbmc.executeJSONRPC(details_query_string)
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        
        if json_response.has_key('result') and json_response['result'] != None:
            self.selected_audio_stream = json_response['result']['currentaudiostream']
            self.selected_sub = json_response['result']['currentsubtitle']
            self.selected_sub_enabled = json_response['result']['subtitleenabled']
            self.audiostreams = json_response['result']['audiostreams']
            self.subtitles = json_response['result']['subtitles']
        log(LOG_DEBUG, json_response )
        genre_tags_query_dict = {"jsonrpc": "2.0",
                                 "method": "Player.GetItem",
                                 "params": { "properties":
                                            ["genre", "tag"],
                                            "playerid": activePlayerID },
                                 "id": 1}
        genre_tags_query_string = simplejson.dumps(genre_tags_query_dict)
        json_query = xbmc.executeJSONRPC(genre_tags_query_string)
        json_query = unicode(json_query, 'utf-8', errors='ignore')
        json_response = simplejson.loads(json_query)
        if json_response.has_key('result') and json_response['result'] != None:
            gt = []
            if json_response['result']['item'].has_key('genre'):
                gt = json_response['result']['item']['genre']
            if json_response['result']['item'].has_key('tag'):
                gt.extend(json_response['result']['item']['tag'])
            self.genres_and_tags = set(map(lambda x:x.lower(), gt))
        log(LOG_DEBUG, 'Video tags/genres: {0}'.format(self.genres_and_tags))
        log(LOG_DEBUG, json_response )

if ( __name__ == "__main__" ):
    log(LOG_INFO, 'service {0} version {1} started'.format(__addonname__, __addonversion__))
    main = Main()
    log(LOG_INFO, 'service {0} version {1} stopped'.format(__addonname__, __addonversion__))
