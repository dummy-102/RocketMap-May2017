import random
import time

from datetime import datetime, timedelta
from base64 import b64encode

from .models import (Pokemon)


def fakeDittoGenerator(db_updates_queue):
    count = 0
    while True:
        time.sleep(3)
        count += 1
        fake_pokemon_objects = [{'name': 'Ditto',  # name only for dbg output
                                 'pokeid': 132,
                                 'time_left_in_seconds': 15,
                                 'latitude': 42.7,
                                 'longitude': -84.5 + count*.0002}]
        add_fake_pokemon(db_updates_queue, fake_pokemon_objects)


def add_fake_pokemon(db_updates_queue, fake_pokemon_objects):
    now_date = datetime.utcnow()
    pokemon = {}
    for obj in fake_pokemon_objects:
        fakeid = random.getrandbits(64)
        fakeidstr = str(fakeid).decode('UTF-8')
        time_left_in_seconds = obj['time_left_in_seconds']
        message = (obj['name'] + ' expires in ' +
                   str(time_left_in_seconds/60.) + ' minutes')
        if time_left_in_seconds <= 0 or time_left_in_seconds > 3600:
            print(message + ' (SKIPPING) (invalid expire time)')
            continue
        print(message)
        disappear_time = (now_date +
                          timedelta(seconds=time_left_in_seconds))
        pokemon[fakeid] = {
            'encounter_id': b64encode(str(fakeid)),
            'spawnpoint_id': fakeidstr,
            'pokemon_id': obj['pokeid'],
            'latitude': obj['latitude'],
            'longitude': obj['longitude'],
            'disappear_time': disappear_time,
            'individual_attack': None,
            'individual_defense': None,
            'individual_stamina': None,
            'move_1': None,
            'move_2': None,
            'cp': None,
            'height': None,
            'weight': None,
            'gender': None,
            'form': None,
            }

    if pokemon:
        db_updates_queue.put((Pokemon, pokemon))


def fake_search_thread(db_updates_queue):
    # pass control to custom pokemon-generating function
    fakeDittoGenerator(db_updates_queue)
