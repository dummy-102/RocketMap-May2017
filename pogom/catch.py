#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import time
import random

from pgoapi.protos.pogoprotos.inventory.item.item_id_pb2 import *

from pogom.account import get_player_inventory
from pogom.utils import get_pokemon_name

log = logging.getLogger(__name__)


def catch(api, encounter_id, spawn_point_id, pid, inventory):
    # Try to catch pokemon, but don't get stuck.
    pkm_name = get_pokemon_name(pid)
    attempts = 1
    while attempts < 3:
        log.info('Starting attempt %s to catch a %s!', attempts, pkm_name)
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
            inventory.update(get_player_inventory(catch_result))

            if (catch_result is not None and 'CATCH_POKEMON' in catch_result['responses']):
                catch_status = catch_result['responses']['CATCH_POKEMON']['status']

                # Success!
                if catch_status == 1:
                    cpid = catch_result['responses']['CATCH_POKEMON']['captured_pokemon_id']
                    log.warning('Catch attempt %s was successful for %s!', attempts, pkm_name)

                    rv = {'catch_status': 'success'}
                    # Check inventory for new pokemon id and movesets
                    iitems = catch_result['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']
                    for item in iitems:
                        iidata = item['inventory_item_data']
                        if 'pokemon_data' in iidata and iidata['pokemon_data']['id'] == cpid:
                            rv.update({
                                'pid': iidata['pokemon_data']['pokemon_id'],
                                'move_1': iidata['pokemon_data']['move_1'],
                                'move_2': iidata['pokemon_data']['move_2'],
                                'height': iidata['pokemon_data']['height_m'],
                                'weight': iidata['pokemon_data']['weight_kg'],
                                'gender': iidata['pokemon_data']['pokemon_display']['gender'],
                                #'cp': '?'
                            })
                            time.sleep(random.uniform(7, 10))
                            release(api, pkm_name, cpid)
                    if not 'pid' in rv:
                        log.error('Could not find caught Pokemon in inventory. Cannot release. Too bad!')
                    return rv

                # Broke free!
                if catch_status == 2:
                    log.info('Catch attempt %s failed for %s. It broke free!', attempts, pkm_name)

                # Ran away!
                if catch_status == 3:
                    log.info('Catch attempt %s failed for %s. It ran away!', attempts, pkm_name)
                    return {'catch_status': 'ran'}

                # Dodged!
                if catch_status == 4:
                    log.info('Catch attempt %s failed for %s. It dodged the ball!', attempts, pkm_name)

            else:
                log.error('Catch attempt %s failed for %s. The api response was empty!', attempts, pkm_name)

        except Exception as e:
            log.error('Catch attempt %s failed for pid: %s. The api response returned an error! ' +
                      'Exception: %s', attempts, pid, repr(e))

        attempts += 1

    if attempts >= 3:
        log.error('Failed to catch pid: %s after %s attempts. Giving up.', pid, (attempts - 1))
        rv = {'catch_status': 'fail'}

    return rv


def release(api, pkm_name, cpid):
    try:
        #log.info('Attempting to release %s', pkm_name)
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
                log.warning('Successfully released %s', pkm_name)
            else:
                log.info('Failed to release %s with result code: %s.', pkm_name, release_result)

    except Exception as e:
        log.error('Exception while releasing %s. Error: %s', pkm_name, repr(e))
        return False

    return True
