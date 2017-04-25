import logging
from base64 import b64decode
from threading import Lock

import time

import sys
from pgoapi import PGoApi

from pogom import schedulers
from pogom.account import check_login, get_player_level
from pogom.models import Pokemon
from pogom.transform import jitter_location
from pogom.utils import get_args, get_pokemon_name

log = logging.getLogger(__name__)

args = get_args()
api = None
key_scheduler = schedulers.KeyScheduler(args.hash_key)

scoutLock = Lock()
last_scout_timestamp = None
encounter_cache = {}


def encounter_request(encounter_id, spawnpoint_id, latitude, longitude):
    req = api.create_request()
    encounter_result = req.encounter(
        encounter_id=encounter_id,
        spawn_point_id=spawnpoint_id,
        player_latitude=latitude,
        player_longitude=longitude)
    encounter_result = req.check_challenge()
    encounter_result = req.get_hatched_eggs()
    encounter_result = req.get_inventory()
    encounter_result = req.check_awarded_badges()
    encounter_result = req.download_settings()
    encounter_result = req.get_buddy_walked()
    return req.call()


def has_captcha(request_result):
    captcha_url = request_result['responses']['CHECK_CHALLENGE'][
        'challenge_url']
    return len(captcha_url) > 1


def calc_pokemon_level(pokemon_info):
    cpm = pokemon_info["cp_multiplier"]
    if cpm < 0.734:
        level = 58.35178527 * cpm * cpm - 2.838007664 * cpm + 0.8539209906
    else:
        level = 171.0112688 * cpm - 95.20425243
    level = (round(level) * 2) / 2.0
    return level


def scout_error(error_msg):
    log.error(error_msg)
    return {"msg": error_msg}


def parse_scout_result(request_result, encounter_id, pokemon_name):
    global encounter_cache

    if has_captcha(request_result):
        return scout_error("Failure: Scout account captcha'd.")

    if request_result is None:
        return scout_error("Unknown failure")

    encounter_result = request_result.get('responses', {}).get('ENCOUNTER', {})

    if encounter_result.get('status', None) == 3:
        return scout_error("Failure: Pokemon already despawned.")

    if 'wild_pokemon' not in encounter_result:
        return scout_error("No wild pokemon info found")

    pokemon_info = encounter_result['wild_pokemon']['pokemon_data']
    cp = pokemon_info["cp"]
    level = calc_pokemon_level(pokemon_info)
    trainer_level = get_player_level(request_result)
    response = {
        'cp': cp,
        'level': level,
        'trainer_level': trainer_level,
        'atk': pokemon_info.get('individual_attack', 0),
        'def': pokemon_info.get('individual_defense', 0),
        'sta': pokemon_info.get('individual_stamina', 0),
        'move_1': pokemon_info['move_1'],
        'move_2': pokemon_info['move_2'],
        'height': pokemon_info['height_m'],
        'weight': pokemon_info['weight_kg'],
        'gender': pokemon_info['pokemon_display']['gender']
    }
    log.info(u"Found level {} {} with CP {} for trainer level {}.".format(level, pokemon_name, cp, trainer_level))

    if 'capture_probability' in encounter_result:
        probs = encounter_result['capture_probability']['capture_probability']
        response['catch_prob_1'] = probs[0]
        response['catch_prob_2'] = probs[1]
        response['catch_prob_3'] = probs[2]
    else:
        log.warning("No capture_probability info found")

    encounter_cache[encounter_id] = response
    return response


def perform_scout(p, db_updates_queue):
    global api, last_scout_timestamp, encounter_cache

    if not args.scout_account_username:
        return { "msg": "No scout account configured." }

    pokemon_name = get_pokemon_name(p.pokemon_id)

    # Check cache once in a non-blocking way
    if p.encounter_id in encounter_cache:
        result = encounter_cache[p.encounter_id]
        log.info(u"Cached scout-result: level {} {} with CP {}.".format(result["level"], pokemon_name, result["cp"]))
        return result

    scoutLock.acquire()
    try:
        # Check cache again after mutually exclusive access
        if p.encounter_id in encounter_cache:
            result = encounter_cache[p.encounter_id]
            log.info(u"Cached scout-result: level {} {} with CP {}.".format(result["level"], pokemon_name, result["cp"]))
            return result

        # Delay scouting
        now = time.time()
        if last_scout_timestamp is not None and now < last_scout_timestamp + args.scout_cooldown_delay:
            wait_secs = last_scout_timestamp + args.scout_cooldown_delay - now
            log.info("Waiting {} more seconds before next scout use.".format(wait_secs))
            time.sleep(wait_secs)

        log.info(u"Scouting a {} at {}, {}".format(pokemon_name, p.latitude, p.longitude))
        step_location = jitter_location([p.latitude, p.longitude, 42])

        if api is None:
            # instantiate pgoapi
            api = PGoApi()

        api.set_position(*step_location)
        account = {
            "auth_service": args.scout_account_auth,
            "username": args.scout_account_username,
            "password": args.scout_account_password
        }
        check_login(args, account, api, None, False)

        if args.hash_key:
            key = key_scheduler.next()
            log.debug('Using key {} for this scout use.'.format(key))
            api.activate_hash_server(key)

        request_result = encounter_request(long(b64decode(p.encounter_id)), p.spawnpoint_id, p.latitude, p.longitude)

        # Update last timestamp
        last_scout_timestamp = time.time()
    finally:
        scoutLock.release()

    result = parse_scout_result(request_result, p.encounter_id, pokemon_name)
    if 'cp' in result:
        update_data = {
            p.encounter_id: {
                'encounter_id': p.encounter_id,
                'spawnpoint_id': p.spawnpoint_id,
                'pokemon_id': p.pokemon_id,
                'latitude': p.latitude,
                'longitude': p.longitude,
                'disappear_time': p.disappear_time,
                'individual_attack': result['atk'],
                'individual_defense': result['def'],
                'individual_stamina': result['sta'],
                'move_1': result['move_1'],
                'move_2': result['move_2'],
                'height': result['height'],
                'weight': result['weight'],
                'gender': result['gender'],
                'cp': result['cp'],
                'level': result['level'],
                'catch_prob_1': result['catch_prob_1'],
                'catch_prob_2': result['catch_prob_2'],
                'catch_prob_3': result['catch_prob_3']
            }
        }
        db_updates_queue.put((Pokemon, update_data))
    return result
