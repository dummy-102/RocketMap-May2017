#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time
import random
# for geofence
from matplotlib.path import Path
from ast import literal_eval

from threading import Lock
from timeit import default_timer

from pgoapi import PGoApi
from pgoapi.exceptions import AuthException
from pgoapi.protos.pogoprotos.inventory.item.item_id_pb2 import *

from .utils import in_radius
from .fakePogoApi import FakePogoApi
from .utils import in_radius, generate_device_info, equi_rect_distance
from .proxy import get_new_proxy

log = logging.getLogger(__name__)


class TooManyLoginAttempts(Exception):
    pass


# Create the API object that'll be used to scan.
def setup_api(args, status):
    # Create the API instance this will use.
    if args.mock != '':
        api = FakePogoApi(args.mock)
    else:
        device_info = generate_device_info()
        api = PGoApi(device_info=device_info)

    # New account - new proxy.
    if args.proxy:
        # If proxy is not assigned yet or if proxy-rotation is defined
        # - query for new proxy.
        if ((not status['proxy_url']) or
                ((args.proxy_rotation is not None) and
                 (args.proxy_rotation != 'none'))):

            proxy_num, status['proxy_url'] = get_new_proxy(args)
            if args.proxy_display.upper() != 'FULL':
                status['proxy_display'] = proxy_num
            else:
                status['proxy_display'] = status['proxy_url']

    if status['proxy_url']:
        log.debug('Using proxy %s', status['proxy_url'])
        api.set_proxy({
            'http': status['proxy_url'],
            'https': status['proxy_url']})

    return api


# Use API to check the login status, and retry the login if possible.
def check_login(args, account, api, position, proxy_url):
    # Logged in? Enough time left? Cool!
    if api._auth_provider and api._auth_provider._ticket_expire:
        remaining_time = api._auth_provider._ticket_expire / 1000 - time.time()
        if remaining_time > 60:
            log.debug(
                'Credentials remain valid for another %f seconds.',
                remaining_time)
            return

    # Try to login. Repeat a few times, but don't get stuck here.
    num_tries = 0
    # One initial try + login_retries.
    while num_tries < (args.login_retries + 1):
        try:
            if proxy_url:
                api.set_authentication(
                    provider=account['auth_service'],
                    username=account['username'],
                    password=account['password'],
                    proxy_config={'http': proxy_url, 'https': proxy_url})
            else:
                api.set_authentication(
                    provider=account['auth_service'],
                    username=account['username'],
                    password=account['password'])
            break
        except AuthException:
            num_tries += 1
            log.error(
                ('Failed to login to Pokemon Go with account %s. ' +
                 'Trying again in %g seconds.'),
                account['username'], args.login_delay)
            time.sleep(args.login_delay)

    if num_tries > args.login_retries:
        log.error(
            ('Failed to login to Pokemon Go with account %s in ' +
             '%d tries. Giving up.'),
            account['username'], num_tries)
        raise TooManyLoginAttempts('Exceeded login attempts.')

    log.debug('Login for account %s successful.', account['username'])
    time.sleep(20)


# Check if all important tutorial steps have been completed.
# API argument needs to be a logged in API instance.
def get_tutorial_state(api, account):
    log.debug('Checking tutorial state for %s.', account['username'])
    request = api.create_request()
    request.get_player(
        player_locale={'country': 'US',
                       'language': 'en',
                       'timezone': 'America/Denver'})

    response = request.call().get('responses', {})

    get_player = response.get('GET_PLAYER', {})
    tutorial_state = get_player.get(
        'player_data', {}).get('tutorial_state', [])
    time.sleep(random.uniform(2, 4))
    return tutorial_state


# Complete minimal tutorial steps.
# API argument needs to be a logged in API instance.
# TODO: Check if game client bundles these requests, or does them separately.
def complete_tutorial(api, account, tutorial_state):
    if 0 not in tutorial_state:
        time.sleep(random.uniform(1, 5))
        request = api.create_request()
        request.mark_tutorial_complete(tutorials_completed=0)
        log.debug('Sending 0 tutorials_completed for %s.', account['username'])
        request.call()

    if 1 not in tutorial_state:
        time.sleep(random.uniform(5, 12))
        request = api.create_request()
        request.set_avatar(player_avatar={
            'hair': random.randint(1, 5),
            'shirt': random.randint(1, 3),
            'pants': random.randint(1, 2),
            'shoes': random.randint(1, 6),
            'avatar': random.randint(0, 1),
            'eyes': random.randint(1, 4),
            'backpack': random.randint(1, 5)
        })
        log.debug('Sending set random player character request for %s.',
                  account['username'])
        request.call()

        time.sleep(random.uniform(0.3, 0.5))

        request = api.create_request()
        request.mark_tutorial_complete(tutorials_completed=1)
        log.debug('Sending 1 tutorials_completed for %s.', account['username'])
        request.call()

    time.sleep(random.uniform(0.5, 0.6))
    request = api.create_request()
    request.get_player_profile()
    log.debug('Fetching player profile for %s...', account['username'])
    request.call()

    starter_id = None
    if 3 not in tutorial_state:
        time.sleep(random.uniform(1, 1.5))
        request = api.create_request()
        request.get_download_urls(asset_id=[
            '1a3c2816-65fa-4b97-90eb-0b301c064b7a/1477084786906000',
            'aa8f7687-a022-4773-b900-3a8c170e9aea/1477084794890000',
            'e89109b0-9a54-40fe-8431-12f7826c8194/1477084802881000'])
        log.debug('Grabbing some game assets.')
        request.call()

        time.sleep(random.uniform(1, 1.6))
        request = api.create_request()
        request.call()

        time.sleep(random.uniform(6, 13))
        request = api.create_request()
        starter = random.choice((1, 4, 7))
        request.encounter_tutorial_complete(pokemon_id=starter)
        log.debug('Catching the starter for %s.', account['username'])
        request.call()

        time.sleep(random.uniform(0.5, 0.6))
        request = api.create_request()
        request.get_player(
            player_locale={
                'country': 'US',
                'language': 'en',
                'timezone': 'America/Denver'})
        responses = request.call().get('responses', {})

        inventory = responses.get('GET_INVENTORY', {}).get(
            'inventory_delta', {}).get('inventory_items', [])
        for item in inventory:
            pokemon = item.get('inventory_item_data', {}).get('pokemon_data')
            if pokemon:
                starter_id = pokemon.get('id')

    if 4 not in tutorial_state:
        time.sleep(random.uniform(5, 12))
        request = api.create_request()
        request.claim_codename(codename=account['username'])
        log.debug('Claiming codename for %s.', account['username'])
        request.call()

        time.sleep(random.uniform(1, 1.3))
        request = api.create_request()
        request.mark_tutorial_complete(tutorials_completed=4)
        log.debug('Sending 4 tutorials_completed for %s.', account['username'])
        request.call()

        time.sleep(0.1)
        request = api.create_request()
        request.get_player(
            player_locale={
                'country': 'US',
                'language': 'en',
                'timezone': 'America/Denver'})
        request.call()

    if 7 not in tutorial_state:
        time.sleep(random.uniform(4, 10))
        request = api.create_request()
        request.mark_tutorial_complete(tutorials_completed=7)
        log.debug('Sending 7 tutorials_completed for %s.', account['username'])
        request.call()

    if starter_id:
        time.sleep(random.uniform(3, 5))
        request = api.create_request()
        request.set_buddy_pokemon(pokemon_id=starter_id)
        log.debug('Setting buddy pokemon for %s.', account['username'])
        request.call()
        time.sleep(random.uniform(0.8, 1.8))

    # Sleeping before we start scanning to avoid Niantic throttling.
    log.debug('And %s is done. Wait for a second, to avoid throttle.',
              account['username'])
    time.sleep(random.uniform(2, 4))
    return True


def cleanup_inventory(api, inventory):
    # Just need to make room for 1 more item
    if inventory['total'] >= 100:
        items_dropped = drop_items(api, inventory, ITEM_POTION, "Potion", 10)
        items_dropped += drop_items(api, inventory, ITEM_SUPER_POTION, "Super Potion", 10)
        items_dropped += drop_items(api, inventory, ITEM_HYPER_POTION, "Hyper Potion", 10)
        items_dropped += drop_items(api, inventory, ITEM_MAX_POTION, "Max Potion", 10)
        items_dropped += drop_items(api, inventory, ITEM_REVIVE, "Revive", 10)
        items_dropped += drop_items(api, inventory, ITEM_MAX_REVIVE, "Max Revive", 10)
        items_dropped += drop_items(api, inventory, ITEM_BLUK_BERRY, "Bluk Berry", 10)
        items_dropped += drop_items(api, inventory, ITEM_NANAB_BERRY, "Nanab Berry", 10)
        items_dropped += drop_items(api, inventory, ITEM_WEPAR_BERRY, "Wepar Berry", 10)
        items_dropped += drop_items(api, inventory, ITEM_PINAP_BERRY, "Pinap Berry", 10)
        items_dropped += drop_items(api, inventory, ITEM_RAZZ_BERRY, "Razz Berry", 10)

        # Throw away balls if necessary
        if inventory['total'] >= 350:
            need_to_drop = inventory['total'] - 350 + 1
            items_dropped = drop_items(api, inventory, ITEM_POKE_BALL, "Poke Ball", need_to_drop)
            if items_dropped < need_to_drop:
                need_to_drop -= items_dropped
                items_dropped = drop_items(api, inventory, ITEM_GREAT_BALL, "Great Ball", need_to_drop)
            if items_dropped < need_to_drop:
                need_to_drop -= items_dropped
                drop_items(api, inventory, ITEM_ULTRA_BALL, "Great Ball", need_to_drop)

def drop_items(api, inventory, item_id, item_name, drop_count=-1):
    item_count = inventory.get(item_id, 0)
    drop_count = item_count if drop_count == -1 else min(item_count, drop_count)
    if drop_count > 0:
        result = drop_items_request(api, item_id, drop_count, inventory)
        if result == 1:
            log.warning("------------------------------- Dropped {} {}s.".format(drop_count, item_name))
            inventory[item_id] -= drop_count
            inventory['total'] -= drop_count
            return drop_count
        else:
            log.warning("Failed dropping {} {}s.".format(drop_count, item_name))
    return 0


def drop_items_request(api, item_id, amount, inventory):
    time.sleep(random.uniform(2, 4))
    try:
        req = api.create_request()
        req.recycle_inventory_item(item_id=item_id,
                                   count=amount)
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        response_dict = req.call()
        inventory.update(get_player_inventory(response_dict))
        if ('responses' in response_dict) and ('RECYCLE_INVENTORY_ITEM' in response_dict['responses']):
            drop_details = response_dict['responses']['RECYCLE_INVENTORY_ITEM']
            return drop_details.get('result', -1)
    except Exception as e:
        log.warning('Exception while dropping items: %s', repr(e))
        return False


def get_player_level(map_dict):
    inventory_items = map_dict['responses'].get(
        'GET_INVENTORY', {}).get(
        'inventory_delta', {}).get(
        'inventory_items', [])
    player_stats = [item['inventory_item_data']['player_stats']
                    for item in inventory_items
                    if 'player_stats' in item.get(
                    'inventory_item_data', {})]
    if len(player_stats) > 0:
        player_level = player_stats[0].get('level', 1)
        return player_level

    return 0


def get_player_inventory(map_dict):
    inventory_items = map_dict['responses'].get(
        'GET_INVENTORY', {}).get(
        'inventory_delta', {}).get(
        'inventory_items', [])
    inventory = {}
    no_item_ids = (
        ITEM_UNKNOWN,
        #ITEM_TROY_DISK,
        ITEM_X_ATTACK,
        ITEM_X_DEFENSE,
        ITEM_X_MIRACLE,
        ITEM_POKEMON_STORAGE_UPGRADE,
        ITEM_ITEM_STORAGE_UPGRADE
    )
    total_items = 0
    for item in inventory_items:
        iid = item.get('inventory_item_data', {})
        if 'item' in iid and iid['item']['item_id'] not in no_item_ids:
            item_id = iid['item']['item_id']
            count = iid['item'].get('count', 0)
            inventory[item_id] = count
            total_items += count
        elif 'egg_incubators' in iid and 'egg_incubator' in iid['egg_incubators']:
            for incubator in iid['egg_incubators']['egg_incubator']:
                item_id = incubator['item_id']
                inventory[item_id] = inventory.get(item_id, 0) + 1
                total_items += 1
    inventory['balls'] = inventory.get(ITEM_POKE_BALL, 0) + inventory.get(ITEM_GREAT_BALL, 0) + inventory.get(
        ITEM_ULTRA_BALL, 0) + inventory.get(ITEM_MASTER_BALL, 0)
    inventory['totalDisks'] = inventory.get(ITEM_TROY_DISK, 0)
    inventory['total'] = total_items
    return inventory


def spin_pokestop(api, fort, step_location, inventory):
    time.sleep(random.uniform(2, 5))  # Do not let Niantic throttle
    spin_response = spin_pokestop_request(api, fort, step_location, inventory)
    if not spin_response:
        return False

    # Check for reCaptcha
    captcha_url = spin_response['responses']['CHECK_CHALLENGE']['challenge_url']
    if len(captcha_url) > 1:
        log.debug('Account encountered a reCaptcha.')
        return False

    spin_result = spin_response['responses']['FORT_SEARCH']['result']
    if spin_result is 1:
        awards = get_awarded_items(spin_response['responses']['FORT_SEARCH']['items_awarded'])
        log.warning('++++++++++++++++++++++++++++ Got {} items ({} balls) from Pokestop.'.format(awards['total'], awards['balls']))
        inventory.update(get_player_inventory(spin_response))
        return True
    elif spin_result is 2:
        log.debug('Pokestop was not in range to spin.')
    elif spin_result is 3:
        log.debug('Failed to spin Pokestop. Has recently been spun.')
    elif spin_result is 4:
        log.debug('Failed to spin Pokestop. Inventory is full.')
    elif spin_result is 5:
        log.debug('Maximum number of Pokestops spun for this day.')
    else:
        log.debug(
            'Failed to spin a Pokestop. Unknown result %d.',
            spin_result)
    return False


def get_awarded_items(items_awarded):
    awards = {}
    total = 0
    balls = 0
    for item in items_awarded:
        item_id = item['item_id']
        count = item['item_count']
        total += count
        if item_id in (ITEM_POKE_BALL, ITEM_GREAT_BALL, ITEM_ULTRA_BALL, ITEM_MASTER_BALL):
            balls += count
        awards[item_id] = awards.get(item_id, 0) + count
    awards['total'] = total
    awards['balls'] = balls
    return awards


def pokestop_spinnable(fort, step_location):
    spinning_radius = 0.04
    in_range = in_radius((fort['latitude'], fort['longitude']), step_location,
                         spinning_radius)
    now = time.time()
    needs_cooldown = "cooldown_complete_timestamp_ms" in fort and fort["cooldown_complete_timestamp_ms"] / 1000 > now
    return in_range and not needs_cooldown


def spin_pokestop_request(api, fort, step_location, inventory):
    try:
        log.warning('++++++++++++++++++++++++++++ SPINNING POKESTOP')
        req = api.create_request()
        req.fort_search(
            fort_id=fort['id'],
            fort_latitude=fort['latitude'],
            fort_longitude=fort['longitude'],
            player_latitude=step_location[0],
            player_longitude=step_location[1])
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        response_dict = req.call()
        inventory.update(get_player_inventory(response_dict))
        return response_dict
        spin_pokestop_response = req.call()

        return spin_pokestop_response

    except Exception as e:
        log.error('Exception while spinning Pokestop: %s.', repr(e))
        return False

def encounter_pokemon_request(api, encounter_id, spawnpoint_id, scan_location):
    try:
        # Setup encounter request envelope.
        req = api.create_request()
        req.encounter(
            encounter_id=encounter_id,
            spawn_point_id=spawnpoint_id,
            player_latitude=scan_location[0],
            player_longitude=scan_location[1])
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        encounter_result = req.call()

        return encounter_result
    except Exception as e:
        log.error('Exception while encountering Pokémon: %s.', repr(e))
        return False

def geofence(step_location, geofence_file, forbidden=False):
    geofence = []
    with open(geofence_file) as f:
        for line in f:
            if len(line.strip()) == 0 or line.startswith('#'):
                continue
            geofence.append(literal_eval(line.strip()))
        if forbidden:
             log.warning('Loaded %d geofence-forbidden coordinates. ' +
                      'Applying...', len(geofence))
        else:
             log.warning('Loaded %d geofence coordinates. Applying...',
                    len(geofence))
    #log.info(geofence)
    p = Path(geofence)
    step_location_geofenced = []
    result_x, result_y, result_z = step_location
    if p.contains_point([step_location[0], step_location[1]]) ^ forbidden:
        step_location_geofenced.append((result_x, result_y, result_z))
        log.warning('FOUND IN THE GEOFENCE, LURING: %s, %s', result_x, result_y)
    return step_location_geofenced

def lure_pokestop(args, api, fort, step_location, inventory):
    if 'active_fort_modifier' not in fort:
        spinning_radius = 0.03
        totalDisks = inventory['totalDisks']
        log.warning('++++++++++++++++++++++++++++ DETECTING %s LURES', totalDisks)
        in_range = in_radius((fort['latitude'], fort['longitude']), step_location,
                                 spinning_radius)
        if in_range:
            if args.lureFence is not None:
                allowed = geofence(step_location, args.lureFence)
                log.warning('FENCE: %s', allowed)
                if allowed == []:
                    log.warning('STOP IS FORBIDDEN')
                    forbidden = True
                else:
                    log.warning('STOP IS GOOD')
                    forbidden = False
            if args.nolureFence is not None:
                forbidden = geofence(step_location, args.nolureFence, forbidden=True)
                log.warning('DI-ALLOWFENCE: %s', forbidden)
                if forbidden == []:
                    log.warning('STOP IS GOOD')
                    forbidden = False
                else:
                    forbidden = True
                    log.warning('STOP IS FORBIDDEN')
            lure_status = None
            lure_id = 501
            if totalDisks == 0:
                forbidden = True
            while lure_status is None and totalDisks > 0:
                req = api.create_request()
                lure_request = req.add_fort_modifier(modifier_type=lure_id,
                                                     fort_id=fort['id'],
                                                     player_latitude=step_location[0],
                                                     player_longitude=step_location[1])
                time.sleep(4.20)
                lure_request = req.call()
                #log.warning('@@@LURE RESPONSE@@@ %s', lure_request['responses'])
                lure_status = lure_request['responses']['ADD_FORT_MODIFIER']['result']
                if lure_status is 0:
                    log.warning('xxxxxxxxxxxxxxxxxxxxxxxxxxxx Lure unset!')
                    lure_status = 'Failed'
                elif lure_status is 1:
                    log.warning('++++++++++++++++++++++++++++ Lure Successfully Set!')
                    lure_status = 'Successful'
                elif lure_status is 2:
                    log.warning('xxxxxxxxxxxxxxxxxxxxxxxxxxxx Stop already has lure!')
                    lure_status = 'Panic'
                elif lure_status is 3:
                    log.warning('xxxxxxxxxxxxxxxxxxxxxxxxxxxx Out of range to set lure!')
                    lure_status = 'Range'
                elif lure_status is 4:
                    log.warning('---------------------------- Account has no lures!')
                    lure_status = 'Empty'

                log.warning('@@@ LURE STATUS @@@ %s', lure_status)

# Send LevelUpRewards request to check for and accept level up rewards.
# @Returns
# 0: UNSET
# 1: SUCCESS
# 2: AWARDED_ALREADY
def level_up_rewards_request(api, level, username, inventory):
    log.warning('Attempting to check level up rewards for level {} of account {}.'.format(level, username))
    time.sleep(random.uniform(2, 3))
    try:
        req = api.create_request()
        req.level_up_rewards(level=level)
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        rewards_response = req.call()
        inventory.update(get_player_inventory(rewards_response))
        if ('responses' in rewards_response) and ('LEVEL_UP_REWARDS' in rewards_response['responses']):
            reward_details = rewards_response['responses']['LEVEL_UP_REWARDS']
            return reward_details.get('result', -1)

    except Exception as e:
        log.warning('Exception while requesting level up rewards: %s', repr(e))

    return False

# The AccountSet returns a scheduler that cycles through different
# sets of accounts (e.g. L30). Each set is defined at runtime, and is
# (currently) used to separate regular accounts from L30 accounts.
# TODO: Migrate the old account Queue to a real AccountScheduler, preferably
# handled globally via database instead of per instance.
# TODO: Accounts in the AccountSet are exempt from things like the
# account recycler thread. We could've hardcoded support into it, but that
# would have added to the amount of ugly code. Instead, we keep it as is
# until we have a proper account manager.
class AccountSet(object):

    def __init__(self, kph):
        self.sets = {}

        # Scanning limits.
        self.kph = kph

        # Thread safety.
        self.next_lock = Lock()

    # Set manipulation.
    def create_set(self, name, values=[]):
        if name in self.sets:
            raise Exception('Account set ' + name + ' is being created twice.')

        self.sets[name] = values

    # Release an account back to the pool after it was used.
    def release(self, account):
        if 'in_use' not in account:
            log.error('Released account %s back to the AccountSet,'
                      + " but it wasn't locked.",
                      account['username'])
        else:
            account['in_use'] = False

    # Get next account that is ready to be used for scanning.
    def next(self, set_name, coords_to_scan):
        # Yay for thread safety.
        with self.next_lock:
            # Readability.
            account_set = self.sets[set_name]

            # Loop all accounts for a good one.
            now = default_timer()
            max_speed_kmph = self.kph

            for i in range(len(account_set)):
                account = account_set[i]

                # Make sure it's not in use.
                if account.get('in_use', False):
                    continue

                # Make sure it's not captcha'd.
                if account.get('captcha', False):
                    continue

                # Check if we're below speed limit for account.
                last_scanned = account.get('last_scanned', False)

                if last_scanned:
                    seconds_passed = now - last_scanned
                    old_coords = account.get('last_coords', coords_to_scan)

                    distance_km = equi_rect_distance(
                        old_coords,
                        coords_to_scan)
                    cooldown_time_sec = distance_km / max_speed_kmph * 3600

                    # Not enough time has passed for this one.
                    if seconds_passed < cooldown_time_sec:
                        continue

                # We've found an account that's ready.
                account['last_scanned'] = now
                account['last_coords'] = coords_to_scan
                account['in_use'] = True

                return account

        # TODO: Instead of returning False, return the amount of min. seconds
        # the instance needs to wait until the first account becomes available,
        # so it doesn't need to keep asking if we know we need to wait.
        return False
