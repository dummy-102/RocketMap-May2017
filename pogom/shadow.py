# Shadowbanned accounts cannot see these Pokemon
SHADOWED_POKEMON = [
    7,      # Squirtle
    13,     # Weedle
    20,     # Raticate
    21,     # Spearow
    22,     # Fearow
    48,     # Venonat
    70,     # Weepinbell
    75,     # Graveler
    79,     # Slowpoke
    90,     # Shellder
    95,     # Onix
    111,    # Rhyhorn
    116,    # Horsea
    138,    # Omanyte
    140,    # Kabuto
    162,    # Furret
    163,    # Hoothoot
    166,    # Ledian
    168,    # Ariados
    170,    # Chinchou
    184,    # Azumarill
    185,    # Sudowoodo
    213,    # Shuckle
    216,    # Teddiursa
    219,    # Magcargo
    223,    # Remoraid
    224,    # Octillery
    226     # Mantine
]

def sees_shadowed_pokemon(api_response):
    cells = api_response.get('responses', {}).get('GET_MAP_OBJECTS', {}).get(
        'map_cells', [])
    for cell in cells:
        for p in cell.get('wild_pokemons', []):
            pid = p['pokemon_data']['pokemon_id']
            if pid in SHADOWED_POKEMON:
                return True
        for p in cell.get('nearby_pokemons', []):
            pid = p['pokemon_id']
            if pid in SHADOWED_POKEMON:
                return True
    return False
