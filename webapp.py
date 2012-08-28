# -*- coding: utf-8 -*-
#
# The Flask part of iposonic
#
# author: Roberto Polli robipolli@gmail.com (c) 2012
#
# License AGPLv3
from flask import Flask
from flask import request, send_file
from flask import Response

import os,sys,random
import simplejson
from os.path import join,dirname,abspath
import logging

from iposonic import Iposonic, IposonicException, SubsonicProtocolException, ResponseHelper, MediaManager
from iposonic import Album, Artist
from iposonic import StringUtils
app = Flask(__name__)

log = logging.getLogger('iposonic-webapp')

#
# Configuration
#
music_folders = ["/opt/music/"]

iposonic = Iposonic(music_folders)

###
# The web
###

#
# Test connection
#
@app.route("/rest/ping.view", methods = ['GET', 'POST'])
def ping_view():
    (u,p,v,c) = [request.args.get(x, None) for x in ['u','p','v','c']]
    print "songs: %s" % iposonic.songs
    print "albums: %s" % iposonic.albums
    print "artists: %s" % iposonic.artists

    return request.formatter({})

@app.route("/rest/getLicense.view", methods = ['GET', 'POST'])
def get_license_view():
    (u,p,v,c) = [request.args.get(x, None) for x in ['u','p','v','c']]
    return ResponseHelper.responsize("""<license valid="true" email="foo@bar.com" key="ABC123DEF" date="2009-09-03T14:46:43"/>""")

#
# List music collections
#
@app.route("/rest/getMusicFolders.view", methods = ['GET', 'POST'])
def get_music_folders_view():
    (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]
    return request.formatter({ 'musicFolders': { 
                'musicFolder' : [{'id': MediaManager.get_entry_id(d), 'name': d } for d in iposonic.music_folders if os.path.isdir(d)] 
                }
                })
                
                

@app.route("/rest/getIndexes.view", methods = ['GET', 'POST'])
def get_indexes_view():
    """
    Return subsonic indexes.
    Request:
      u=Aaa&p=enc:616263&v=1.2.0&c=android&ifModifiedSince=0&musicFolderId=591521045
    Response:
    <indexes lastModified="237462836472342">
      <shortcut id="11" name="Audio books"/>
      <shortcut id="10" name="Podcasts"/>
      <index name="A">
        <artist id="1" name="ABBA"/>
        <artist id="2" name="Alanis Morisette"/>
        <artist id="3" name="Alphaville"/>
      </index>
      <index name="B">
        <artist name="Bob Dylan" id="4"/>
      </index>

      <child id="111" parent="11" title="Dancing Queen" isDir="false"
      album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="24"
      size="8421341" contentType="audio/mpeg" suffix="mp3" duration="146" bitRate="128"
      path="ABBA/Arrival/Dancing Queen.mp3"/>

      <child id="112" parent="11" title="Money, Money, Money" isDir="false"
      album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="25"
      size="4910028" contentType="audio/flac" suffix="flac"
      transcodedContentType="audio/mpeg" transcodedSuffix="mp3"  duration="208" bitRate="128"
      path="ABBA/Arrival/Money, Money, Money.mp3"/>
    </indexes>

    TODO implement @param musicFolderId
    TODO implement @param ifModifiedSince
    """
    # refresh indexes
    iposonic.walk_music_directory()

    #
    # XXX sample code to support jsonp clients
    #     this should be managed with some
    #     @jsonp_formatter
    #
    # XXX we should think to reimplement the
    #     DB in some consistent way before
    #     wasting time with unsearchable, dict-based
    #     data to format
    #
    (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]
    log.info("response is %s" % f)

    indexes_j = {'index' : []}
    ret = ""
    for (k,v) in iposonic.indexes.iteritems():
        item =  {'name': k, 'artist': [ item['artist'] for item in v ] }
        indexes_j['index'].append (item)
            
            
    return request.formatter( { 'indexes': indexes_j})

@app.route("/rest/getMusicDirectory.view", methods = ['GET', 'POST'])
def get_music_directory_view():
    """
      request:
        /rest/getMusicDirectory.view?u=Aaa&p=enc:616263&v=1.2.0&c=android&id=-493506601
      response1:
      <directory id="1" name="ABBA">
        <child id="11" parent="1" title="Arrival" artist="ABBA" isDir="true" coverArt="22"/>
        <child id="12" parent="1" title="Super Trouper" artist="ABBA" isDir="true" coverArt="23"/>
      </directory>

      response2:
      <directory id="11" parent="1" name="Arrival">
        <child id="111" parent="11" title="Dancing Queen" isDir="false"
        album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="24"
        size="8421341" contentType="audio/mpeg" suffix="mp3" duration="146" bitRate="128"
        path="ABBA/Arrival/Dancing Queen.mp3"/>

        <child id="112" parent="11" title="Money, Money, Money" isDir="false"
        album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="25"
        size="4910028" contentType="audio/flac" suffix="flac"
        transcodedContentType="audio/mpeg" transcodedSuffix="mp3"  duration="208" bitRate="128"
        path="ABBA/Arrival/Money, Money, Money.mp3"/>
      </directory>

        TODO getAlbumArt
        TODO getBitRate
    """
    (u, p, v, c, f, callback, dir_id) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback', 'id']]

    if not dir_id:
        raise SubsonicProtocolException("Missing required parameter: 'id' in getMusicDirectory.view")
    (path, dir_path) = iposonic.get_directory_path_by_id(dir_id)
    artist = Artist(path)
    children = []
    for child in os.listdir(dir_path):
        if child[0] in ['.','_']:
            continue
        path = join("/", dir_path, child)
        try:
          child_j = {}
          is_dir = os.path.isdir(path)
          # This is a Lazy Indexing. It should not be there
          #   unless a cache is set
          # XXX
          eid = iposonic.add_entry(path, album = is_dir)
          child_j = iposonic.get_entry_by_id(eid)
          _child_j = {
            'id' : MediaManager.get_entry_id(path),
            'parent' : dir_id,
            'title' : child,
            'artist' : artist['name'],
            'isDir': str(is_dir).lower(),
            'coverArt' : 0
            }
          if not is_dir:
            info = iposonic.get_song_by_id(eid)
            track = info.get('tracknumber',0)
            try:
                track = int(track)
            except:
                track = 0
            child_j.update({
              'track' : str(track),
#              'year' : 0,
#              'genre' : info.get('genre',0),
              'size'  : os.path.getsize(path),
              'suffix' : path[-3:],
              'path'  : path
              })
            if info:
                child_j.update(info)
          children.append(child_j)  
        except IposonicException as e:
          log.info (e)
          

    return request.formatter({'directory': {'id' : dir_id, 'name': artist['name'], 'child': children}})
    



#
# Search
#
#@app.route("/rest/search2.view", methods = ['GET', 'POST'])
def search2_mock():
    album = {'album': [{'album': u'Bach Violin Concertos (PREVIEW: buy it at www.magnatune.com)', 'isDir': 'false', 'parent': '759327748', 'artist': u'Lara St John (PREVIEW: buy it at www.magnatune.com)', 'title': u'BWV 1041 : I. Allegro (PREVIEW: buy it at www.magnatune.com)', 'genre': u'Classical', 'path': '/home/rpolli/workspace-py/iposonic/test/data/lara.mp3', 'date': u'2001', 'tracknumber': u'1', 'id': '-780183664'}], 'title': [{'album': u'Bach Violin Concertos (PREVIEW: buy it at www.magnatune.com)', 'isDir': 'false', 'parent': '759327748', 'artist': u'Lara St John (PREVIEW: buy it at www.magnatune.com)', 'title': u'BWV 1041 : I. Allegro (PREVIEW: buy it at www.magnatune.com)', 'genre': u'Classical', 'path': '/home/rpolli/workspace-py/iposonic/test/data/lara.mp3', 'date': u'2001', 'tracknumber': u'1', 'id': '-780183664'}], 'artist': [{'album': u'Bach Violin Concertos (PREVIEW: buy it at www.magnatune.com)', 'isDir': 'false', 'parent': '759327748', 'artist': u'Lara St John (PREVIEW: buy it at www.magnatune.com)', 'title': u'BWV 1041 : I. Allegro (PREVIEW: buy it at www.magnatune.com)', 'genre': u'Classical', 'path': '/home/rpolli/workspace-py/iposonic/test/data/lara.mp3', 'date': u'2001', 'tracknumber': u'1', 'id': '-780183664'}]}
    album= [{'album': x} for x in album['album']]
    
    return ResponseHelper.responsize(jsonmsg=
      {'searchResult2':
        {'__content': album }}
      )

@app.route("/rest/search2.view", methods = ['GET', 'POST'])
def search2_view():
    """
    request:
      u=Aaa&p=enc:616263&v=1.2.0&c=android&query=Mannoia&artistCount=10&albumCount=20&songCount=25

    response:
        <searchResult2>
        <artist id="1" name="ABBA"/>
        <album id="11" parent="1" title="Arrival" artist="ABBA" isDir="true" coverArt="22"/>
        <album id="12" parent="1" title="Super Trouper" artist="ABBA" isDir="true" coverArt="23"/>
        <song id="112" parent="11" title="Money, Money, Money" isDir="false"
              album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="25"
              size="4910028" contentType="audio/flac" suffix="flac"
              transcodedContentType="audio/mpeg" transcodedSuffix="mp3"
              path="ABBA/Arrival/Money, Money, Money.mp3"/>
    </searchResult2>

    """
    if not 'query' in request.args:
        raise SubsonicProtocolException("Missing required parameter: 'query' in search2_view.view")
        
    (query, artistCount, albumCount, songCount) = [request.args[x] for x in ("query", "artistCount", "albumCount", "songCount")]

    # ret is 
    ret = iposonic.search2(query, artistCount, albumCount, songCount)
    songs = [{'song': s } for s in ret['title']]
    songs.extend([{'album': a} for a in ret['album']])
    songs.extend([{'artist': a} for a in ret['artist']])
    return ResponseHelper.responsize(jsonmsg=
      {'searchResult2':
        {'__content': songs }}
      )
    raise NotImplemented("WriteMe")





#
# Extras
#
@app.route("/rest/getAlbumList.view", methods = ['GET', 'POST'])
def get_album_list_view():

    """
    http://your-server/rest/getAlbumList.view
    type    Yes     The list type. Must be one of the following: random, newest, highest, frequent, recent. Since 1.8.0 you can also use alphabeticalByName or alphabeticalByArtist to page through all albums alphabetically, and starred to retrieve starred albums.
    size    No  10  The number of albums to return. Max 500.
    offset  No  0   The list offset. Useful if you for example want to page through the list of newest albums.


    <albumList>
            <album id="11" parent="1" title="Arrival" artist="ABBA" isDir="true" coverArt="22" userRating="4" averageRating="4.5"/>
            <album id="12" parent="1" title="Super Trouper" artist="ABBA" isDir="true" coverArt="23" averageRating="4.4"/>
        </albumList>
    """
    mock_albums= [
      {'album': {'id': 11, 'parent': 1, 'title' : 'Arrival', 'artist': 'ABBA', 'isDir': 'true'}}
      ]
    if not 'type' in request.args:
        raise SubsonicProtocolException("Type is a require parameter")

    #albums = randomize(iposonic.albums, 20)
    albums = [{'album' : a } for a in iposonic.albums.values()]
    albumList = {'albumList' : {'__content' : albums}}
    return ResponseHelper.responsize(jsonmsg = albumList)

def randomize(dictionary, limit = 20):
    a_all = dictionary.keys()
    a_max = len(a_all)
    ret = []
    r = 0

    if not a_max:
        return ret

    try:
      for x in range(0,limit):
          r = random.randint(0,a_max-1)
          k_rnd = a_all[r]
          ret.append(dictionary[k_rnd])
      return ret
    except:
      print "a_all:%s" % a_all
      raise

def randomize2(dictionary, limit = 20):
    a_max = len(dictionary)
    ret = []

    for (k,v) in dictionary.iteritems():
        k_rnd = random.randint(0,a_max)
        if k_rnd > limit: continue
        ret.append(v)
    return ret

    
@app.route("/rest/getRandomSongs.view", methods = ['GET', 'POST'])
def get_random_songs_view():
    """

    request:
      size    No  10  The maximum number of songs to return. Max 500.
      genre   No      Only returns songs belonging to this genre.
      fromYear    No      Only return songs published after or in this year.
      toYear  No      Only return songs published before or in this year.
      musicFolderId   No      Only return songs in the music folder with the given ID. See getMusicFolders.

    response:
      <randomSongs>
      <song id="111" parent="11" title="Dancing Queen" isDir="false"
      album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="24"
      size="8421341" contentType="audio/mpeg" suffix="mp3" duration="146" bitRate="128"
      path="ABBA/Arrival/Dancing Queen.mp3"/>

      <song id="112" parent="11" title="Money, Money, Money" isDir="false"
      album="Arrival" artist="ABBA" track="7" year="1978" genre="Pop" coverArt="25"
      size="4910028" contentType="audio/flac" suffix="flac"
      transcodedContentType="audio/mpeg" transcodedSuffix="mp3"  duration="208" bitRate="128"
      path="ABBA/Arrival/Money, Money, Money.mp3"/>
      </randomSongs>
    """
    #(size, genre, fromYear, toYear, musicFolderId) = [request.args(x) for x in ('size','genre','fromYear', 'toYear', 'musicFolderId')]
    genre = None
    songs = []
    if genre:
        print "genre: %s" % genre
        songs = iposonic.get_genre_songs(genre)
    else:
        assert len(iposonic.songs.values())
        songs = iposonic.songs.values()
    assert songs
    #raise NotImplemented("WriteMe")
    songs = [{'song': s} for s in songs]
    randomSongs = {'randomSongs' : {'__content' : songs}}
    return ResponseHelper.responsize(jsonmsg = randomSongs)




#
# download and stream
#

@app.route("/rest/stream.view", methods = ['GET', 'POST'])
def stream_view():
  """@params ?u=Aaa&p=enc:616263&v=1.2.0&c=android&id=1409097050&maxBitRate=0

  """
  (u, p, v, c, f, callback, eid) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback','id']]

  print("request.headers: %s" % request.headers)
  if not eid:
      raise SubsonicProtocolException("Missing required parameter: 'id' in stream.view")
  info = iposonic.get_song_by_id(eid)
  assert 'path' in info, "missing path in song: %s" % info
  if os.path.isfile(info['path']):
      fp = open(info['path'], "r")
      print "sending static file: %s" % info['path']
      return send_file(info['path'])
  raise IposonicException("why here?")

@app.route("/rest/download.view", methods = ['GET', 'POST'])
def download_view():
  """@params ?u=Aaa&p=enc:616263&v=1.2.0&c=android&id=1409097050&maxBitRate=0

  """
  if not 'id' in request.args:
      raise SubsonicProtocolException("Missing required parameter: 'id' in stream.view")
  info = iposonic.get_song_by_id(request.args['id'])
  assert 'path' in info, "missing path in song: %s" % info
  if os.path.isfile(info['path']):
      return send_file(info['path'])
  raise IposonicException("why here?")




@app.route("/rest/scrobble.view", methods = ['GET', 'POST']) 
def scrobble_view():
    """Add song to last.fm"""
    (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]

    return request.formatter({})

#
# TO BE DONE
#
@app.route("/rest/getCoverArt.view", methods = ['GET', 'POST']) 
def get_cover_art_view():
    raise NotImplemented("WriteMe")

@app.route("/rest/getLyrics.view", methods = ['GET', 'POST'])
def get_lyrics_view():
    raise NotImplemented("WriteMe")



#
# Helpers
#
def get_formatter(request):
    try:
        f = request.args['f']
        if f  == "jsonp" and 'callback' in request.args:
            return jsonp_formatter
    except:
        return xml_formatter


    
@app.before_request
def responsizer():
    """Return a function to create the response."""
    (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]
    if f == 'jsonp':
        if not callback: raise SubsonicProtocolException("Missing callback with jsonp")
        request.formatter = lambda x : ResponseHelper.responsize_jsonp(x, callback)
    else:
        request.formatter = lambda x : ResponseHelper.responsize_xml(x)
    

@app.after_request
def after_request(response):
    print("response: %s" %response.data)
    (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]
    if f == 'jsonp':
        response.headers['content-type'] = 'application/json'
    return response

@app.after_request
def fix_content_length_for_static(res):
  (u, p, v, c, f, callback) = [request.args.get(x, None) for x in ['u','p','v','c','f','callback']]

  # problems behind Nginx with HTTPS
  print("request: %s" %request.path)
  if request.endpoint == 'stream_view':
     directory = dirname(abspath(__file__))
     requested_file = join(directory,request.path[1:]) # what about when 404?
     res.headers.add("Content-Length", str(os.path.getsize(requested_file))) # do I need to sanitize this to stop ../../ attacks
  return res




if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

