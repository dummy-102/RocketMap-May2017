#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time
import random

from pgoapi.protos.pogoprotos.inventory.item.item_id_pb2 import *

from pogom.account import get_player_inventory, log, spin_pokestop_request, \
    encounter_pokemon_request
from pogom.utils import get_pokemon_name, in_radius

log = logging.getLogger(__name__)


DROP_BALLS = 50

DITTO_POKEDEX_ID = 132

ITEM_NAMES = {
    ITEM_POKE_BALL: u"Poké Ball",
    ITEM_GREAT_BALL: u"Great Ball",
    ITEM_ULTRA_BALL: u"Ultra Ball",
    ITEM_POTION: u"Potion",
    ITEM_SUPER_POTION: u"Super Potion",
    ITEM_HYPER_POTION: u"Hyper Potion",
    ITEM_MAX_POTION: u"Max Potion",
    ITEM_REVIVE: u"Revive",
    ITEM_MAX_REVIVE: u"Max Revive",
    ITEM_BLUK_BERRY: u"Bluk Berry",
    ITEM_NANAB_BERRY: u"Nanab Berry",
    ITEM_WEPAR_BERRY: u"Wepar Berry",
    ITEM_PINAP_BERRY: u"Pinap Berry",
    ITEM_RAZZ_BERRY: u"Razz Berry"
}


def is_ditto(args, api, p, inventory):
    pokemon_id = p['pokemon_data']['pokemon_id']
    pokemon_name = get_pokemon_name(pokemon_id)
    captured_pokemon_name = pokemon_name
    log.info(u'{} may be a Ditto. Triggering catch logic!'.format(pokemon_name))

    # Encounter Pokemon.
    time.sleep(args.encounter_delay)
    encounter_pokemon_request(api, p['encounter_id'], p['spawn_point_id'],
                              [p['latitude'], p['longitude']])

    # Now try to catch it.
    got_ditto = False
    catch_result = catch(api, p['encounter_id'], p['spawn_point_id'], inventory)
    if catch_result['catch_status'] == 'success':
        if int(catch_result['pid']) == DITTO_POKEDEX_ID:
            logmsg = u'Successfully caught a Ditto disguised as {}! Needed {} attempts.'
            captured_pokemon_name = get_pokemon_name(DITTO_POKEDEX_ID)
            got_ditto = True
        else:
            logmsg = u'Successfully caught a regular {} after {} attempts.'
        log.info(logmsg.format(pokemon_name, catch_result['attempts']))
        # Release the Pokemon in any case
        time.sleep(random.uniform(7, 10))
        if release(api, catch_result['capture_id']):
            log.info(u'Successfully released {}.'.format(captured_pokemon_name))
    else:
        log.info("Failed catching {}: {} Attempts: {}".format(pokemon_name, catch_result['reason'], catch_result['attempts']))
    return got_ditto

def catch(api, encounter_id, spawn_point_id, inventory):
    # Try to catch pokemon, but don't get stuck.
    rv = {
        'catch_status': 'fail',
        'reason': "Unknown reason.",
        'attempts': 1
    }
    while rv['attempts'] < 3:
        time.sleep(random.uniform(2, 3))
        try:
            # Randomize throwing parameters
            random_throw = 1.5 + 0.40 * random.random()
            random_spin = 0.8 + 0.2 * random.random()

            # Determine best ball - we know for sure that we have at least one
            ball = ITEM_ULTRA_BALL if inventory.get(ITEM_ULTRA_BALL, 0) > 0 else (
                ITEM_GREAT_BALL if inventory.get(ITEM_GREAT_BALL, 0) > 0 else ITEM_POKE_BALL)

            req = api.create_request()
            req.catch_pokemon(
                encounter_id=encounter_id,
                pokeball=ball,
                normalized_reticle_size=random_throw,
                spawn_point_id=spawn_point_id,
                hit_pokemon=1,
                spin_modifier=random_spin,
                normalized_hit_position=1.0)
            req.check_challenge()
            req.get_hatched_eggs()
            req.get_inventory()
            req.check_awarded_badges()
            req.download_settings()
            req.get_buddy_walked()
            catch_result = req.call()

            # Inventory changed on throwing a ball.
            inventory.update(get_player_inventory(catch_result))

            if (catch_result is not None and 'CATCH_POKEMON' in catch_result['responses']):
                catch_status = catch_result['responses']['CATCH_POKEMON']['status']

                # Success!
                if catch_status == 1:
                    # Check inventory for caught Pokemon
                    capture_id = catch_result['responses']['CATCH_POKEMON']['captured_pokemon_id']
                    pid = get_captured_pokemon_id_from_inventory(capture_id, catch_result)
                    if pid:
                        # Set ID of caught Pokemon
                        rv['catch_status'] = 'success'
                        rv['pid'] = pid
                        rv['capture_id'] = capture_id
                    else:
                        rv['reason'] = "Could not find caught Pokemon in inventory."
                    return rv

                # Broke free!
                if catch_status == 2:
                    log.debug('Catch attempt %s failed. It broke free!', rv['attempts'])

                # Ran away!
                if catch_status == 3:
                    rv['reason'] = "Pokemon ran away!"
                    return rv

                # Dodged!
                if catch_status == 4:
                    log.debug('Catch attempt %s failed. It dodged the ball!', rv['attempts'])

            else:
                log.error('Catch attempt %s failed. The api response was empty!', rv['attempts'])

        except Exception as e:
            log.error('Catch attempt %s failed. API exception: %s', rv['attempts'], repr(e))

        rv['attempts'] += 1

    if rv['attempts'] >= 3:
        rv['attempts'] -= 1
        rv['reason'] = "Giving up."

    return rv


def get_captured_pokemon_id_from_inventory(capture_id, response):
    iitems = response['responses']['GET_INVENTORY']['inventory_delta'][
        'inventory_items']
    for item in iitems:
        iidata = item['inventory_item_data']
        if 'pokemon_data' in iidata and iidata['pokemon_data']['id'] == capture_id:
            return iidata['pokemon_data']['pokemon_id']
    return None


def release(api, cpid):
    try:
        req = api.create_request()
        req.release_pokemon(pokemon_id=cpid)
        req.check_challenge()
        req.get_hatched_eggs()
        req.get_inventory()
        req.check_awarded_badges()
        req.download_settings()
        req.get_buddy_walked()
        release_result = req.call()

        if (release_result is not None and 'RELEASE_POKEMON' in release_result['responses']):
            release_result = release_result['responses']['RELEASE_POKEMON']['result']
            if int(release_result) == 1:
                return True
            else:
                log.error('Failed to release Pokemon with result code: %s.', release_result)

    except Exception as e:
        log.error('Exception while releasing Pokemon. Error: %s', repr(e))

    return False


def pokestop_spinnable(fort, step_location):
    spinning_radius = 0.03
    in_range = in_radius((fort['latitude'], fort['longitude']), step_location,
                         spinning_radius)
    now = time.time()
    needs_cooldown = "cooldown_complete_timestamp_ms" in fort and fort["cooldown_complete_timestamp_ms"] / 1000 > now
    return in_range and not needs_cooldown


def spin_pokestop_update_inventory(api, fort, step_location, inventory):
    time.sleep(random.uniform(0.8, 1.8))  # Do not let Niantic throttle
    log.warning('++++++++++++++++++++++++++++ GAINXP SPINNING POKESTOP')
    spin_response = spin_pokestop_request(api, fort, step_location)

    time.sleep(random.uniform(2, 4))  # Do not let Niantic throttle
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
        log.warning('Got {} items ({} balls) from Pokestop.'.format(awards['total'], awards['balls']))
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


def cleanup_inventory(api, inventory):
    drop_stats = {}
    # Just need to make room for more items
    if inventory['total'] >= 100:
        drop_items(api, inventory, ITEM_POTION, drop_stats, 10)
        drop_items(api, inventory, ITEM_SUPER_POTION, drop_stats, 10)
        drop_items(api, inventory, ITEM_HYPER_POTION, drop_stats, 10)
        drop_items(api, inventory, ITEM_MAX_POTION, drop_stats, 10)
        drop_items(api, inventory, ITEM_REVIVE, drop_stats, 10)
        drop_items(api, inventory, ITEM_MAX_REVIVE, drop_stats, 10)
        drop_items(api, inventory, ITEM_BLUK_BERRY, drop_stats, 10)
        drop_items(api, inventory, ITEM_NANAB_BERRY, drop_stats, 10)
        drop_items(api, inventory, ITEM_WEPAR_BERRY, drop_stats, 10)
        drop_items(api, inventory, ITEM_PINAP_BERRY, drop_stats, 10)
        drop_items(api, inventory, ITEM_RAZZ_BERRY, drop_stats, 10)

        # Throw away balls if necessary
        if inventory['total'] >= 350:
            need_to_drop = inventory['total'] - 350 + DROP_BALLS
            items_dropped = drop_items(api, inventory, ITEM_POKE_BALL, drop_stats, need_to_drop)
            if items_dropped < need_to_drop:
                need_to_drop -= items_dropped
                items_dropped = drop_items(api, inventory, ITEM_GREAT_BALL, drop_stats, need_to_drop)
                if items_dropped < need_to_drop:
                    need_to_drop -= items_dropped
                    drop_items(api, inventory, ITEM_ULTRA_BALL, drop_stats, need_to_drop)

        # Log what was dropped
        drops = []
        for item_id in sorted(drop_stats):
            dropped = drop_stats[item_id]
            drops.append(u"{} {}s".format(dropped, ITEM_NAMES[item_id]))
        log.info(u"------------------------------- Items dropped: {}".format(u", ".join(drops)))


def drop_items(api, inventory, item_id, drop_stats, drop_count=-1):
    item_count = inventory.get(item_id, 0)
    drop_count = item_count if drop_count == -1 else min(item_count, drop_count)
    if drop_count > 0:
        result = drop_items_request(api, item_id, drop_count, inventory)
        if result == 1:
            drop_stats[item_id] = drop_count
            return drop_count
        else:
            log.warning(u"Failed dropping {} {}s.".format(drop_count, ITEM_NAMES[item_id]))
    return 0


def drop_items_request(api, item_id, amount, inventory):
    time.sleep(random.uniform(2, 4))
    inventory_timestamp = None
    try:
        req = api.create_request()
        req.recycle_inventory_item(item_id=item_id,
                                   count=amount)
        req.check_challenge()
        req.get_hatched_eggs()
        if inventory_timestamp:
            req.get_inventory(last_timestamp_ms=inventory_timestamp)
        else:
            req.get_inventory()
        req.check_awarded_badges()
        req.get_buddy_walked()
        response_dict = req.call()

        # Update inventory timestamp
        inventory_timestamp = response_dict['responses']['GET_INVENTORY'][
                    'inventory_delta']['new_timestamp_ms']

        inventory.update(get_player_inventory(response_dict))
        if ('responses' in response_dict) and ('RECYCLE_INVENTORY_ITEM' in response_dict['responses']):
            drop_details = response_dict['responses']['RECYCLE_INVENTORY_ITEM']
            return drop_details.get('result', -1)
    except Exception as e:
        log.warning('Exception while dropping items: %s', repr(e))
        return False


def lure_pokestop(args, api, fort, step_location, inventory):
    if 'active_fort_modifier' not in fort:
        inventory_timestamp = None
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
                req.check_challenge()
                req.get_hatched_eggs()
                if inventory_timestamp:
                    req.get_inventory(last_timestamp_ms=inventory_timestamp)
                else:
                    req.get_inventory()
                req.check_awarded_badges()
                req.get_buddy_walked()
                time.sleep(4.20)
                lure_request = req.call()

                # Update inventory timestamp
                inventory_timestamp = lure_request['responses']['GET_INVENTORY'][
                            'inventory_delta']['new_timestamp_ms']

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
    time.sleep(random.uniform(2, 3))
    inventory_timestamp = None
    try:
        req = api.create_request()
        req.level_up_rewards(level=level)
        req.check_challenge()
        req.get_hatched_eggs()
        if inventory_timestamp:
            req.get_inventory(last_timestamp_ms=inventory_timestamp)
        else:
            req.get_inventory()
        req.check_awarded_badges()
        req.get_buddy_walked()
        rewards_response = req.call()

        # Update inventory timestamp
        inventory_timestamp = rewards_response['responses']['GET_INVENTORY'][
                    'inventory_delta']['new_timestamp_ms']

        if ('responses' in rewards_response) and ('LEVEL_UP_REWARDS' in rewards_response['responses']):
            inventory.update(get_player_inventory(rewards_response))
            reward_details = rewards_response['responses']['LEVEL_UP_REWARDS']
            return reward_details.get('result', -1)

    except Exception as e:
        log.error('Exception while requesting level up rewards: %s', repr(e))

    return False
