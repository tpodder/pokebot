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
import urllib2, json
import random

from pgoapi import pgoapi
from pgoapi import utilities as util

from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import Cell, CellId, LatLng

from slackclient import SlackClient
    
log = logging.getLogger(__name__)

# starterbot's ID as an environment variable
BOT_ID = os.environ.get("BOT_ID")

# constants
AT_BOT = "<@" + BOT_ID + ">"
ABOUT_POKEBOT_COMMAND = "about pokebot"
ABOUT_POKEMON_COMMAND = "about pokemon"
JOKE_COMMAND = "jokemon"
QUOTES_COMMAND = "quotemon"
SPECIAL_ALERT_COMMAND = "pokelist"
RESET_LIST_COMMAND = "reset pokelist"
REMOVE_POKEMON_COMMAND = "remove pokemon"
CHECK_LIST_COMMAND = "my pokelist"
HELP_COMMAND = "help"
NO_LIST_USER = "You don't have any pokemon. To add pokemon enter command \"pokemon list\""

MINIMUM_ALERT_TIME_UB = 2.5
MINIMUM_ALERT_TIME_LB = 1.5

# instantiate Slack & Twilio clients
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))

with open('pokemonNames.json') as data_file:    
    pokemonNames = json.load(data_file)

with open('pokemonMemes.json') as data_file:    
    pokemonMemes = json.load(data_file)
    
with open('pokemonQuotes.json') as data_file:    
    pokemonQuotes = json.load(data_file)
    
pokemonMemesSize = len(pokemonMemes)
pokemonQuotesSize = len(pokemonQuotes)

laughingResponses = [ "LOL :joy: :laughing:", "ROFL :laughing: :joy:", "haha :joy: :joy: :joy:", "Get it, eh? :wink:"]
laughingResponsesSize = len(laughingResponses)

quoteResponses = ["Have a great day :simple_smile:", ":+1: :ok_hand: :simple_smile:", ":upside_down_face:"]
quoteResponsesSize = len(quoteResponses)

unwantedPokemon = [ "Jynx", "Zubat", "Rattata", "Drowzee"]

specialAlertUser = {}


#https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Hi! I'm not sure what you mean. :confused:\nWhat can I do?\n- I send you alerts about nearby pokemon. :poke:"
    useCommandResponse ="\nUse command\n- about pokebot: To know more about me. \n- about pokemon pokemon_name: To know more about your favourite pokemon. \n- jokemon: I'll tell you pokemon jokes and share memes.\n- quotemon: I'll share quotes with you\n Get special alerts for the pokemons you want the most. Use commands\n- pokelist: Enter a list of the pokemon you want. Make sure you enter the list along with the command.\n- reset pokelist: Empties your pokelist. \n- remove pokemon: Removes the pokemon(s) from your list.\n- my pokelist: See pokemons in your pokelist  "
    response = response + useCommandResponse
    if command.startswith(ABOUT_POKEBOT_COMMAND) or command.startswith("hi") or command.startswith("Hi") or command.startswith("Hi!") or command.startswith("What's up?") or command.startswith("sup"):
        response = "Hi, I'm pokebot! :simple_smile: I send you alerts about nearby pokemon so that you can catch 'em all." + useCommandResponse
    if command.startswith(HELP_COMMAND):
        response = "Pokebot is here to help :simple_smile:\n" + useCommandResponse
    if command.startswith(ABOUT_POKEMON_COMMAND):
        pokemon_name = command.split()[-1]
        response = get_pokemon_info(pokemon_name)
    if command.startswith(JOKE_COMMAND):
        randomMemeIndex = random.randint(0,pokemonMemesSize - 1)
        randomLaughingResponsesIndex = random.randint(0,laughingResponsesSize - 1)
        response = laughingResponses[randomLaughingResponsesIndex]+"\n"+pokemonMemes[randomMemeIndex]
    if command.startswith(QUOTES_COMMAND):
        randomQuoteIndex = random.randint(0,pokemonQuotesSize - 1)
        randomQuoteResponsesIndex = random.randint(0,quoteResponsesSize - 1)
        response = quoteResponses[randomQuoteResponsesIndex]+"\n"+pokemonQuotes[randomQuoteIndex]
    if command.startswith(SPECIAL_ALERT_COMMAND):
        response, channel = get_listed_pokemon_response(command, channel, user)
    if command.startswith(RESET_LIST_COMMAND):
       if isEmptyPokelist(user):
           response = NO_LIST_USER
       else:
           specialAlertUser[user] = []
           response = "Pokelist reset"
           channel = user
    if command.startswith(REMOVE_POKEMON_COMMAND):
       response, channel = remove_pokemon(command, channel, user)
    if command.startswith(CHECK_LIST_COMMAND):
        response = print_list(user)
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
                       output['channel'], output['user']
    return None, None, None
    
def get_pokemon_info(pokemon_name):
     url = "http://pokeapi.co/api/v2/pokemon/"+pokemon_name
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
     return response
     
def get_listed_pokemon_response(command, channel, user):
    command = command.lower()
    wantedPokemons = command.split()
    wantedPokemons.remove('pokelist') # remove the first two elements 'pokemon list'
    if len(wantedPokemons) > 0:
        if user in specialAlertUser.keys():
            specialAlertUser[user].extend(wantedPokemons)
        else:
            specialAlertUser[user] = wantedPokemons
        response = "Special alert activated for pokemon:\n"
        for pokemon in wantedPokemons:
            response += pokemon + "\n"
            channel = user
    else:
        response = "Please enter a list of pokemon along with the command.\nExample: pokemon list\npikachu\nbutterfree\njynx"
    return response, channel

def remove_pokemon(command, channel, user):
    command = command.lower()
    unwantedPokemons = command.split()
    unwantedPokemons.remove('remove') # remove the first two elements 'pokemon list'
    unwantedPokemons.remove('pokemon')
    if len(unwantedPokemons) > 0:
        if isEmptyPokelist(user):
            response = NO_LIST_USER
        else:
            response = "Removed pokemon:\n"
            for pokemon in unwantedPokemons:
                specialAlertUser[user].remove(pokemon)
                response += pokemon + "\n"
        channel = user
    else:
        response = "Please enter a list of pokemon along with the command.\nExample: remove pokemon:\npikachu\nbutterfree\njynx"
    return response, channel

def print_list(user):
    if isEmptyPokelist(user):
        response = NO_LIST_USER 
    else:
        pokeList = specialAlertUser[user]
        response = "Your list:\n"
        for pokemon in pokeList:
            response += pokemon + "\n"
    return response

def isEmptyPokelist(user):
    if user in specialAlertUser.keys() and len(specialAlertUser[user]) > 0:
        return False
    return True

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
    required = lambda x: not x in load
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')",
        required=required("auth_service"))
    parser.add_argument("-u", "--username", help="Username", required=required("username"))
    parser.add_argument("-p", "--password", help="Password")
    parser.add_argument("-l", "--location", help="Location", required=required("location"))
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("-t", "--test", help="Only parse the specified location", action='store_true')
    parser.add_argument("-px", "--proxy", help="Specify a socks5 proxy url")
    parser.set_defaults(DEBUG=False, TEST=False)
    config = parser.parse_args()

    # Passed in arguments shoud trump
    for key in config.__dict__:
        if key in load and config.__dict__[key] == None:
            config.__dict__[key] = str(load[key])

    if config.__dict__["password"] is None:
        log.info("Secure Password Input (if there is no password prompt, use --password <pw>):")
        config.__dict__["password"] = getpass.getpass()

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
    api =  pgoapi.PGoApi()

    # provide player position on the earth
    api.set_position(*position)

    if not api.login(config.auth_service, config.username, config.password):
        return

    # chain subrequests (methods) into one RPC call
    api.activate_signature("encrypt64bit.dll")    

    # get player profile call
    # ----------------------
    #response_dict = api.get_player()

    # apparently new dict has binary data in it, so formatting it with this method no longer works, pprint works here but there are other alternatives    
    # print('Response dictionary: \n\r{}'.format(json.dumps(response_dict, indent=2)))
     # instantiate Slack & Twilio clients
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    starttime=time.time()
    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            currentTime = time.time()
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, user)
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
                                pokemon['name'] = pokemonNames[pokemon['pokemon_data']['pokemon_id']-1]
                                pokemon['hides_at'] = (pokemon['time_till_hidden_ms']/1000)/60
                                if pokemon['name'] not in unwantedPokemon and pokemon['hides_at'] >= MINIMUM_ALERT_TIME_LB and pokemon['hides_at'] <= MINIMUM_ALERT_TIME_UB:
                                    address = geolocator.reverse(repr(pokemon['latitude'])+", "+repr(pokemon['longitude'])).address
                                    sep = ', Financial District'
                                    rest = address.split(sep, 1)[0]
                                    pokemon['location'] = rest  
                                    poi['pokemons'][pokekey] = pokemon
                                    for user in specialAlertUser:
                                        pokemonList = specialAlertUser[user]
                                        searchFor =  pokemon['name'].lower()
                                        if searchFor in  pokemonList:
                                            text = searchFor+" at "+pokemon['location']+"hidinf for"+"{0:.2f}".format(pokemon['hides_at']) + " minutes \n"
                                            slack_client.api_call(
                                                                "chat.postMessage", channel=user, text=text,
                                                                username='pokebot', as_user = True
                                                        )
                                    
                                    
                    
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