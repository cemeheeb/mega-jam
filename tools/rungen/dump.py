"""Дамп раскладки забега в JSON и эталонные файлы для проверки порта.

python3 dump.py --seed 42            раскладка одного зерна в stdout
python3 dump.py --golden             переписать golden/*.json (после смены правил или чисел)

Порт в Unreal считается верным, если для тех же зёрен и того же Config он выдаёт
те же значения, что в golden/*.json.
"""

import argparse
import json
import os
from dataclasses import asdict

import content as C
import generator as G
from config import DEFAULT
from rng import Rng, hash32, mix32

GOLDEN_SEEDS = (1, 2, 3, 42, 1337, 20261113, 4294967295)
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def item_name(i: int) -> str:
    return C.NOTEBOOK_NAME if i == G.NOTEBOOK else C.CATALOG[i].name


def room_json(rc: G.RoomContent) -> dict:
    return {
        "key": rc.key,
        "copy": rc.copy,
        "type": G.ROOM_TYPE_NAMES[rc.room_type],
        "switches": rc.switches,
        "anomaly": G.ANOMALY_NAMES[rc.anomaly],
        "doors": rc.doors,
        "items": [item_name(i) for i in rc.items],
        "notes": [{"kind": C.NOTE_KIND_NAMES[n.kind], "items": [item_name(i) for i in n.items],
                   "tpl": n.tpl, "text": n.text()} for n in rc.notes],
    }


def key_name(layout: G.RunLayout, key: int) -> str:
    if key == 0:
        return "{} (empty pocket)"
    if key == G.ANCHOR:
        return "{} (notebook only)"
    return "{" + ", ".join(G.ROLE_NAMES[r] for r in range(G.NUM_SIG) if key & (1 << r)) + "}"


def dump(seed: int, cfg=DEFAULT, copies: int = 4) -> dict:
    layout = G.RunLayout(seed, cfg)
    looks = []
    for key in G.all_keys():
        t, sw = layout.look(key)
        looks.append({"key": key, "signature": key_name(layout, key), "class": G.CLS_NAMES[G.room_class(key)],
                      "level": G.chain_level(key), "type": G.ROOM_TYPE_NAMES[t], "switches": sw,
                      "anomaly_chance": layout.anomaly_chance(key), "guarantee_copy": layout.guarantee_copy(key)})
    chain_keys = [k for k in G.all_keys() if G.room_class(k) in (G.CLS_CHAIN, G.CLS_ENGINE)]
    guess_keys = [G.RM_X, G.RM_L | G.RM_Y, G.RM_L | G.RM_K2, G.RM_K1 | G.RM_K2 | G.RM_K3 | G.RM_L]
    rooms = {}
    for k in chain_keys:
        rooms[key_name(layout, k)] = [room_json(layout.room_copy(k, c)) for c in range(1, copies + 1)]
    for k in guess_keys + [0]:
        rooms[key_name(layout, k)] = [room_json(layout.room_copy(k, c)) for c in range(1, 3)]
    return {
        "config": asdict(cfg),
        "layout": layout.describe(),
        "run_items": [C.CATALOG[i].name for i in layout.run_items],
        "level_types": [G.ROOM_TYPE_NAMES[t] for t in layout.level_type],
        "switch_of": {G.ROOM_TYPE_NAMES[t]: list(p) for t, p in layout.switch_of.items()},
        "start_room": room_json(layout.start_room()),
        "looks": looks,
        "rooms": rooms,
    }


def rng_vectors() -> dict:
    r = Rng(7, 3, 2026)
    seq = [r.next_u32() for _ in range(5)]
    r2 = Rng(1)
    arr = list(range(10))
    r2.shuffle(arr)
    return {
        "mix32": {str(x): mix32(x) for x in (0, 1, 2, 0xFFFFFFFF, 123456789)},
        "hash32(1,2,3)": hash32(1, 2, 3),
        "hash32()": hash32(),
        "Rng(7,3,2026).next_u32 x5": seq,
        "Rng(1).shuffle(0..9)": arr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int)
    ap.add_argument("--golden", action="store_true")
    args = ap.parse_args()
    if args.golden:
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(os.path.join(GOLDEN_DIR, "rng_vectors.json"), "w") as f:
            json.dump(rng_vectors(), f, indent=1, ensure_ascii=False)
        for s in GOLDEN_SEEDS:
            with open(os.path.join(GOLDEN_DIR, f"seed_{s}.json"), "w") as f:
                json.dump(dump(s), f, indent=1, ensure_ascii=False)
        print("golden written:", GOLDEN_DIR)
    else:
        print(json.dumps(dump(args.seed if args.seed is not None else 1), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
