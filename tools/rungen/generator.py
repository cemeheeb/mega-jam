"""Эталонный генератор забега: зерно -> раскладка. Чистая логика без движка.

Разделы DESIGN.md: 5.4–5.8. Всё, что зависит от случая, берётся из Rng с ключом
(seed, домен, ...), поэтому каждая величина считается независимо от остальных
и порядок вызовов в других местах на неё не влияет.

Сигнатура хранится как маска ролей: бит 0 — проводник L, 1–3 — ключи K1–K3, биты с 4-го —
лишние значимые предметы E1, E2, ... (их число задаёт Config.extras). Опасных предметов нет:
аномалию несёт набор целиком. Пустышки в маску не попадают. Ключ комнаты = маска, а при пустой
маске ключ — ANCHOR: без значимых предметов (пустой карман, блокнот, оружие, пустышки) любая дверь ведёт
в капитанскую рубку, это первая петля (решение автора 15.11, вечер: раньше так было только с одним блокнотом,
а совсем пустой карман вёл в жилую комнату). Счётчики копий можно держать в массиве.
"""

from dataclasses import dataclass

import content as C
from config import Config, DEFAULT
from rng import Rng, hash32

# Роли значимых предметов = номера битов в маске
L, K1, K2, K3 = 0, 1, 2, 3
NUM_CHAIN = 4           # роли правильного пути; дальше идут лишние значимые: 4, 5, ...
MAX_SIG = 12            # предел числа значимых предметов: столько битов в маске
DUMMY = 99
NOT_IN_RUN = -1
NUM_SWITCHES = 6        # переключателей в отсеке обычного типа, 5.1


def role_name(r: int) -> str:
    if r == DUMMY:
        return "dummy"
    return ("L", "K1", "K2", "K3")[r] if r < NUM_CHAIN else f"E{r - NUM_CHAIN + 1}"


RM_L, RM_K1, RM_K2, RM_K3 = 1, 2, 4, 8
FINAL_MASK = RM_K1 | RM_K2 | RM_K3
ANCHOR = 1 << MAX_SIG   # 4096: ключ «ничего значимого» — рубка
NOTEBOOK = -1           # id блокнота в кармане (вне каталога)
WEAPON = -2             # id оружия: занимает слот, на комнату не влияет (5.3, вопрос 12.3)
SUIT = -4               # id скафандра: надевается, слот не занимает, на комнату не влияет (5.3, 5.9). −3 — аптечка игры
CARD = -5               # id карточки капитана (лор автора 15.11): в двигательном отсеке, слот занимает, на комнату не влияет
POCKET_SLOTS = 4

# Типы отсеков, 5.1
# Рубка и двигательный отсек бывают только при своих наборах. Остальные типы — обычные: их получает
# набор по хешу. Четыре последних добавлены автором 13.11 сверх пяти из раздела 5.1.
BRIDGE, LIVING, LAB, LIFE_SUPPORT, ENGINE, MEDBAY, CARGO, MESS, COMPUTER = range(9)
ROOM_TYPE_NAMES = ("Bridge", "Living", "Lab", "LifeSupport", "Engine", "Medbay", "Cargo", "Mess", "Computer")
ORDINARY_TYPES = (LIVING, LAB, LIFE_SUPPORT, MEDBAY, CARGO, MESS, COMPUTER)

# Класс комнаты. CLS_START — только стартовая рубка (копия 0), у ключей такого класса нет.
CLS_START, CLS_CHAIN, CLS_GUESS, CLS_ENGINE = 0, 1, 2, 3
CLS_NAMES = ("start", "chain", "guess", "engine")

# Угрозы неправильных наборов, 5.9: четыре аномалии (решение автора 15.11, вместо прежних четырёх и эха)
# и три противника (добавлены 13.11). В коде и данных всё это по-прежнему называется anomaly.
# Разгерметизация — не угроза догадки, а ворота правильного пути, её здесь нет.
NO_ANOMALY, BLACK_HOLE, SMOKE, SLOW_TIME, FUNGUS, ROBOT, RATS, HUMAN = range(8)
ANOMALY_NAMES = ("none", "BlackHole", "Smoke", "SlowTime", "Fungus", "Robot", "Rats", "Human")
NUM_ANOMALIES = len(ANOMALY_NAMES) - 1

# Записки
N_NOTEBOOK_FIRST, N_LOOP_EXIT, N_NEXT_KEY, N_USELESS, N_DANGER, N_ENGINE_SET, N_FINALE = range(7)

# Двери, 5.2 (решение автора 13.11): в каждой комнате четыре двери — север, юг, запад, восток.
# В комнату входят через одну из них, остальные три не раскрыты. В стартовой рубке не раскрыты все четыре.
DOORS_PER_ROOM = 4

# Домены ГСЧ. Номер 6 раньше выбирал число дверей, с 15.11 (вечер) — тайник проводника в рубке. Номер 2 (раньше
# типы уровней цепочки) — с 15.11 уровень разгерметизации.
D_ROLES, D_DECOMP, D_ROOM_TYPE, D_SWITCH, D_ANOMALY, D_HIDE, D_ITEMS, D_NOTES, \
    D_GUARANTEE, D_COSMETIC, D_START, D_PLAYER = range(1, 13)

# Тайников проводника в рубке (решение автора 15.11, вечер): в рубке лежит только проводник, спрятанный в одном
# из этих мест; какое — решает зерно. Сами места — в RunDirector.cpp (RunStory::HideSpots).
NUM_HIDE_SPOTS = 3

# Цепочка: уровень петли -> роль предмета, который из неё выводит
CHAIN_TARGET = (L, K1, K2, K3)
# Предпосылки ключей, 5.7.2
PREREQ = {K1: RM_L, K2: RM_K1, K3: RM_K1 | RM_K2}


def popcount(x: int) -> int:
    return bin(x).count("1")


def room_key(role_mask: int, has_notebook: bool = False) -> int:
    """has_notebook больше не влияет (15.11, вечер): без значимых предметов дверь всегда ведёт в рубку."""
    return role_mask if role_mask else ANCHOR


def chain_level(key: int) -> int:
    """Уровень петли: 0 — без значимых предметов (рубка-петля), 1 {L}, 2 {L,K1}/{K1}, 3 {L,K1,K2}/{K1,K2},
    4 двигательный отсек. -1 — догадка."""
    if key in (0, ANCHOR):
        return 0
    if key >> NUM_CHAIN:    # в наборе есть лишний значимый предмет
        return -1
    if key & RM_K3:
        return 4 if key == FINAL_MASK else -1
    if key & RM_K2:
        return 3 if key & RM_K1 else -1
    if key & RM_K1:
        return 2
    if key & RM_L:
        return 1
    return -1


def room_class(key: int) -> int:
    lvl = chain_level(key)
    if lvl == 4:
        return CLS_ENGINE
    if lvl >= 0:
        return CLS_CHAIN
    return CLS_GUESS


def all_keys(num_sig: int, max_items: int = POCKET_SLOTS) -> list[int]:
    """Все ключи, которые можно получить карманом на 4 слота при num_sig значимых предметах."""
    keys = [ANCHOR]
    keys += [m for m in range(1, 1 << num_sig) if popcount(m) <= max_items]
    return keys


@dataclass(frozen=True)
class Note:
    kind: int
    items: tuple[int, ...]  # id предметов: см. порядок ниже
    tpl: int                # номер шаблона текста
    # NOTEBOOK_FIRST: (L,)  LOOP_EXIT: (цель,)  NEXT_KEY: (ключ, *предпосылки)
    # USELESS: (пустышка,)  DANGER: (предмет, предмет) — опасная пара  ENGINE_SET: (K1, K2, K3, L)  FINALE: ()

    def text(self) -> str:
        return C.render(self.kind, self.tpl, self.items)


@dataclass(frozen=True)
class RoomContent:
    """Комната набора. Решение автора 13.11: всё в комнате определяет набор в кармане, а не дверь.
    Сколько бы дверей ни раскрыли с одним набором, за ними одна и та же комната с теми же вещами."""
    key: int
    room_type: int
    switches: int
    anomaly: int
    items: tuple[int, ...]   # id предметов (NOTEBOOK для блокнота)
    notes: tuple[Note, ...]


class RunLayout:
    """Раскладка забега. Всё вычисляется из seed и cfg."""

    def __init__(self, seed: int, cfg: Config = DEFAULT):
        self.num_sig = NUM_CHAIN + cfg.extras   # значимых предметов в забеге
        if not (0 <= cfg.extras and self.num_sig <= MAX_SIG):
            raise ValueError("extras out of range")
        if cfg.items_in_run < self.num_sig + 2 or cfg.items_in_run > len(C.CATALOG):
            raise ValueError("items_in_run out of range")
        self.seed = seed & 0xFFFFFFFF
        self.cfg = cfg

        # 1. Роли. Перемешать каталог, первые items_in_run идут в забег;
        #    из них первые шесть получают роли L, K1, K2, K3, X, Y, остальные — пустышки.
        order = list(range(len(C.CATALOG)))
        Rng(self.seed, D_ROLES).shuffle(order)
        self.run_items: tuple[int, ...] = tuple(order[:cfg.items_in_run])
        self.role_item: tuple[int, ...] = self.run_items[:self.num_sig]
        self.dummies: tuple[int, ...] = self.run_items[self.num_sig:]
        self.extras: tuple[int, ...] = self.role_item[NUM_CHAIN:]
        self.item_role = [NOT_IN_RUN] * len(C.CATALOG)
        for r, it in enumerate(self.role_item):
            self.item_role[it] = r
        for it in self.dummies:
            self.item_role[it] = DUMMY

        # 2. Тип отсека для сигнатуры со значимыми предметами — по хешу в look().
        #    Шаг цепочки не обязан менять тип: выход из петли видно по переключателям
        #    и поведению комнаты (решение автора 13.11).

        # 3. Переключатели, 5.1: в каждом обычном типе каждый значимый предмет
        #    включает ровно один из шести переключателей. switch_of[type][role] -> номер.
        self.switch_of: dict[int, tuple[int, ...]] = {}
        for t in ORDINARY_TYPES:
            # Переключателей шесть. Первые шесть ролей получают разные, поэтому наборы правильного
            # пути всегда выглядят по-разному. Остальные лишние предметы делят переключатели с ними:
            # комната может выглядеть так же, но быть другой (решение автора 13.11).
            srng = Rng(self.seed, D_SWITCH, t)
            perm = list(range(NUM_SWITCHES))
            srng.shuffle(perm)                                              # rng: перестановка
            sw = [perm[r] for r in range(min(self.num_sig, NUM_SWITCHES))]
            sw += [srng.below(NUM_SWITCHES) for _ in range(NUM_SWITCHES, self.num_sig)]   # rng: по одному на роль
            self.switch_of[t] = tuple(sw)
        # Рубка (только блокнот) и двигательный отсек бывают при одной сигнатуре:
        # их переключатели косметические, постоянные в пределах забега.
        self.bridge_switches = hash32(self.seed, D_COSMETIC, BRIDGE) & 63
        self.engine_switches = hash32(self.seed, D_COSMETIC, ENGINE) & 63

        # 4. Прочие предметы для раскладки: пустышки и ложные.
        self.filler_pool: tuple[int, ...] = self.dummies + self.extras
        self.filler_weights: tuple[int, ...] = ((cfg.dummy_weight,) * len(self.dummies)
                                                + (cfg.extra_weight,) * len(self.extras))

        self.first_note = Note(N_NOTEBOOK_FIRST, (self.role_item[L],), 0)
        # тайник проводника в рубке
        self.hide_spot = hash32(self.seed, D_HIDE) % NUM_HIDE_SPOTS

        # Разгерметизация (решение автора 15.11, схема ассистента в DESIGN 5.9): ворота правильного пути.
        # Комнаты уровня 2 ({L,K1}, {K1} — там K2) или 3 ({L,K1,K2}, {K1,K2} — там K3) без скафандра не открываются;
        # скафандр лежит в комнатах предыдущего уровня, рядом с предыдущим ключом, — его встречают раньше ворот.
        self.decomp_level = 2 + (hash32(self.seed, D_DECOMP) & 1)

        # 5. Опасные пары для записок (решение автора 13.11: опасны не предметы, а сочетания).
        #    Пара значимых предметов опасна, если набор ровно из них двоих даёт комнату с аномалией.
        #    Порядок: по номерам ролей, меньшая первой.
        self.danger_pairs: tuple[tuple[int, int], ...] = tuple(
            (self.role_item[a], self.role_item[b])
            for a in range(self.num_sig) for b in range(a + 1, self.num_sig)
            if self.anomaly_of((1 << a) | (1 << b)) != NO_ANOMALY)

    # ---------- роли и сигнатуры ----------

    def all_keys(self) -> list[int]:
        return all_keys(self.num_sig)

    def role_of(self, item: int) -> int:
        if item < 0:   # блокнот и оружие вне каталога и на комнату не влияют
            return NOT_IN_RUN
        return self.item_role[item]

    def role_mask(self, pocket) -> int:
        m = 0
        for it in pocket:
            r = self.role_of(it)
            if 0 <= r < self.num_sig:
                m |= 1 << r
        return m

    def pocket_key(self, pocket) -> int:
        return room_key(self.role_mask(pocket), NOTEBOOK in pocket)

    # ---------- сигнатура -> вид комнаты ----------

    def look(self, key: int) -> tuple[int, int]:
        """(тип отсека, маска переключателей). Детерминирована от seed и key."""
        if key == ANCHOR:
            return BRIDGE, self.bridge_switches
        if key == FINAL_MASK:
            return ENGINE, self.engine_switches
        t = ORDINARY_TYPES[hash32(self.seed, D_ROOM_TYPE, key) % len(ORDINARY_TYPES)]
        sw = 0
        perm = self.switch_of[t]
        for r in range(self.num_sig):
            if key & (1 << r):
                sw |= 1 << perm[r]
        return t, sw

    def needs_suit(self, key: int) -> bool:
        """Комната набора — разгерметизация: дверь в неё без скафандра не открывается."""
        return room_class(key) == CLS_CHAIN and chain_level(key) == self.decomp_level

    def suit_lies_in(self, key: int) -> bool:
        """Скафандр лежит в комнате этого набора: уровень цепочки перед разгерметизацией."""
        return room_class(key) == CLS_CHAIN and chain_level(key) == self.decomp_level - 1

    def anomaly_of(self, key: int) -> int:
        """Аномалия набора (решение автора 13.11): зависит только от зерна и сигнатуры, поэтому
        один набор в забеге всегда даёт одну и ту же аномалию или её отсутствие, в любой копии.
        Правильный путь безопасен: у комнат цепочки и двигательного отсека аномалий нет.
        У догадки аномалия есть с шансом p_guess, её вид — один из семи (ANOMALY_NAMES), поровну."""
        if room_class(key) != CLS_GUESS:
            return NO_ANOMALY
        rng = Rng(self.seed, D_ANOMALY, key)
        if not rng.chance(self.cfg.p_guess):                         # rng: есть ли аномалия у набора
            return NO_ANOMALY
        return 1 + rng.below(NUM_ANOMALIES)                          # rng: вид

    # ---------- записки ----------

    def _ahead_note(self, lvl: int) -> tuple[int, tuple[int, ...]]:
        """Записка «на шаг вперёд» для петли уровня lvl, 5.7.4."""
        ri = self.role_item
        if lvl == 0:
            return N_NEXT_KEY, (ri[K1], ri[L])
        if lvl == 1:
            return N_NEXT_KEY, (ri[K2], ri[K1])
        if lvl == 2:
            return N_NEXT_KEY, (ri[K3], ri[K1], ri[K2])
        return N_ENGINE_SET, (ri[K1], ri[K2], ri[K3], ri[L])

    def _danger_note(self, rng: Rng) -> tuple[int, tuple[int, ...]]:
        """Записка об опасной паре. Если в забеге таких пар нет — записка о пустышке."""
        if self.danger_pairs:
            return N_DANGER, self.danger_pairs[rng.below(len(self.danger_pairs))]
        return N_USELESS, (self.dummies[rng.below(len(self.dummies))],)

    def _note(self, rng: Rng, kind: int, items: tuple[int, ...]) -> Note:
        return Note(kind, items, rng.below(len(C.TEMPLATES[kind])))

    def _chain_notes(self, key: int) -> tuple[Note, ...]:
        # Порядок вызовов rng важен для порта: см. комментарии.
        lvl = chain_level(key)
        rng = Rng(self.seed, D_NOTES, key)
        kind, items = self._ahead_note(lvl)                      # записка на шаг вперёд есть всегда, 5.7.4
        notes = [self._note(rng, kind, items)]                   # rng: шаблон
        if rng.chance(self.cfg.p_extra_note):                    # rng: есть ли вторая записка
            pick = rng.weighted([2, 2, 1])                       # rng: вид
            if pick == 0:
                kind, items = N_LOOP_EXIT, (self.role_item[CHAIN_TARGET[lvl]],)
            elif pick == 1:
                kind, items = N_USELESS, (self.dummies[rng.below(len(self.dummies))],)   # rng: предмет
            else:
                kind, items = self._danger_note(rng)                                   # rng: пара или пустышка
            notes.append(self._note(rng, kind, items))           # rng: шаблон
        return tuple(notes)

    def _guess_notes(self, key: int) -> tuple[Note, ...]:
        rng = Rng(self.seed, D_NOTES, key)
        if not rng.chance(self.cfg.p_guess_note):
            return ()
        if rng.weighted([2, 1]) == 0:
            kind, items = N_USELESS, (self.dummies[rng.below(len(self.dummies))],)
        else:
            kind, items = self._danger_note(rng)
        return (self._note(rng, kind, items),)

    # ---------- содержимое копии комнаты ----------

    def _draw_filler(self, rng: Rng, n: int) -> list[int]:
        pool = list(self.filler_pool)
        weights = list(self.filler_weights)
        out = []
        for _ in range(min(n, len(pool))):
            i = rng.weighted(weights)
            out.append(pool.pop(i))
            weights.pop(i)
        return out

    def target_of(self, key: int) -> int | None:
        """Предмет правильного пути, который лежит в комнате этого набора, или None.
        Рубка (ничего значимого) — проводник L; {L} — K1; {L,K1} и {K1} — K2; {L,K1,K2} и {K1,K2} — K3.
        В двигательном отсеке таких предметов нет."""
        if room_class(key) != CLS_CHAIN:
            return None
        return self.role_item[CHAIN_TARGET[chain_level(key)]]

    def room(self, key: int) -> RoomContent:
        """Комната набора: вид, аномалия, предметы и записки. Зависит только от зерна и набора."""
        cfg = self.cfg
        t, sw = self.look(key)
        cls = room_class(key)
        if cls == CLS_ENGINE:
            rng = Rng(self.seed, D_NOTES, key)
            return RoomContent(key, t, sw, NO_ANOMALY, (CARD,), (self._note(rng, N_FINALE, ()),))

        if key == ANCHOR:
            # Рубка (решение автора 15.11, вечер): только проводник, спрятанный (hide_spot), без записок и прочего.
            # Игрок выходит без него и попадает в ту же рубку — понимает, что он в петле; находит проводника,
            # выходит с ним — и видит новую комнату. Читать для этого ничего не нужно. ГСЧ не тратит.
            return RoomContent(key, t, sw, NO_ANOMALY, (self.role_item[L],), ())

        irng = Rng(self.seed, D_ITEMS, key)
        items: list[int] = []
        if key == RM_L:
            items += [NOTEBOOK, WEAPON]            # первая новая комната: блокнот и ключ переехали сюда из рубки
        target = self.target_of(key)
        if target is not None:
            items.append(target)
        if self.suit_lies_in(key):
            items.append(SUIT)                     # ГСЧ не тратит: раскладка прочих предметов та же
        n_fill = cfg.filler_min + irng.below(cfg.filler_max - cfg.filler_min + 1)   # rng: сколько прочих
        if key == RM_L:
            n_fill = max(1, n_fill - 2)            # вещей столько же, сколько было до блокнота и ключа
        items += self._draw_filler(irng, n_fill)                                    # rng: какие
        notes = self._chain_notes(key) if cls == CLS_CHAIN else self._guess_notes(key)
        return RoomContent(key, t, sw, self.anomaly_of(key), tuple(items), notes)

    def start_room(self) -> RoomContent:
        """Рубка в начале забега — комната набора «ничего значимого»: раскрыв дверь без проводника,
        игрок попадает в неё же, это первая петля. С 15.11 (вечер) блокнот и ключ лежат в комнате {L}."""
        return self.room(ANCHOR)

    # ---------- описание для дампа ----------

    def describe(self) -> dict:
        ri = self.role_item
        return {
            "seed": self.seed,
            "roles": {role_name(r): C.CATALOG[ri[r]].name for r in range(self.num_sig)},
            "dummies": [C.CATALOG[i].name for i in self.dummies],
            "chain": [C.CATALOG[ri[r]].name for r in CHAIN_TARGET],
            "final_set": [C.CATALOG[ri[r]].name for r in (K1, K2, K3)],
            "chain_room_types": {name: ROOM_TYPE_NAMES[self.look(k)[0]] for name, k in (
                ("nothing that matters", ANCHOR), ("L", RM_L), ("L,K1", RM_L | RM_K1),
                ("K1", RM_K1), ("L,K1,K2", RM_L | RM_K1 | RM_K2), ("K1,K2", RM_K1 | RM_K2),
                ("K1,K2,K3", FINAL_MASK))},
            "notebook_first": self.first_note.text(),
            "decompression_level": self.decomp_level,
            "hide_spot": self.hide_spot,
        }


# ---------- проверка правдивости записок ----------

def note_is_true(layout: RunLayout, note: Note, key: int) -> bool:
    """Независимая проверка утверждения записки по ролям забега."""
    role = layout.role_of
    ri = layout.role_item
    if note.kind == N_NOTEBOOK_FIRST:
        return note.items == (ri[L],)
    if note.kind == N_LOOP_EXIT:
        lvl = chain_level(key)
        return 0 <= lvl <= 3 and note.items == (ri[CHAIN_TARGET[lvl]],)
    if note.kind == N_NEXT_KEY:
        k = role(note.items[0])
        if k not in PREREQ:
            return False
        pre = 0
        for it in note.items[1:]:
            r = role(it)
            if not (0 <= r < layout.num_sig):
                return False
            pre |= 1 << r
        return pre == PREREQ[k] and len(note.items) - 1 == popcount(pre)
    if note.kind == N_USELESS:
        return role(note.items[0]) == DUMMY
    if note.kind == N_DANGER:
        roles = [role(it) for it in note.items]
        if len(roles) != 2 or roles[0] == roles[1] or not all(0 <= r < layout.num_sig for r in roles):
            return False
        return layout.anomaly_of((1 << roles[0]) | (1 << roles[1])) != NO_ANOMALY
    if note.kind == N_ENGINE_SET:
        return note.items == (ri[K1], ri[K2], ri[K3], ri[L])
    if note.kind == N_FINALE:
        return note.items == () and room_class(key) == CLS_ENGINE
    return False


def validate_layout(layout: RunLayout) -> list[str]:
    """Статическая проверка раскладки. Пустой список — ошибок нет."""
    err: list[str] = []
    cfg = layout.cfg
    ri = layout.role_item

    if len(set(layout.run_items)) != cfg.items_in_run:
        err.append("run items not distinct")
    if layout.first_note.items != (ri[L],):
        err.append("notebook first entry does not name L")
    if popcount(FINAL_MASK) > POCKET_SLOTS - 1:
        err.append("final set does not fit next to the notebook")

    # Вид комнаты: рубка только при одном блокноте, жилая при пустом кармане, двигатель только
    # при финальной сигнатуре, один вид на одну сигнатуру. Наборы правильного пути выглядят по-разному;
    # прочие наборы могут совпадать видом: комната выглядит так же, но она другая.
    seen_looks: dict[tuple[int, int], int] = {}
    for key in all_keys(layout.num_sig):
        t, sw = layout.look(key)
        if (t == BRIDGE) != (key == ANCHOR):
            err.append(f"key {key}: bridge rule broken")
        if (t == ENGINE) != (key == FINAL_MASK):
            err.append(f"key {key}: engine rule broken")
        if room_class(key) != CLS_GUESS:
            if (t, sw) in seen_looks:
                err.append(f"right-path keys {seen_looks[(t, sw)]} and {key} look identical")
            seen_looks[(t, sw)] = key
        if layout.look(key) != (t, sw):
            err.append(f"key {key}: look not deterministic")

    # Содержимое комнат: зависит только от набора; предметы правильного пути лежат каждый в своей
    # комнате; записки правдивы; в каждой комнате цепочки есть записка на шаг вперёд.
    chain_items = (ri[L], ri[K1], ri[K2], ri[K3])
    for key in all_keys(layout.num_sig):
        cls = room_class(key)
        lvl = chain_level(key)
        rc = layout.room(key)
        if rc != layout.room(key):
            err.append(f"key {key}: content not deterministic")
        target = layout.target_of(key)
        want_target = None if cls != CLS_CHAIN else ri[CHAIN_TARGET[lvl]]
        if target != want_target:
            err.append(f"key {key}: wrong right-path item for this set")
        if len(set(rc.items)) != len(rc.items):
            err.append(f"key {key}: item repeated in one room")
        for it in rc.items:
            if it in chain_items and it != target:
                err.append(f"key {key}: right-path item {role_name(layout.role_of(it))} lies in a wrong room")
            if it not in (SUIT, CARD, NOTEBOOK, WEAPON) and layout.role_of(it) == NOT_IN_RUN:
                err.append(f"key {key}: item not in this run")
        if target is not None and target not in rc.items:
            err.append(f"key {key}: right-path item is missing")
        for n in rc.notes:
            if not note_is_true(layout, n, key):
                err.append(f"key {key}: false note {n}")
            if n.kind in (N_LOOP_EXIT, N_NEXT_KEY, N_ENGINE_SET) and cls != CLS_CHAIN:
                err.append(f"key {key}: chain note outside the chain")
        if cls != CLS_GUESS and rc.anomaly != NO_ANOMALY:
            err.append(f"key {key}: anomaly on the right path")
        if rc.anomaly != layout.anomaly_of(key):
            err.append(f"key {key}: anomaly differs from the set's anomaly")
        if cls == CLS_CHAIN and key != ANCHOR:   # в рубке записок нет: из петли выводят без чтения
            want_kind, want_items = layout._ahead_note(lvl)
            if not any(n.kind == want_kind and n.items == want_items for n in rc.notes):
                err.append(f"key {key}: room lacks the next-link note")
    # Разгерметизация: уровень 2 или 3; скафандр лежит ровно в комнатах уровня перед ней, и больше нигде
    if layout.decomp_level not in (2, 3):
        err.append(f"decompression level {layout.decomp_level} out of 2..3")
    for key in all_keys(layout.num_sig):
        has_suit = SUIT in layout.room(key).items
        if has_suit != (room_class(key) == CLS_CHAIN and chain_level(key) == layout.decomp_level - 1):
            err.append(f"key {key}: suit {'misplaced' if has_suit else 'missing'}")
    start = layout.start_room()
    if start != layout.room(ANCHOR) or start.items != (ri[L],) or start.notes:
        err.append("start room is not the bridge with only L in it")
    first = layout.room(RM_L).items
    if first[:2] != (NOTEBOOK, WEAPON) or ri[K1] not in first:
        err.append("the {L} room lacks the notebook, the wrench or K1")
    if not 0 <= layout.hide_spot < NUM_HIDE_SPOTS:
        err.append("hide spot out of range")
    if layout.pocket_key([]) != ANCHOR or layout.pocket_key([NOTEBOOK, WEAPON] + list(layout.dummies[:2])) != ANCHOR:
        err.append("a pocket with nothing that matters does not lead to the bridge")
    return err
