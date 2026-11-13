"""Тесты генератора. Запуск: python3 -m unittest -v test_rungen"""

import json
import os
import unittest
from dataclasses import replace

import content as C
import dump
import generator as G
import sim
from config import DEFAULT, START_5_8
from rng import Rng, hash32, mix32


class RngTest(unittest.TestCase):
    def test_vectors_match_golden(self):
        path = os.path.join(dump.GOLDEN_DIR, "rng_vectors.json")
        with open(path) as f:
            self.assertEqual(json.load(f), json.loads(json.dumps(dump.rng_vectors())))

    def test_mix32_is_32bit(self):
        for x in (0, 1, 0xFFFFFFFF, 0xDEADBEEF):
            self.assertTrue(0 <= mix32(x) <= 0xFFFFFFFF)

    def test_chance_edges(self):
        r = Rng(1)
        self.assertFalse(any(r.chance(0.0) for _ in range(1000)))
        self.assertTrue(all(r.chance(1.0) for _ in range(1000)))


class LayoutTest(unittest.TestCase):
    def test_golden_dumps(self):
        for s in dump.GOLDEN_SEEDS:
            with open(os.path.join(dump.GOLDEN_DIR, f"seed_{s}.json")) as f:
                self.assertEqual(json.load(f), json.loads(json.dumps(dump.dump(s))), f"seed {s}")

    def test_deterministic(self):
        for s in (5, 99, 123456):
            a, b = dump.dump(s), dump.dump(s)
            self.assertEqual(a, b)

    def test_validator_many_seeds(self):
        cfgs = [DEFAULT, START_5_8, replace(DEFAULT, items_in_run=10)]  # 10 — из списка «что режем»
        for cfg in cfgs:
            for s in range(1, 301):
                self.assertEqual(G.validate_layout(G.RunLayout(s, cfg)), [], f"seed {s} cfg {cfg}")

    def test_look_rules(self):
        lay = G.RunLayout(77)
        self.assertEqual(lay.look(G.ANCHOR)[0], G.BRIDGE)       # только блокнот — рубка, первая петля
        self.assertEqual(lay.look(0), (G.LIVING, 0))            # пустой карман — жилая
        self.assertEqual(lay.look(G.FINAL_MASK)[0], G.ENGINE)
        self.assertEqual(lay.start_room().room_type, G.BRIDGE)
        for k in G.all_keys():
            if k not in (G.ANCHOR, G.FINAL_MASK):
                self.assertIn(lay.look(k)[0], G.ORDINARY_TYPES)

    def test_chain_step_may_keep_room_type(self):
        """Шаг цепочки не обязан менять тип отсека (решение автора 13.11)."""
        same = 0
        for s in range(1, 301):
            lay = G.RunLayout(s)
            if lay.look(G.RM_L)[0] == lay.look(G.RM_L | G.RM_K1)[0]:
                same += 1
        self.assertGreater(same, 0)

    def test_pocket_key(self):
        lay = G.RunLayout(3)
        d = lay.dummies[0]
        self.assertEqual(lay.pocket_key([]), 0)
        self.assertEqual(lay.pocket_key([d]), 0)              # пустышки не влияют
        self.assertEqual(lay.pocket_key([G.NOTEBOOK, d, d]), G.ANCHOR)
        k = [lay.role_item[r] for r in (G.K1, G.K2, G.K3)]
        self.assertEqual(lay.pocket_key([G.NOTEBOOK] + k), G.FINAL_MASK)
        self.assertEqual(lay.pocket_key(k + [k[0]]), G.FINAL_MASK)  # без учёта повторов

    def test_roles_cover_catalog(self):
        seen = {r: set() for r in range(7)}
        for s in range(1, 401):
            lay = G.RunLayout(s)
            for it in lay.run_items:
                seen[lay.role_of(it)].add(it)
        for r, items in seen.items():
            self.assertEqual(len(items), len(C.CATALOG), f"role {G.ROLE_NAMES[r]}")

    def test_notes_render(self):
        for s in range(1, 101):
            lay = G.RunLayout(s)
            texts = [lay.first_note.text()]
            for k in G.all_keys():
                for c in (1, 2, 3):
                    texts += [n.text() for n in lay.room_copy(k, c).notes]
            for t in texts:
                self.assertNotIn("{", t)
                self.assertTrue(t.isascii(), t)

    def test_validator_catches_broken_layouts(self):
        """Валидатор должен ловить порчу, иначе его «0 ошибок» ничего не значит."""
        lay = G.RunLayout(11)
        orig = lay.room_copy

        def k2_too_early(key, copy):  # K2 в комнате без K1
            rc = orig(key, copy)
            if key == G.RM_L and copy == 2:
                return replace(rc, items=rc.items + (lay.role_item[G.K2],))
            return rc
        lay.room_copy = k2_too_early
        self.assertTrue(any("without prerequisites" in e for e in G.validate_layout(lay)))

        def lying_note(key, copy):  # пустышку назвали опасной
            rc = orig(key, copy)
            if key == G.ANCHOR and copy == 3:
                return replace(rc, notes=rc.notes + (G.Note(G.N_DANGER, (lay.dummies[0],), 0),))
            return rc
        lay.room_copy = lying_note
        self.assertTrue(any("false note" in e for e in G.validate_layout(lay)))

        def no_ahead_note(key, copy):  # первая копия без записки на шаг вперёд
            rc = orig(key, copy)
            if key == G.RM_L and copy == 1:
                return replace(rc, notes=())
            return rc
        lay.room_copy = no_ahead_note
        self.assertTrue(any("next-link note" in e for e in G.validate_layout(lay)))

        lay2 = G.RunLayout(12)
        orig_look = lay2.look
        lay2.look = lambda key: (G.LIVING, 0) if key == G.ANCHOR else orig_look(key)  # блокнот не в рубку
        self.assertTrue(any("bridge rule" in e for e in G.validate_layout(lay2)))

    def test_catalog(self):
        self.assertEqual(len(C.CATALOG), 16)
        self.assertEqual(len({i.name for i in C.CATALOG}), 16)


class SimTest(unittest.TestCase):
    def test_notes_player_always_finishes(self):
        for cfg in (DEFAULT, replace(DEFAULT, items_in_run=10)):
            for s in range(1, 501):
                r = sim.NotesPlayer(G.RunLayout(s, cfg), health=10 ** 9).run()
                self.assertEqual(r.status, "win", f"seed {s}")
                self.assertEqual(r.guess_rooms, 0)

    def test_notes_player_with_misses_finishes(self):
        for s in range(1, 301):
            r = sim.NotesPlayer(G.RunLayout(s), health=10 ** 9, miss=0.5).run()
            self.assertEqual(r.status, "win", f"seed {s}")

    def test_finale_keeps_notebook_and_reaches_bridge(self):
        for s in range(1, 101):
            p = sim.NotesPlayer(G.RunLayout(s), health=10 ** 9)
            r = p.run()
            self.assertEqual(r.status, "win")
            self.assertEqual(p.pocket, [G.NOTEBOOK])
            self.assertEqual(p.room.look[0], G.BRIDGE)
            self.assertTrue(p.engine_fixed)

    def test_anomaly_state_persists(self):
        """Устранённая аномалия не бьёт; неустранённая бьёт при каждом входе."""
        never_fix = replace(DEFAULT, p_hit=1.0, p_fix=0.0)
        always_fix = replace(DEFAULT, p_hit=1.0, p_fix=1.0)
        for s in range(1, 201):
            r = sim.NotesPlayer(G.RunLayout(s, never_fix), health=10 ** 9).run()
            self.assertEqual(r.hits, r.anomaly_entries)
            p = sim.NotesPlayer(G.RunLayout(s, always_fix), health=10 ** 9)
            r = p.run()
            # победная рубка не в счёт: концовка наступает раньше, чем аномалия успевает ударить
            anomalous = sum(1 for rid in p.visited if rid != p.cur and p.world.rooms[rid].anomaly != G.NO_ANOMALY)
            self.assertEqual(r.anomaly_entries, anomalous)  # в каждую аномальную комнату — ровно одно попадание

    def test_sim_deterministic(self):
        for name in sim.PLAYERS:
            a = sim.run_many(DEFAULT, range(1, 50), name)
            b = sim.run_many(DEFAULT, range(1, 50), name)
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
