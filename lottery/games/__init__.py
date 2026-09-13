from lottery.games.lotto import GAME_CONFIG as LOTTO
from lottery.games.euromillions import GAME_CONFIG as EUROMILLIONS
from lottery.games.set_for_life import GAME_CONFIG as SET_FOR_LIFE
from lottery.games.thunderball import GAME_CONFIG as THUNDERBALL

REGISTRY: dict = {
    "lotto": LOTTO,
    "euromillions": EUROMILLIONS,
    "set-for-life": SET_FOR_LIFE,
    "thunderball": THUNDERBALL,
}


def get_game(slug: str):
    slug = slug.lower().replace("_", "-")
    if slug not in REGISTRY:
        raise ValueError(f"Unknown game '{slug}'. Available: {', '.join(REGISTRY)}")
    return REGISTRY[slug]
