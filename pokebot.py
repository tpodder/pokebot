# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import time
import struct
import random
import logging
import requests
import argparse
import pprint
import pykemon

from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f
from pgoapi import utilities as util

from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import Cell, CellId, LatLng

import os
import time
from slackclient import SlackClient
    
    
    

log = logging.getLogger(__name__)

import os
import time




# starterbot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

# constants
AT_BOT = "<@" + BOT_ID + ">:"
ABOUT_POKEBOT_COMMAND = "about pokebot"
ABOUT_POKEMON_COMMAND = "about pokemon"

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

with open('pokemonNames.json') as data_file:    
    pokemonNames = json.load(data_file)

def handle_command(command, channel):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
               "* command with numbers, delimited by spaces."
    if command.startswith(ABOUT_POKEBOT_COMMAND):
        response = "Hi, I'm pokebot! :simple_smile: I send you alerts about nearby pokemon so that you can catch 'em all."
    if command.startswith(ABOUT_POKEMON_COMMAND):
        pokemon_name = command.split()[-1]
        import urllib2, json
        url = "http://pokeapi.co/api/v2/pokemon/"+pokemon_name
        print url
        hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
        req = urllib2.Request(url, headers=hdr)
        try: 
            response = urllib2.urlopen(req)
            data = json.loads(response.read())
            response = "\t\tInfomon :poke:\nName:\t"+str(data['name']) +"\nBase Experience:\t"+str(data['base_experience'])+"\nHeight:\t"+str(data['height']/float(10))+" m"+"\nWeight:\t"+str(data['weight']/float(10))+" kg"+"\nSpecies:\t"+data['species']['name']+"\nAbilities:\t"
            for ability in data['abilities']:
                response += ability['ability']['name']+", "
            response = response[:-2]
            response += "\nTypes:\t"
            for poketype in data['types']:
                response += poketype['type']['name']+", "
            response = response[:-2]
        except urllib2.HTTPError, error:
            response = "Sorry, pokemon not found. Are you sure that pokemon exists?"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True,
                username='pokebot')


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None

def get_pos_by_name(location_name):
    geolocator = GoogleV3()
    loc = geolocator.geocode(location_name)
    if not loc:
        return None

    log.info('Your given location: %s', loc.address.encode('utf-8'))
    log.info('lat/long/alt: %s %s %s', loc.latitude, loc.longitude, loc.altitude)

    return (loc.latitude, loc.longitude, loc.altitude)

def get_cell_ids(lat, long, radius = 20):
    origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
    walk = [origin.id()]
    right = origin.next()
    left = origin.prev()

    # Search around provided radius
    for i in range(radius):
        walk.append(right.id())
        walk.append(left.id())
        right = right.next()
        left = left.prev()

    # Return everything
    return sorted(walk)

def encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)

def init_config():
    parser = argparse.ArgumentParser()
    config_file = "config.json"

    # If config file exists, load variables from json
    load   = {}
    if os.path.isfile(config_file):
        with open(config_file) as data:
            load.update(json.load(data))

    # Read passed in Arguments
    required = lambda x: x not in load
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')",
        required=required("auth_service"))
    parser.add_argument("-u", "--username", help="Username", required=required("username"))
    parser.add_argument("-p", "--password", help="Password", required=required("password"))
    parser.add_argument("-l", "--location", help="Location", required=required("location"))
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("-t", "--test", help="Only parse the specified location", action='store_true')
    parser.set_defaults(DEBUG=False, TEST=False)
    config = parser.parse_args()

    # Passed in arguments shoud trump
    for key in config.__dict__:
        if key in load and config.__dict__[key] == None:
            config.__dict__[key] = load[key]

    if config.auth_service not in ['ptc', 'google']:
      log.error("Invalid Auth service specified! ('ptc' or 'google')")
      return None

    return config

def main():
    # log settings
    # log format
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
    # log level for http request class
    logging.getLogger("requests").setLevel(logging.WARNING)
    # log level for main pgoapi class
    logging.getLogger("pgoapi").setLevel(logging.INFO)
    # log level for internal pgoapi class
    logging.getLogger("rpc_api").setLevel(logging.INFO)

    
    # starterbot's ID as an environment variable
    BOT_ID = os.environ.get("BOT_ID")
    

    config = init_config()
    if not config:
        return

    if config.debug:
        logging.getLogger("requests").setLevel(logging.DEBUG)
        logging.getLogger("pgoapi").setLevel(logging.DEBUG)
        logging.getLogger("rpc_api").setLevel(logging.DEBUG)

    position = get_pos_by_name(config.location)
    if not position:
        return
        
    if config.test:
        return

    # instantiate pgoapi
    api = PGoApi()

    # provide player position on the earth
    api.set_position(*position)

    if not api.login(config.auth_service, config.username, config.password):
        return

    # chain subrequests (methods) into one RPC call
        

    # get player profile call
    # ----------------------
    response_dict = api.get_player()

    # apparently new dict has binary data in it, so formatting it with this method no longer works, pprint works here but there are other alternatives    
    # print('Response dictionary: \n\r{}'.format(json.dumps(response_dict, indent=2)))
     # instantiate Slack & Twilio clients
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    starttime=time.time()
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            currentTime = time.time()
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            if currentTime >= starttime + 60:
                starttime = time.time()
                find_poi(api, position[0], position[1], slack_client)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")

def find_poi(api, lat, lng, slack_client):
    poi = {'pokemons': {}, 'forts': []}
    coords = coords_square(lat, lng)
    for coord in coords:
        lat = coord['lat']
        lng = coord['lng']
        api.set_position(lat, lng, 0)

        from geopy.geocoders import Nominatim
        geolocator = Nominatim()
        cell_ids = get_cell_ids(lat, lng)
        timestamps = [0,] * len(cell_ids)
        response_dict = api.get_map_objects(latitude = util.f2i(lat), longitude = util.f2i(lng), since_timestamp_ms = timestamps, cell_id = cell_ids)
        if (response_dict['responses']):
            if 'status' in response_dict['responses']['GET_MAP_OBJECTS']:
                if response_dict['responses']['GET_MAP_OBJECTS']['status'] == 1:
                    for map_cell in response_dict['responses']['GET_MAP_OBJECTS']['map_cells']:
                        if 'wild_pokemons' in map_cell:
                            for pokemon in map_cell['wild_pokemons']:
                                pokekey = get_key_from_pokemon(pokemon)
                                pokemon['hides_at'] = (pokemon['time_till_hidden_ms']/1000)/60
                                address = geolocator.reverse(repr(pokemon['latitude'])+", "+repr(pokemon['longitude'])).address
                                sep = ', Financial District'
                                rest = address.split(sep, 1)[0]
                                pokemon['location'] = rest  
                                pokemon['name'] = pokemonNames[pokemon['pokemon_data']['pokemon_id']-1]
                                poi['pokemons'][pokekey] = pokemon
                    
            time.sleep(0.7)
    textSlack = ""
    for pokemon in poi['pokemons']:
        print(pokemon)
        textSlack += poi['pokemons'][pokemon]['name']+" at " + poi['pokemons'][pokemon]['location']+ " hiding for "+"{0:.2f}".format(poi['pokemons'][pokemon]['hides_at']) + " minutes \n"
            
            
    slack_client.api_call(
                "chat.postMessage", channel="#pokemon", text=textSlack,
                username='pokebot', as_user = True
        )
    print('POI dictionary: \n\r{}'.format(pprint.PrettyPrinter(indent=4).pformat(poi)))
    print('Open this in a browser to see the path the spiral search took:')
    print_gmaps_dbug(coords)
    
def get_key_from_pokemon(pokemon):
    return '{}-{}'.format(pokemon['spawn_point_id'], pokemon['pokemon_data']['pokemon_id'])

def print_gmaps_dbug(coords):
    url_string = 'http://maps.googleapis.com/maps/api/staticmap?size=400x400&path='
    for coord in coords:
        url_string += '{},{}|'.format(coord['lat'], coord['lng'])
    print(url_string[:-1])

#http://gis.stackexchange.com/questions/15545/calculating-coordinates-of-square-x-miles-from-center-point
def coords_square(starting_lat, starting_lng):
    import math
    coords = [{'lat': starting_lat, 'lng': starting_lng}]
    dlat = 0.060/69        # North-south distance in degrees
    dlon = dlat / math.cos(starting_lat) # East-west distance in degrees
    southernMostLat = starting_lat - dlat 
    northernMostLat = starting_lat + dlat 
    westernLong = starting_lng - dlon 
    easternLong = starting_lng + dlon 
    coords.append({'lat': southernMostLat, 'lng': westernLong})
    coords.append({'lat': northernMostLat, 'lng': westernLong})
    coords.append({'lat': northernMostLat, 'lng': easternLong})
    coords.append({'lat': southernMostLat, 'lng': easternLong})
    return coords

if __name__ == '__main__':
    main()