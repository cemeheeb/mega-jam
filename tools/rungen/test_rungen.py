"""Тесты генератора. Запуск: python3 -m unittest -v test_rungen"""

import json
import os
import unittest
from dataclasses import replace

import content as C
import dump
import generator as G
import sim
from config import DEFAULT
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
        cfgs = [DEFAULT, replace(DEFAULT, p_guess=0.85), replace(DEFAULT, items_in_run=10, extras=2)]  # последний — из списка «что режем»
        for cfg in cfgs:
            for s in range(1, 301):
                self.assertEqual(G.validate_layout(G.RunLayout(s, cfg)), [], f"seed {s} cfg {cfg}")

    def test_look_rules(self):
        lay = G.RunLayout(77)
        self.assertEqual(lay.look(G.ANCHOR)[0], G.BRIDGE)       # ничего значимого — рубка, первая петля
        self.assertEqual(lay.look(G.FINAL_MASK)[0], G.ENGINE)
        self.assertEqual(lay.start_room().room_type, G.BRIDGE)
        for k in lay.all_keys():
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
        self.assertEqual(lay.pocket_key([]), G.ANCHOR)         # 15.11 (вечер): пустой карман — тоже рубка
        self.assertEqual(lay.pocket_key([d]), G.ANCHOR)        # пустышки не влияют
        self.assertEqual(lay.pocket_key([G.NOTEBOOK, G.WEAPON, d, d]), G.ANCHOR)
        k = [lay.role_item[r] for r in (G.K1, G.K2, G.K3)]
        self.assertEqual(lay.pocket_key([G.NOTEBOOK] + k), G.FINAL_MASK)
        self.assertEqual(lay.pocket_key(k + [k[0]]), G.FINAL_MASK)  # без учёта повторов

    def test_roles_cover_catalog(self):
        seen = {r: set() for r in list(range(G.NUM_CHAIN + DEFAULT.extras)) + [G.DUMMY]}
        for s in range(1, 401):
            lay = G.RunLayout(s)
            for it in lay.run_items:
                seen[lay.role_of(it)].add(it)
        for r, items in seen.items():
            self.assertEqual(len(items), len(C.CATALOG), f"role {G.role_name(r)}")

    def test_notes_render(self):
        for s in range(1, 101):
            lay = G.RunLayout(s)
            texts = [lay.first_note.text()]
            for k in lay.all_keys():
                texts += [n.text() for n in lay.room(k).notes]
            for t in texts:
                self.assertNotIn("{", t)
                self.assertTrue(t.isascii(), t)

    def test_validator_catches_broken_layouts(self):
        """Валидатор должен ловить порчу, иначе его «0 ошибок» ничего не значит."""
        lay = G.RunLayout(11)
        orig = lay.room

        def k2_too_early(key):  # K2 в комнате набора {L}, где должен лежать только K1
            rc = orig(key)
            return replace(rc, items=rc.items + (lay.role_item[G.K2],)) if key == G.RM_L else rc
        lay.room = k2_too_early
        self.assertTrue(any("lies in a wrong room" in e for e in G.validate_layout(lay)))

        def lying_note(key):  # пустышку назвали половиной опасной пары
            rc = orig(key)
            note = G.Note(G.N_DANGER, (lay.dummies[0], lay.role_item[G.L]), 0)
            return replace(rc, notes=rc.notes + (note,)) if key == G.RM_L else rc
        lay.room = lying_note
        self.assertTrue(any("false note" in e for e in G.validate_layout(lay)))

        def no_ahead_note(key):  # комната правильного пути без записки на шаг вперёд
            rc = orig(key)
            return replace(rc, notes=()) if key == G.RM_L else rc
        lay.room = no_ahead_note
        self.assertTrue(any("next-link note" in e for e in G.validate_layout(lay)))

        def no_leader(key):  # в рубке нет проводника
            rc = orig(key)
            return replace(rc, items=tuple(i for i in rc.items if i != lay.role_item[G.L])) if key == G.ANCHOR else rc
        lay.room = no_leader
        self.assertTrue(any("right-path item is missing" in e for e in G.validate_layout(lay)))

        lay2 = G.RunLayout(12)
        orig_look = lay2.look
        lay2.look = lambda key: (G.LIVING, 0) if key == G.ANCHOR else orig_look(key)  # пустой карман не в рубку
        self.assertTrue(any("bridge rule" in e for e in G.validate_layout(lay2)))

    def test_catalog(self):
        self.assertEqual(len(C.CATALOG), 16)
        self.assertEqual(len({i.name for i in C.CATALOG}), 16)


class SimTest(unittest.TestCase):
    def test_notes_player_always_finishes(self):
        for cfg in (DEFAULT, replace(DEFAULT, items_in_run=10, extras=2)):
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

    def test_anomaly_depends_on_set(self):
        """Аномалия — свойство набора (решение автора 13.11): один набор — одна аномалия во всех копиях;
        на правильном пути аномалий нет; у неправильных наборов она есть примерно в p_guess случаев."""
        with_anomaly = total = 0
        for s in range(1, 201):
            layout = G.RunLayout(s)
            for key in layout.all_keys():
                a = layout.anomaly_of(key)
                self.assertEqual(layout.room(key).anomaly, a)
                if G.room_class(key) == G.CLS_GUESS:
                    total += 1
                    with_anomaly += a != G.NO_ANOMALY
                else:
                    self.assertEqual(a, G.NO_ANOMALY)
        self.assertAlmostEqual(with_anomaly / total, DEFAULT.p_guess, delta=0.02)

    def test_room_depends_only_on_set(self):
        """Решение автора 13.11: неважно, какую дверь раскрыть, важно, что в руках. Сколько бы дверей
        ни раскрыли с одним набором, за ними та же комната с теми же вещами, и взятое не возвращается."""
        for s in range(1, 51):
            p = sim.Sim(G.RunLayout(s))
            p.enter(0)
            leader = p.L.role_item[G.L]
            self.assertEqual(p.room.items, [leader])  # 15.11 (вечер): в рубке только проводник
            seen = []
            for _ in range(3):                      # три двери подряд с пустым карманом — петля рубки
                p.cur = 0
                p.reveal(p.unrevealed()[0])
                seen.append((p.room.look, list(p.room.items), p.room.notes))
            self.assertEqual(seen[0], seen[1])
            self.assertEqual(seen[1], seen[2])
            self.assertEqual(seen[0], (p.world.rooms[0].look, [leader], ()))           # та же рубка с тем же проводником
            self.assertEqual(seen[0][0][0], G.BRIDGE)
            p.pick(leader)
            p.reveal(p.unrevealed()[0])             # с проводником — комната {L}: блокнот, ключ, K1
            self.assertEqual(p.room.key, G.RM_L)
            self.assertEqual(p.room.items[:2], [G.NOTEBOOK, G.WEAPON])
            self.assertIn(p.L.role_item[G.K1], p.room.items)
            p.drop(leader)                           # выброшенное остаётся в комнате набора
            self.assertIn(leader, p.world.items_of[G.RM_L])
            p.reveal(p.unrevealed()[0])              # снова ничего значимого — рубка, проводника в ней уже нет
            self.assertEqual(p.room.look[0], G.BRIDGE)
            self.assertNotIn(leader, p.room.items)

    def test_right_path_is_safe(self):
        """Игрок по запискам урона не получает и всегда доходит до конца."""
        for r in sim.run_many(DEFAULT, range(1, 301), "notes"):
            self.assertEqual((r.status, r.hits), ("win", 0))

    def test_anomaly_state_persists(self):
        """Устранённая аномалия не бьёт; неустранённая бьёт при каждом входе. Проверяется на игроке наугад:
        только он заходит в комнаты с аномалиями и возвращается в них."""
        never_fix = replace(DEFAULT, p_hit=1.0, p_fix=0.0)
        always_fix = replace(DEFAULT, p_hit=1.0, p_fix=1.0)
        entries = 0
        for s in range(1, 201):
            r = sim.RandomPlayer(G.RunLayout(s, never_fix), health=10 ** 9).run()
            self.assertEqual(r.hits, r.anomaly_entries)
            p = sim.RandomPlayer(G.RunLayout(s, always_fix), health=10 ** 9)
            r = p.run()
            # победная рубка не в счёт: концовка наступает раньше, чем аномалия успевает ударить
            won_in = p.cur if r.status == "win" else -1
            anomalous = sum(1 for rid in p.visited if rid != won_in and p.world.rooms[rid].anomaly != G.NO_ANOMALY)
            self.assertEqual(r.anomaly_entries, anomalous)  # в каждую аномальную комнату — ровно одно попадание
            entries += r.anomaly_entries
        self.assertGreater(entries, 100)

    def test_sim_deterministic(self):
        for name in sim.PLAYERS:
            a = sim.run_many(DEFAULT, range(1, 50), name)
            b = sim.run_many(DEFAULT, range(1, 50), name)
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
