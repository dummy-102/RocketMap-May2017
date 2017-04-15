#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time
import random

from pgoapi.exceptions import AuthException

from .utils import in_radius

log = logging.getLogger(__name__)


class TooManyLoginAttempts(Exception):
    pass


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


# Perform a Pokestop spin.
# API argument needs to be a logged in API instance.
# Called during fort parsing in models.py
def pokestop_spin(api, inventory, forts, step_location, account):
    for fort in forts:
        if fort.get('type') == 1:
            if pokestop_spinnable(fort, step_location) and spin_pokestop(api, fort, step_location):
                log.debug(
                    'Account %s successfully spun a Pokestop.',
                    account['username'])
                log.debug("Dropping some items for account {}".format(account["username"]))
                drop_items(api, inventory, 1, 30, 0.40, "Poke Ball")
                drop_items(api, inventory, 2, 30, 0.40, "Great Ball")
                drop_items(api, inventory, 101, 30, 0.40, "Potion")
                drop_items(api, inventory, 102, 30, 0.40, "Super Potion")
                drop_items(api, inventory, 201, 30, 0.40, "Revive")
                drop_items(api, inventory, 701, 30, 0.40, "Razz Berry")
                return True

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
    for item in inventory_items:
        if 'item' in item.get('inventory_item_data', {}) and item['inventory_item_data']['item']['item_id'] in (1, 2, 101, 102, 201, 701):
            item_id = item['inventory_item_data']['item']['item_id']
            count = item['inventory_item_data']['item']['count']
            inventory[item_id] = count
    return inventory


def spin_pokestop(api, fort, step_location):
    log.debug('Attempt to spin Pokestop.')

    time.sleep(random.uniform(0.8, 1.8))  # Do not let Niantic throttle
    spin_response = spin_pokestop_request(api, fort, step_location)
    time.sleep(random.uniform(2, 4))  # Do not let Niantic throttle

    # Check for reCaptcha
    captcha_url = spin_response['responses'][
        'CHECK_CHALLENGE']['challenge_url']
    if len(captcha_url) > 1:
        log.debug('Account encountered a reCaptcha.')
        return False

    spin_result = spin_response['responses']['FORT_SEARCH']['result']
    if spin_result is 1:
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


def pokestop_spinnable(fort, step_location):
    spinning_radius = 0.04
    in_range = in_radius((fort['latitude'], fort['longitude']), step_location,
                 spinning_radius)
    now = time.time()
    needs_cooldown = "cooldown_complete_timestamp_ms" in fort and fort["cooldown_complete_timestamp_ms"] / 1000 > now
    return in_range and not needs_cooldown


def spin_pokestop_request(api, fort, step_location):
    try:
        req = api.create_request()
        spin_pokestop_response = req.fort_search(
            fort_id=fort['id'],
            fort_latitude=fort['latitude'],
            fort_longitude=fort['longitude'],
            player_latitude=step_location[0],
            player_longitude=step_location[1])
        spin_pokestop_response = req.check_challenge()
        spin_pokestop_response = req.get_hatched_eggs()
        spin_pokestop_response = req.get_inventory()
        spin_pokestop_response = req.check_awarded_badges()
        spin_pokestop_response = req.download_settings()
        spin_pokestop_response = req.get_buddy_walked()
        spin_pokestop_response = req.call()

        return spin_pokestop_response

    except Exception as e:
        log.warning('Exception while spinning Pokestop: %s', repr(e))
        return False


def drop_items(api, inventory, item_id, min_count, drop_fraction, item_name):
    item_count = inventory[item_id]
    drop_count = int(item_count * drop_fraction)
    if item_count > min_count and drop_count > 0:
        result = drop_items_request(api, item_id, drop_count)
        if result == 1:
            log.debug("Dropped {} {}s.".format(drop_count, item_name))
        else:
            log.warning("Failed dropping {} {}s.".format(drop_count, item_name))
    else:
        log.debug("Got only {} {}s. No need to drop some.".format(item_count, item_name))


def drop_items_request(api, item_id, amount):
    time.sleep(5)
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

        if ('responses' in response_dict) and ('RECYCLE_INVENTORY_ITEM' in response_dict['responses']):
            drop_details = response_dict['responses']['RECYCLE_INVENTORY_ITEM']
            return drop_details.get('result', -1)
    except Exception as e:
        log.warning('Exception while dropping items: %s', repr(e))
        return False
