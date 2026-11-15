"""Серая сборка девяти типов отсеков (DESIGN.md 5.1): блюпринты BP_Room_<Тип>, уровень игры Lvl_Game
и проверочный уровень Lvl_Rooms, где все комнаты стоят в ряд.

Геометрию комнаты даёт блюпринт, поведение — его C++-родитель ARunRoom (Source/MegaJam/Run/RunRoom.h).
Он ищет компоненты по именам: <N|S|W|E>_DoorInner — створки, ItemSpot*/NoteSpot* — места предметов и записок.
Размеры коробки ниже должны совпадать с RunRoomGeo в RunRoom.h.

Комнаты описаны данными ниже и собираются в редакторе через MCP. Повторный запуск
пересобирает блюпринты с нуля. Нужен открытый редактор с проектом MegaJam.

    python3 tools/ue/build_rooms.py            # обе комнаты
    python3 tools/ue/build_rooms.py Bridge     # одна
    python3 tools/ue/build_rooms.py --dry      # только показать, что будет построено

Единицы — сантиметры. Начало координат комнаты — центр пола.
Стороны света: север — +X, восток — +Y, юг — −X, запад — −Y.
Правило локаций (DESIGN.md 5.2): в каждой комнате четыре двери, по одной в каждой стене.

Вдоль стен стоят колонки-шкафы из набора Singula (SourceArt/environment/common/wall-columns, импорт —
tools/ue/import_wall_columns.py): 75 см в ширину, 45 в глубину, от пола до потолка. Стены стоят за ними,
поэтому LX × LY — комната до лица колонок, а коробка больше на LIN с каждой стороны. Раскладку колонок
делает lining() по правилам ниже (PROGRAM, ORDER), мебель ставится как раньше — перед колонками.

Реквизит из наборов Singula (tools/ue/import_singula.py) ставится через Room.mesh: аварийный пост в нишах колонок,
кнопки и маркеры у проёмов (lining), панели потолка и маячки шлюзов (fixtures), поручни в тамбурах (airlock),
кресло и органы управления на консолях рубки, мелочи на пультах и столах — в функциях комнат.
"""

import json
import math
import sys
import zlib

from uemcp import tool

BP = "editor_toolset.toolsets.blueprint.BlueprintTools"
PR = "editor_toolset.toolsets.primitive.PrimitiveTools"
AS = "editor_toolset.toolsets.asset.AssetTools"
OB = "editor_toolset.toolsets.object.ObjectTools"
SC = "editor_toolset.toolsets.scene.SceneTools"
AC = "editor_toolset.toolsets.actor.ActorTools"
MI = "editor_toolset.toolsets.material_instance.MaterialInstanceTools"

ROOT = "/Game/Game"
LEVEL = f"{ROOT}/Maps/Lvl_Rooms"
GAME_LEVEL = f"{ROOT}/Maps/Lvl_Game"
ROOM_CLASS = "/Script/MegaJam.RunRoom"
DIRECTOR_CLASS = "/Script/MegaJam.RunDirector"
# где комнаты стоят на проверочном уровне и где появляется игрок
PLACES = {"Living": (0, 0, 0), "Bridge": (0, 3000, 0), "Lab": (0, 6000, 0),
          "LifeSupport": (0, 9000, 0), "Engine": (0, 12000, 0), "Medbay": (0, 15000, 0),
          "Cargo": (0, 18000, 0), "Mess": (0, 21000, 0), "Computer": (0, 24000, 0), "Cabin": (0, 27000, 0)}
PLAYER_START = (-290, -225, 100)   # в жилой комнате, перед спальной капсулой

# --- размеры коробки, общие для всех комнат ---
LX, LY, H = 900, 750, 300      # комната внутри до лица колонок: с юга на север, с запада на восток, высота
LIN = 45                       # колонки-шкафы вдоль стен: стена стоит на столько дальше лица колонок
T = 30                         # толщина стен
DW, DH = 150, 225              # проём двери: ширина, высота
VW, VD = 450, 300              # тамбур шлюза внутри: ширина вдоль стены, глубина наружу
LEAF = 10                      # толщина створки
ENV = "/Game/Environment"      # меши наборов (колонки, реквизит из Singula): import_wall_columns.py, import_singula.py

# --- материалы: имя -> цвет поверхности (r, g, b) ---
MATERIALS = {
    "Wall": (0.62, 0.62, 0.60),
    "Floor": (0.10, 0.11, 0.12),
    "Ceiling": (0.35, 0.35, 0.35),
    "Dark": (0.06, 0.07, 0.08),
    "Door": (0.85, 0.33, 0.08),
    "Furniture": (0.42, 0.44, 0.47),
    "Bed": (0.20, 0.55, 0.58),
    "Linen": (0.80, 0.80, 0.76),
    "Glow": (0.25, 0.85, 0.95),
    "Plant": (0.18, 0.45, 0.16),
    "Tank": (0.72, 0.74, 0.76),
}
FLOOR_TILES = "/Game/Environment/Common/FloorTiles/MI_FloorTiles"   # вместо MI_Gray_Floor, если есть


class Room:
    def __init__(self, name):
        self.name = name
        self.parent = ROOM_CLASS   # класс-родитель блюпринта: у каюты свой (ARunCabin)
        self.boxes = []      # (имя, размер, центр, материал, поворот вокруг Z)
        self.cylinders = []  # (имя, радиус, высота, центр, материал, поворот (pitch, yaw, roll))
        self.lights = []     # (имя, положение, сила, радиус, цвет)
        self.spots = []      # (имя, положение): места для предметов и записок, высота — верх поверхности
        self.meshes = []     # (имя, путь меша, положение, (pitch, yaw, roll)): колонки у стен и реквизит
        self.feet = []       # (имя, размер, центр): габариты мебели-мешей по осям комнаты, для раскладки колонок
        self.scales = {}     # имя меша -> (x, y, z): масштаб в осях меша (один меш бака на три размера)

    def mesh(self, name, asset, center, yaw=0.0, rot=None, foot=None, scale=None):
        """asset — путь от /Game/Environment, например Common/Lamps/SM_CagedCeilingLamp. foot — (размер, центр)
        по осям комнаты: габарит меша-мебели, который стоит у стены (коробки и цилиндры дают габарит сами).
        Третьим в foot можно дать False: предмет не коробка со столешницей (бочка, унитаз) — колонку за ним
        он закрывает, а не служит ей рабочей поверхностью."""
        self.meshes.append((name, f"{ENV}/{asset}", center, rot or (0, yaw, 0)))
        if scale:
            self.scales[name] = scale
        if foot:
            self.feet.append((name, *foot))

    def box(self, name, size, center, mat, yaw=0.0):
        self.boxes.append((name, size, center, mat, yaw))

    def cylinder(self, name, radius, height, center, mat, rot=(0, 0, 0)):
        """Цилиндр стоит вертикально. Лежачий вдоль X — rot=(90, 0, 0), вдоль Y — rot=(90, 90, 0)."""
        self.cylinders.append((name, radius, height, center, mat, rot))

    def light(self, name, pos, intensity, radius, color):
        self.lights.append((name, pos, intensity, radius, color))

    def spots_for(self, prefix, points):
        for i, p in enumerate(points):
            self.spots.append((f"{prefix}{i + 1}", p))

    def names(self):
        return ([b[0] for b in self.boxes] + [c[0] for c in self.cylinders] + [l[0] for l in self.lights]
                + [sp[0] for sp in self.spots] + [m[0] for m in self.meshes])


# ---------- повороты реквизита ----------

UP = (0, 0, 1)
# Поручень Singula смоделирован лёжа: длинная ось Y меша, стойки вниз к основанию z = 0 (ручка в 9,5 см над ним).
GRAB_HANDLE = "Common/Handrails/SM_GrabHandle"
STORAGE_TANK = "Common/StorageTank/SM_StorageTank"            # бак 2,5 м: жизнеобеспечение, двигательный, серверная
CONTROL_CABINET = "Common/ControlCabinet/SM_ControlCabinet"   # пульт со столом на 1,0 м и экраном


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def rot_from_axes(x, y, z):
    """Поворот Unreal (pitch, yaw, roll), который переводит оси меша X, Y, Z в данные направления (FMatrix::Rotator)."""
    pitch = math.degrees(math.atan2(x[2], math.hypot(x[0], x[1])))
    yaw = math.degrees(math.atan2(x[1], x[0]))
    cp, sp, cy, sy = (math.cos(math.radians(pitch)), math.sin(math.radians(pitch)),
                      math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
    sy_axis = (-sy, cy, 0.0)        # ось Y поворота без крена
    dot = lambda a, b: sum(p * q for p, q in zip(a, b))
    roll = math.degrees(math.atan2(dot(z, sy_axis), dot(y, sy_axis)))
    return (round(pitch, 3), round(yaw, 3), round(roll, 3))


# ---------- коробка: пол, потолок, четыре стены с проёмами, четыре шлюза, свет ----------

def wall_with_door(room, prefix, axis, fixed, lo, hi, door_at):
    """Стена с проёмом. axis — вдоль какой оси идёт стена, fixed — её координата по другой оси."""
    left_len = (door_at - DW / 2) - lo
    right_len = hi - (door_at + DW / 2)
    parts = [
        ("A", left_len, lo + left_len / 2, H, H / 2),
        ("B", right_len, hi - right_len / 2, H, H / 2),
        ("Lintel", DW, door_at, H - DH, DH + (H - DH) / 2),
    ]
    for tag, length, mid, height, z in parts:
        if axis == "y":
            room.box(f"{prefix}_{tag}", (T, length, height), (fixed, mid, z), "Wall")
        else:
            room.box(f"{prefix}_{tag}", (length, T, height), (mid, fixed, z), "Wall")


def airlock(room, side, door_at=0, ox=None):
    """Тамбур шлюза снаружи стены. u — вдоль стены, v — наружу от её внешней грани.
    ox — своя внешняя грань северной и южной стен (каюта меньше комнат)."""
    ox, oy = ox or LX / 2 + LIN + T, LY / 2 + LIN + T     # внешние грани стен

    def place(name, su, sv, sz, u, v, z, mat):
        if side == "N":         # стена +X, наружу +X
            room.box(name, (sv, su, sz), (ox + v, door_at + u, z), mat)
        elif side == "S":       # стена −X, наружу −X
            room.box(name, (sv, su, sz), (-ox - v, door_at + u, z), mat)
        elif side == "W":       # стена −Y, наружу −Y
            room.box(name, (su, sv, sz), (door_at + u, -oy - v, z), mat)
        else:                   # "E": стена +Y, наружу +Y
            room.box(name, (su, sv, sz), (door_at + u, oy + v, z), mat)

    p = f"{side}_Airlock"
    # оси тамбура в осях комнаты: u — вдоль стены, v — наружу; base — середина проёма на внешней грани стены
    uvec = {"N": (0, 1), "S": (0, 1), "W": (1, 0), "E": (1, 0)}[side]
    vvec = {"N": (1, 0), "S": (-1, 0), "W": (0, -1), "E": (0, 1)}[side]
    base = {"N": (ox, door_at), "S": (-ox, door_at), "W": (door_at, -oy), "E": (door_at, oy)}[side]

    def at(u, v):
        return (base[0] + u * uvec[0] + v * vvec[0], base[1] + u * uvec[1] + v * vvec[1])

    def facing(f):              # колонки и табло смотрят лицом в +Y при yaw 0
        return math.degrees(math.atan2(-f[0], f[1]))

    # Отделка тамбура (автор, 15.11, вечер: «сейчас там дефолтные текстуры, как минимум нужен свет, желательно
    # вентиляцию»). Боковые стены — колонки набора с решётками вентиляции; у торцов щель на толщину створки:
    # внутренняя створка этой комнаты (и соседней — у торца напротив) уезжает вбок вдоль торца до боковой стены.
    # Над обоими проёмами перемычка, потолок — панели: две пары светильников по сторонам маячка, решётки у створок.
    # Тамбур симметричен по глубине (автор, 15.11: «тамбуры надо делать симметричными, тк при открытии двери видно
    # свап»): при смене комнат на его место встаёт тамбур соседней комнаты передом назад — ось вдоль стены та же,
    # глубина v зеркальная (v -> VD - v). Поэтому ряд колонок каждой стены — палиндром по середине тамбура, поручни
    # посередине, повороты панелей потолка одинаковы в зеркальных рядах. Ряд 56 + 75 + 17 + 75 + 56 = 279 см
    # между щелями створок (280).
    widths = {"Filler17": 17, "Filler53": 53, "Filler56": 56}
    for sgn, tag, mods in ((-1, "A", ("Filler56", "Vent", "Filler17", "Vent", "Filler56")),
                           (1, "B", ("Filler56", "Blank", "Filler17", "Blank", "Filler56"))):
        v = (VD - sum(widths.get(m, COL) for m in mods)) / 2
        for k, m in enumerate(mods):
            w = widths.get(m, COL)
            x, y = at(sgn * VW / 2, v + w / 2)
            room.mesh(f"{p}_Col{tag}{k + 1}", f"{WALL_COLUMNS}/SM_WallColumn{m}", (x, y, 0), facing((-sgn * uvec[0], -sgn * uvec[1])))
            v += w
    for v0, f, tag in ((0, vvec, "Inner"), (VD, (-vvec[0], -vvec[1]), "Outer")):
        x, y = at(0, v0)
        room.mesh(f"{p}_Header{tag}", f"{WALL_COLUMNS}/SM_WallColumnHeader", (x, y, 0), facing(f))
    lit = {(-75, 112.5): "Light", (75, 112.5): "Light", (-75, 187.5): "Light", (75, 187.5): "Light",
           (0, 37.5): "Vent", (0, 262.5): "Vent"}
    for i, u in enumerate((-150, -75, 0, 75, 150)):           # 5 × 75 = 375: края уходят в колонки (лица на ±180)
        for j, v in enumerate((37.5, 112.5, 187.5, 262.5)):
            k = lit.get((u, v), "")
            x, y = at(u, v)
            yaw = facing(uvec) + (0 if k else 90 * ((i * 3 + min(j, 3 - j)) % 4))   # ряды j и 3 − j одинаковы
            room.mesh(f"{p}_CeilingTile{k}_{i}{j}", TILES + k, (x, y, H), rot=(0, yaw, 180))
    # вертикальные поручни (Singula handrails) на лице средних вставок, посередине боковых стен, лицом внутрь
    for sgn, tag in ((-1, "A"), (1, "B")):
        inward = (-sgn * uvec[0], -sgn * uvec[1], 0)
        x, y = at(sgn * (VW / 2 - LIN), VD / 2)
        room.mesh(f"{p}_Handle{tag}", GRAB_HANDLE, (x, y, 120), rot=rot_from_axes(cross(UP, inward), UP, inward))
    place(f"{p}_Floor", VW + 2 * T, VD + T, 20, 0, (VD + T) / 2, -10, "Floor")
    place(f"{p}_Ceiling", VW + 2 * T, VD + T, 20, 0, (VD + T) / 2, H + 11, "Ceiling")   # на 1 см над панелями
    for sgn, tag in ((-1, "SideA"), (1, "SideB")):
        place(f"{p}_{tag}", T, VD, H, sgn * (VW / 2 + T / 2), VD / 2, H / 2, "Wall")
    seg = VW / 2 + T - DW / 2
    for sgn, tag in ((-1, "EndA"), (1, "EndB")):
        place(f"{p}_{tag}", seg, T, H, sgn * (DW / 2 + seg / 2), VD + T / 2, H / 2, "Wall")
    place(f"{p}_EndLintel", DW, T, H - DH, 0, VD + T / 2, DH + (H - DH) / 2, "Wall")
    # Створки стоят закрытыми. Внутреннюю двигает ARunRoom, внешняя не открывается никогда:
    # при переходе на её месте оказывается внутренняя створка соседней комнаты.
    place(f"{side}_DoorInner", DW, LEAF, DH, 0, LEAF / 2, DH / 2, "Door")
    place(f"{side}_DoorOuter", DW, LEAF, DH, 0, VD - LEAF / 2, DH / 2, "Door")
    mid = {"N": (ox + VD / 2, door_at), "S": (-ox - VD / 2, door_at),
           "W": (door_at, -oy - VD / 2), "E": (door_at, oy + VD / 2)}[side]
    room.light(f"{p}_Light", (mid[0], mid[1], H - 40), 1500, 650, (1.0, 0.88, 0.72))   # было 600, тускло-рыжий


def shell(room):
    ix, iy = LX / 2 + LIN, LY / 2 + LIN             # внутренние грани стен, за колонками
    room.box("Floor", (2 * (ix + T), 2 * (iy + T), 20), (0, 0, -10), "Floor")
    room.box("Ceiling", (2 * (ix + T), 2 * (iy + T), 20), (0, 0, H + 15), "Ceiling")   # над панелями (fixtures)
    wall_with_door(room, "Wall_N", "y", ix + T / 2, -(iy + T), iy + T, 0)
    wall_with_door(room, "Wall_S", "y", -(ix + T / 2), -(iy + T), iy + T, 0)
    wall_with_door(room, "Wall_W", "x", -(iy + T / 2), -ix, ix, 0)
    wall_with_door(room, "Wall_E", "x", iy + T / 2, -ix, ix, 0)
    for side in "NSWE":
        airlock(room, side)
    for i, x in enumerate((-250, 100, 330)):
        room.light(f"Room_Light{i + 1}", (x, 0, H - 30), 1800, 1200, (1.0, 0.96, 0.90))


# ---------- жилая комната: спальная капсула, шкафчики, кухонный уголок со столом, уборная ----------

def living():
    r = Room("Living")
    shell(r)
    # спальная капсула в юго-западном углу, спиной к южной стене — модель environment/living/sleep-capsule
    # (15.11, пока с однотонными зонами, import_sleep_capsule.py; до неё — девять серых коробок). Корпус 236 × 100 ×
    # 180 см, привязка — середина корпуса на полу, ступень выступает вперёд ещё на 20 см. Открытая сторона меша +Y
    # смотрит в комнату на север (yaw −90); изголовье при этом на востоке — подушка слева, как на картинке автора
    # (у коробок голова была к западной стене). Свет — под крышей капсулы (её низ на 169 см)
    px, py = -LX / 2 + 50, -225
    r.mesh("Sleep", "Living/SleepCapsule/SM_SleepCapsule", (px, py, 0), yaw=-90, foot=((100, 236.5, 180), (px, py, 90)))
    r.light("Sleep_Light", (px, py, 150), 250, 350, (0.45, 0.90, 0.95))
    # три шкафчика в юго-восточном углу, вдоль южной стены
    # модель environment/living/crew-locker (Tripo автора, 15.11, ночь; третья партия — до неё серые коробки):
    # 76 × 50 × 200 см, лицо меша +Y смотрит на север, в комнату
    for i in range(3):
        y = 150 + i * 80
        r.mesh(f"Locker{i + 1}", "Living/CrewLocker/SM_CrewLocker", (-LX / 2 + 25, y, 0), yaw=-90,
               foot=((50, 76, 200), (-LX / 2 + 25, y, 100)))
    # кухонный уголок у северной стены, в северо-западной четверти
    r.box("Galley_Counter", (60, 220, 90), (LX / 2 - 30, -230, 45), "Furniture")
    r.box("Galley_Top", (62, 222, 4), (LX / 2 - 30, -230, 92), "Dark")
    r.box("Galley_Cabinet", (35, 220, 60), (LX / 2 - 17.5, -230, 190), "Furniture")
    # стол и два табурета перед кухонным уголком
    # модели набора environment/common/dining-set (Tripo автора, 15.11; до них — серые коробки тех же размеров):
    # столешница на 78 см, привязка — центр дна; foot — прежний габарит коробки для раскладки колонок и потолка
    r.mesh("Table", "Common/DiningSet/SM_CrewTable", (250, -230, 0), foot=((120, 80, 78), (250, -230, 39)))
    r.mesh("Stool1", "Common/DiningSet/SM_Stool", (250, -300, 0), foot=((36, 36, 45), (250, -300, 22.5)))
    r.mesh("Stool2", "Common/DiningSet/SM_Stool", (250, -160, 0), yaw=90, foot=((36, 36, 45), (250, -160, 22.5)))
    r.mesh("Table_DrinkPouch", "Bridge/CrewItems/SM_DrinkPouch", (292, -212, 78), yaw=20)   # в стороне от мест предметов
    # уборная: кабинка 1,6 × 1,6 м в северо-восточном углу, дверь смотрит на юг
    x0, y0, w = 285, 210, 8                     # южная и западная грани кабинки, толщина перегородки
    x1, y1 = LX / 2, LY / 2                     # северная и восточная стены комнаты
    r.box("Lavatory_WallW", (x1 - x0, w, H), ((x0 + x1) / 2, y0 + w / 2, H / 2), "Wall")
    g0, g1, gh = 250, 330, 210                  # проём двери по Y и его высота
    r.box("Lavatory_WallS_A", (w, g0 - (y0 + w), H), (x0 + w / 2, (y0 + w + g0) / 2, H / 2), "Wall")
    r.box("Lavatory_WallS_B", (w, y1 - g1, H), (x0 + w / 2, (g1 + y1) / 2, H / 2), "Wall")
    r.box("Lavatory_Lintel", (w, g1 - g0, H - gh), (x0 + w / 2, (g0 + g1) / 2, gh + (H - gh) / 2), "Wall")
    # дверь приоткрыта наружу на 75°, петля у восточного края проёма
    ang = math.radians(75)
    leaf = g1 - g0 - 2
    r.box("Lavatory_Door", (4, leaf, gh - 2),
          (x0 + 2 - math.sin(ang) * leaf / 2, g1 - math.cos(ang) * leaf / 2, (gh - 2) / 2), "Furniture", yaw=-75)
    # унитаз с бачком и поручнями — модель environment/living/space-toilet (71 × 73 × 75 см): бачком к северной
    # стене, лицом на юг, к двери кабинки (лицо меша +Y -> −X)
    r.mesh("Lavatory_Toilet", "Living/SpaceToilet/SM_SpaceToilet", (x1 - 36.5, 300, 0), yaw=90,
           foot=((73, 68, 75), (x1 - 36.5, 300, 37.5), False))
    r.box("Lavatory_SinkStand", (16, 16, 80), (330, y1 - 12, 40), "Furniture")
    r.box("Lavatory_Sink", (42, 32, 12), (330, y1 - 18, 86), "Linen")
    r.box("Lavatory_Mirror", (34, 3, 45), (330, y1 - 1.5, 145), "Dark")
    r.light("Lavatory_Light", ((x0 + x1) / 2, (y0 + y1) / 2, 255), 300, 320, (1.0, 0.96, 0.90))
    r.spots_for("ItemSpot", [(250, -205, 78), (250, -255, 78), (LX / 2 - 30, -170, 94), (LX / 2 - 30, -290, 94),
                             (px + 10, py, 61), (-250, 150, 0), (150, 150, 0), (-100, -250, 0)])
    r.spots_for("NoteSpot", [(215, -230, 78), (-330, 120, 0), (330, 150, 0)])
    return r


# ---------- рубка: только центральный пост — кресло на помосте и консоли навигаторов по кругу ----------
#
# Пометки автора на снимке 14.11: панель пилота перед креслом убрана; консоли кольца — консоли навигаторов
# с мониторами (карточки environment/bridge/navigator-console и bridge-dais). Помост собран в Blender по картинке
# автора (15.11), до моделей стояли серые коробки и цилиндр тех же размеров.

def bridge():
    r = Room("Bridge")
    shell(r)
    # помост (environment/bridge/bridge-dais, import_kit.py): 240 × 12 см, начало — центр дна; затёртый проход
    # к креслу смотрит в −X, то есть на юг, поэтому без поворота
    r.mesh("Post_Dais", "Bridge/BridgeDais/SM_BridgeDais", (0, 0, 0))
    # противоперегрузочное кресло (Singula acceleration-couch) в центре, лицом на север: лицо меша +Y -> +X
    r.mesh("Chair_Couch", "Bridge/AccelerationCouch/SM_AccelerationCouch", (0, 0, 12), yaw=-90)
    # кольцо консолей вокруг поста; на юге проход к креслу. Консоль — модель навигаторской (карточка
    # environment/bridge/navigator-console: 150 × 92 см, начало — середина дна, сторона оператора +Y, мониторы у
    # дальнего края слиты с ней). Оператор стоит внутри кольца, лицом наружу: +Y -> к центру, yaw = deg + 90.
    # Радиус: ближние к посту углы соседних консолей сходятся на 227 см (шаг 45°), на 232 между ними щель 4 см.
    # До 15.11 здесь стояли серые коробки с мониторами-коробками и парами органов Singula: у модели свои клавиши.
    # В выгоревшей рубке ARunRoom::ApplyBurn меняет консоль на SM_NavigatorConsole_Burned сам, по имени меша.
    radius, depth = 232, 92
    for i, deg in enumerate((0, 45, 90, 135, 225, 270, 315)):
        a = math.radians(deg)
        r.mesh(f"Ring_Console{i + 1}", "Bridge/NavigatorConsole/SM_NavigatorConsole",
               (radius * math.cos(a), radius * math.sin(a), 0), yaw=deg + 90)
    r.light("Post_Light", (0, 0, 200), 500, 500, (0.45, 0.90, 0.95))
    # предметы и записка — на коврике консоли, в 22 см от ближнего к посту края (как в вычислительном центре), стол 1,003 м
    spot = radius - depth / 2 + 22
    d = spot * math.sqrt(0.5)
    r.spots_for("ItemSpot", [(d, d, 100), (-d, d, 100), (d, -d, 100), (-d, -d, 100), (0, spot, 100),
                             (0, -spot, 100), (350, 300, 0), (-350, -300, 0)])
    r.spots_for("NoteSpot", [(spot, 0, 100), (-350, 300, 0), (350, -300, 0)])
    return r


# ---------- лаборатория: клетки сбежавших крыс, капсула с образцом, столы с приборами, вытяжной шкаф ----------

def lab():
    r = Room("Lab")
    shell(r)
    # стеллаж с клетками вдоль южной стены, юго-западная четверть; одна клетка распахнута
    # модель environment/lab/cage-rack (третья партия): корпус 240 × 60 × 190 см, привязка — середина корпуса;
    # распахнутая дверца верхней средней клетки выходит вперёд ещё на 18 см. Лицо +Y -> север
    r.mesh("Cages_Rack", "Lab/CageRack/SM_CageRack", (-LX / 2 + 30, -225, 0), yaw=-90,
           foot=((60, 240, 190), (-LX / 2 + 30, -225, 95)))
    # капсула с образцом в юго-восточной четверти и пульт к ней
    cx, cy = -270, 250
    r.cylinder("Specimen_Base", 75, 30, (cx, cy, 15), "Furniture")
    r.cylinder("Specimen_Tube", 60, 190, (cx, cy, 125), "Glow")
    r.cylinder("Specimen_Cap", 75, 24, (cx, cy, 232), "Furniture")
    r.box("Specimen_Panel", (30, 44, 100), (cx + 110, cy - 90, 50), "Furniture", yaw=35)
    r.box("Specimen_PanelTop", (26, 40, 4), (cx + 110, cy - 90, 102), "Dark", yaw=35)
    r.light("Specimen_Light", (cx, cy, 270), 400, 400, (0.45, 0.90, 0.95))
    # лабораторный стол у западной стены, северо-западная четверть
    r.box("BenchW", (240, 70, 90), (250, -LY / 2 + 35, 45), "Furniture")
    r.box("BenchW_Top", (244, 74, 4), (250, -LY / 2 + 35, 92), "Dark")
    r.box("BenchW_Microscope", (22, 22, 38), (190, -LY / 2 + 35, 113), "Linen")
    r.box("BenchW_Centrifuge", (44, 44, 30), (320, -LY / 2 + 38, 109), "Linen")
    for i in range(3):
        r.cylinder(f"BenchW_Flask{i + 1}", 6, 22, (236 + i * 16, -LY / 2 + 30, 105), "Glow")
    r.box("BenchW_Stool", (36, 36, 55), (250, -LY / 2 + 110, 27.5), "Furniture")
    # вытяжной шкаф у северной стены и стол-остров, северо-восточная четверть
    r.box("Hood_Body", (60, 200, 210), (LX / 2 - 30, 240, 105), "Furniture")
    r.box("Hood_Window", (4, 170, 80), (LX / 2 - 62, 240, 150), "Dark")
    r.box("Island", (80, 200, 90), (230, 240, 45), "Furniture")
    r.box("Island_Top", (84, 204, 4), (230, 240, 92), "Dark")
    r.box("Island_Monitor", (6, 50, 36), (230, 190, 114), "Dark")
    r.box("Island_Samples", (30, 60, 14), (230, 290, 101), "Linen")
    r.spots_for("ItemSpot", [(280, -LY / 2 + 35, 94), (150, -LY / 2 + 35, 94), (230, 240, 94), (200, 320, 94),
                             (-200, -100, 0), (-130, 130, 0), (120, -150, 0), (-150, 330, 0)])
    r.spots_for("NoteSpot", [(255, 150, 94), (165, -LY / 2 + 50, 94), (-330, 100, 0)])
    return r


# ---------- жизнеобеспечение: баки, очистители воздуха, гидропоника, трубы, баллоны ----------

def life_support():
    r = Room("LifeSupport")
    shell(r)
    # два больших бака у западной стены, северо-западная четверть
    # модель environment/common/storage-tank (третья партия): 2,5 м, поперечник 1,6 м с лапами; манометр на лице +Y
    # смотрит на восток, в комнату. Тот же меш с масштабом — баки охлаждения двигателя и охладители серверов
    for i, x in enumerate((180, 350)):
        r.mesh(f"Tank{i + 1}", STORAGE_TANK, (x, -LY / 2 + 85, 0), foot=((150, 150, 250), (x, -LY / 2 + 85, 125), False))
    # два очистителя воздуха у северной стены, северо-восточная четверть
    for i, y in enumerate((150, 290)):
        r.box(f"Scrubber{i + 1}", (80, 120, 220), (LX / 2 - 40, y, 110), "Furniture")
        r.box(f"Scrubber{i + 1}_Grille", (4, 100, 110), (LX / 2 - 82, y, 140), "Dark")
        r.cylinder(f"Scrubber{i + 1}_Duct", 22, 80, (LX / 2 - 40, y, 260), "Tank")
    # гидропонные стеллажи в юго-восточной четверти: вдоль южной и восточной стен
    def rack(tag, center, size, along):
        r.box(f"Hydro{tag}_Frame", size, (center[0], center[1], 100), "Furniture")
        for lvl in range(3):
            tray = (size[0] + 6, size[1] - 10, 8) if along == "y" else (size[0] - 10, size[1] + 6, 8)
            r.box(f"Hydro{tag}_Tray{lvl + 1}", tray, (center[0], center[1], 45 + lvl * 65), "Plant")
    rack("S", (-LX / 2 + 25, 230), (50, 240, 200), "y")
    rack("E", (-200, LY / 2 - 25), (200, 50, 200), "x")
    r.light("Hydro_Light", (-320, 260, 250), 500, 450, (0.85, 0.55, 0.95))
    # пульт и стойка кислородных баллонов в юго-западной четверти
    # пульт — модель environment/common/control-cabinet (третья партия): 180 × 72 см, стол на 1,0 м, экран над задним
    # краем; здесь уже — 130 см (масштаб 0,72 по ширине меша). Лицо +Y -> север. Вещи и записки лежат на передней
    # половине стола: задняя — под экраном
    r.mesh("Control", CONTROL_CABINET, (-LX / 2 + 36, -150, 0), yaw=-90, scale=(0.72, 1, 1),
           foot=((72, 130, 100), (-LX / 2 + 36, -150, 50)))
    for i in range(4):
        r.cylinder(f"Oxygen{i + 1}", 14, 120, (-LX / 2 + 24, -260 - i * 34, 60), "Linen")
    r.box("Oxygen_Rack", (36, 140, 10), (-LX / 2 + 24, -305, 95), "Dark")
    # трубы под потолком вдоль западной и восточной стен, на каждой по вентилю
    for sgn, tag in ((-1, "W"), (1, "E")):
        y = sgn * (LY / 2 - 18)
        r.cylinder(f"Pipe{tag}1", 10, LX, (0, y, 265), "Tank", rot=(90, 0, 0))
        r.cylinder(f"Pipe{tag}2", 7, LX, (0, y, 238), "Door", rot=(90, 0, 0))
        r.cylinder(f"Pipe{tag}_Valve", 16, 6, (-150, sgn * (LY / 2 - 34), 238), "Door", rot=(90, 90, 0))
    r.spots_for("ItemSpot", [(-LX / 2 + 50, -115, 100), (-LX / 2 + 50, -185, 100), (200, -170, 0), (300, 120, 0),
                             (-150, 150, 0), (-330, -300, 0), (120, -120, 0), (-250, 250, 0)])
    r.spots_for("NoteSpot", [(-LX / 2 + 50, -150, 100), (250, 200, 0), (-120, -200, 0)])
    return r


# ---------- двигательный отсек: ядро варп-двигателя, пилоны, пульты, баки охлаждения, щит питания ----------

def engine():
    r = Room("Engine")
    shell(r)
    # ядро в центре, от пола до потолка
    # модель environment/engine/warp-core (Tripo автора, 15.11): 3,0 м, основание 2,27 м (у серых цилиндров было 3,0),
    # колонна светится своей картой. Патрубки хомутов смотрят на пилоны: у меша они по осям, отсюда поворот на 45°.
    # foot — габарит прежнего основания: под ним потолок без светильников, как раньше
    r.mesh("Core", "Engine/WarpCore/SM_WarpCore", (0, 0, 0), yaw=45, foot=((300, 300, H), (0, 0, H / 2)))
    r.light("Core_Light", (140, 0, 150), 2500, 900, (0.35, 0.85, 1.0))
    r.light("Core_Light2", (-140, 0, 150), 2500, 900, (0.35, 0.85, 1.0))
    # четыре пилона по диагоналям и силовые шины от них к ядру
    # модель environment/engine/core-pylon (третья партия): колонна 45 × 48 × 300 см, привязка — её середина; шина
    # уходит на 1,56 м вдоль +X меша, поэтому меш повёрнут шиной к ядру, а пилон стоит в 2,5 м от оси (у коробок 2,15):
    # конец шины — в 94 см от оси, у колонны ядра
    for i, deg in enumerate((45, 135, 225, 315)):
        a = math.radians(deg)
        x, y = 250 * math.cos(a), 250 * math.sin(a)
        r.mesh(f"Pylon{i + 1}", "Engine/CorePylon/SM_CorePylon", (x, y, 0), yaw=deg + 180, foot=((48, 48, H), (x, y, H / 2), False))
    # два пульта у южной стены, по сторонам от двери
    # модель environment/common/control-cabinet (третья партия): 180 × 72 см, стол на 1,0 м, лицо +Y -> север
    for sgn, tag in ((-1, "W"), (1, "E")):
        r.mesh(f"Console{tag}", CONTROL_CABINET, (-LX / 2 + 36, sgn * 220, 0), yaw=-90,
               foot=((72, 180, 100), (-LX / 2 + 36, sgn * 220, 50)))
    # после ремонта на пультах остались сварочный пистолет (лежит на боку: толщина меша по Y -> вверх)
    # и ремкомплект обшивки; середина пультов свободна под записки
    r.mesh("ConsoleW_WeldingGun", "WeldingGun/SM_WeldingGun", (-LX / 2 + 50, -270, 100 + 2.1), rot=(0, 0, -90))
    r.mesh("ConsoleE_PatchKit", "Common/SafetyEquipment/SM_HullPatchKit", (-LX / 2 + 50, 280, 100), yaw=-75)
    # баки охлаждения в северных углах с трубами к потолку
    # бак — модель storage-tank с масштабом 0,73 (высота 1,83 м, поперечник 1,17 м), манометром к ядру;
    # до потолка добирает труба
    for sgn, tag in ((-1, "W"), (1, "E")):
        cx, cy = LX / 2 - 65, sgn * (LY / 2 - 65)
        r.mesh(f"Coolant{tag}", STORAGE_TANK, (cx, cy, 0), yaw=math.degrees(math.atan2(-cy, -cx)) - 90,
               scale=(0.73, 0.73, 0.73), foot=((110, 110, 220), (cx, cy, 110), False))
        r.cylinder(f"Coolant{tag}_Pipe", 12, 122, (cx, cy, 239), "Tank")
    # щит питания на западной стене: гнёзда под батареи и предохранители
    r.box("Power_Board", (150, 10, 150), (-230, -LY / 2 + 5, 130), "Dark")
    for i in range(3):
        r.cylinder(f"Power_Cell{i + 1}", 14, 40, (-275 + i * 45, -LY / 2 + 24, 150), "Glow", rot=(90, 90, 0))
    for i in range(4):
        r.box(f"Power_Fuse{i + 1}", (16, 8, 34), (-284 + i * 36, -LY / 2 + 13, 92), "Linen")
    # гироскоп навигации у восточной стены
    r.cylinder("Gyro_Stand", 30, 90, (-230, LY / 2 - 50, 45), "Furniture")
    r.cylinder("Gyro_Ring", 42, 8, (-230, LY / 2 - 50, 122), "Tank", rot=(90, 90, 0))
    r.cylinder("Gyro_Rotor", 22, 20, (-230, LY / 2 - 50, 122), "Door", rot=(90, 90, 0))
    r.spots_for("ItemSpot", [(300, 150, 0), (300, -150, 0), (-300, 120, 0), (-300, -120, 0)])
    r.spots_for("NoteSpot", [(-LX / 2 + 50, -220, 100), (-LX / 2 + 50, 220, 100)])
    return r


# ---------- медотсек: две койки с мониторами, диагностическая капсула, шкафы с лекарствами, смотровое кресло ----------

def medbay():
    r = Room("Medbay")
    shell(r)
    # две койки у западной стены, изголовьем к стене; северо-западная четверть
    for i, x in enumerate((150, 310)):
        y = -LY / 2 + 100
        # модель environment/medbay/medical-bed (третья партия): 94 × 200 см, матрас на 65 см, стойка с монитором
        # у изголовья до 1,5 м; изголовье меша в −Y — к западной стене
        r.mesh(f"Bed{i + 1}", "Medbay/MedicalBed/SM_MedicalBed", (x, y, 0), foot=((94, 200, 65), (x, y, 32.5)))
    # диагностическая капсула в северо-восточной четверти (Tripo автора, 15.11; до неё — коробки и цилиндр):
    # 230 × 148 × 116 см, труба вдоль длинной оси меша X, пульт на лице +Y у конца +X. Yaw 90: труба — вдоль Y
    # комнаты, пульт смотрит на юг, в комнату, у восточного конца. Капсула в 30 см от колонок северной стены:
    # щель в 76 см, как у коробок, была уже героя, а дверцы в ней выглядели бы доступными; так они глухие
    # (ближе REACH). Коллизия — UCX меша; капсула не столешница, на ней ничего не лежит
    sx, sy = LX / 2 - 30 - 74, 250
    r.mesh("Scanner", "Medbay/DiagnosticCapsule/SM_DiagnosticCapsule", (sx, sy, 0), yaw=90,
           foot=((148, 230, 116), (sx, sy, 58), False))
    r.light("Scanner_Light", (sx, sy, 240), 350, 400, (0.45, 0.90, 0.95))
    # шкафы с лекарствами и раковина вдоль южной стены, юго-восточная четверть
    for i in range(3):
        y = 130 + i * 84
        r.box(f"Cabinet{i + 1}", (40, 80, 200), (-LX / 2 + 20, y, 100), "Furniture")
        r.box(f"Cabinet{i + 1}_Glass", (4, 66, 90), (-LX / 2 + 42, y, 145), "Dark")
    r.box("Sink_Stand", (40, 60, 85), (-LX / 2 + 20, 345, 42.5), "Furniture")
    r.cylinder("Sink_Bowl", 20, 8, (-LX / 2 + 22, 345, 88), "Linen")
    # смотровое кресло под хирургической лампой и ширма, юго-западная четверть
    cx, cy = -250, -220
    r.box("Chair_Seat", (70, 60, 50), (cx, cy, 25), "Furniture")
    r.box("Chair_Back", (16, 60, 80), (cx - 40, cy, 80), "Furniture", yaw=0)
    r.box("Chair_Leg", (70, 56, 12), (cx + 65, cy, 44), "Furniture")
    # модели набора environment/medbay/medbay-kit (Tripo автора, 15.11; до них — серые коробки и цилиндры).
    # Лампа висит на потолке: привязка — верх крепления, оно над серединой кресла, где была штанга заглушки
    # (foot — её габарит: потолок над лампой собирается как раньше). Плафон на коленчатой штанге отведён от крепления
    # на 18 см к востоку и спускается до 2,0 м; свет — под ним. Коллизии у лампы нет.
    r.mesh("Lamp", "Medbay/MedbayKit/SM_SurgicalLamp", (cx, cy, H), foot=((10, 10, 60), (cx, cy, 265)))
    r.light("Lamp_Light", (cx, cy + 18, 185), 900, 300, (1.0, 0.98, 0.95))
    # ширма стоит зигзагом из трёх створок, в плане 106 × 101 см (плоская коробка была 6 × 170): отодвинута
    # от подножки кресла; коллизия — по створкам
    r.mesh("Screen", "Medbay/MedbayKit/SM_PrivacyScreen", (cx + 160, cy - 40, 0), foot=((106, 101, 170), (cx + 160, cy - 40, 85)))
    # столик на колёсах 53 × 51 × 85 см, верхняя полка на 68 см — на ней место предмета; он шире коробки-заглушки,
    # поэтому на 6 см дальше от западной стены: дверцы колонок за ним остаются доступны
    r.mesh("Tray", "Medbay/MedbayKit/SM_InstrumentTrolley", (cx - 20, cy - 84, 0), foot=((53, 51, 85), (cx - 20, cy - 84, 42.5)))
    # бак у южной стены, педалью в комнату (лицо меша +Y -> +X)
    r.mesh("Biohazard_Bin", "Medbay/MedbayKit/SM_BiohazardBin", (-LX / 2 + 18, -100, 0), yaw=-90,
           foot=((29, 29, 65), (-LX / 2 + 18, -100, 32.5)))
    # пульт капсулы скошен, на него не положить: третья вещь — на полу у его подножия, вторая записка — на первой
    # койке у подушки, как первая на второй (обе раньше лежали на коробке-пульте)
    r.spots_for("ItemSpot", [(150, -LY / 2 + 130, 65), (310, -LY / 2 + 130, 65), (sx - 115, sy + 74, 0), (cx - 20, cy - 84, 68),
                             (cx + 4, cy, 50), (150, 120, 0), (-150, 150, 0), (-330, -100, 0)])
    r.spots_for("NoteSpot", [(310, -LY / 2 + 70, 65), (150, -LY / 2 + 70, 65), (-200, 250, 0)])
    return r


# ---------- грузовой отсек: ящики, бочки, контейнер, стеллаж, кран-балка ----------

def cargo():
    r = Room("Cargo")
    shell(r)
    # штабель ящиков в северо-западной четверти
    # модели набора environment/cargo/cargo-crates (Tripo автора, 15.11; до них — серые коробки тех же размеров):
    # кубы 120, 100 и 80 см, привязка — центр дна; оранжевый пояс большого ящика — на самой модели.
    # Лицо с ручками и замками (+Y меша) смотрит на восток или, при yaw 90, на юг — к середине комнаты
    crates = "Cargo/CargoCrates/SM_"
    r.mesh("CrateA", crates + "CrateLarge", (340, -280, 0), foot=((120, 120, 120), (340, -280, 60)))
    r.mesh("CrateB", crates + "CrateLarge", (200, -300, 0), yaw=90, foot=((120, 120, 120), (200, -300, 60)))
    r.mesh("CrateC", crates + "CrateMedium", (330, -285, 120), foot=((100, 100, 100), (330, -285, 170)))
    r.mesh("CrateD", crates + "CrateSmall", (190, -160, 0), yaw=90, foot=((80, 80, 80), (190, -160, 40)))
    # бочки в северо-восточной четверти
    k = 0
    for bx in (300, 372):
        for by in (200, 272, 344):
            k += 1
            # бочка набора — оранжевая (серых через одну, как у цилиндров-заглушек, пока нет); повёрнуты вразнобой
            r.mesh(f"Barrel{k}", crates + "Barrel", (bx, by, 0), yaw=k * 47, foot=((64, 64, 90), (bx, by, 45), False))
    r.mesh("Barrel_Top", crates + "Barrel", (336, 236, 90), yaw=20, foot=((64, 64, 90), (336, 236, 135), False))
    # стеллаж с коробками вдоль южной стены, юго-восточная четверть
    # модель environment/cargo/cargo-shelf (третья партия): 260 × 60 × 230 см с шестью ящиками, лицо +Y -> север
    r.mesh("Shelf", "Cargo/CargoShelf/SM_CargoShelf", (-LX / 2 + 30, 240, 0), yaw=-90,
           foot=((60, 260, 230), (-LX / 2 + 30, 240, 115)))
    # длинный контейнер и тележка с ящиком, юго-западная четверть
    r.box("Container", (110, 240, 130), (-LX / 2 + 55, -230, 65), "Furniture")
    r.box("Container_Door", (4, 100, 110), (-LX / 2 + 112, -280, 60), "Dark")
    r.box("Container_Stripe", (112, 242, 14), (-LX / 2 + 55, -230, 118), "Door")
    r.box("Cart_Deck", (90, 60, 10), (-180, -200, 25), "Dark")
    r.box("Cart_Handle", (6, 60, 90), (-225, -200, 65), "Dark")
    r.box("Cart_Crate", (60, 50, 50), (-170, -200, 55), "Tank")
    # кран-балка под потолком с крюком
    r.box("Crane_Rail", (LX, 20, 16), (0, 180, 284), "Dark")
    r.box("Crane_Trolley", (50, 40, 24), (120, 180, 264), "Door")
    r.cylinder("Crane_Cable", 3, 60, (120, 180, 222), "Dark")
    r.box("Crane_Hook", (16, 16, 24), (120, 180, 182), "Dark")
    # разметка на полу у дверей
    for sgn, tag in ((-1, "W"), (1, "E")):
        r.box(f"Floor_Stripe{tag}", (160, 10, 1), (0, sgn * 300, 0.5), "Door")
    r.spots_for("ItemSpot", [(190, -160, 80), (-170, -200, 80), (-LX / 2 + 55, -200, 130), (200, -300, 120),
                             (150, 130, 0), (-150, 130, 0), (-200, -100, 0), (120, -130, 0)])
    r.spots_for("NoteSpot", [(340, -250, 120), (-LX / 2 + 55, -260, 130), (-250, 200, 0)])
    return r


# ---------- столовая: два стола с лавками, раздаточный автомат, камбуз, холодильник, бак с водой ----------

def mess():
    r = Room("Mess")
    shell(r)
    # два стола с лавками в северных четвертях
    for sgn, tag in ((-1, "W"), (1, "E")):
        y = sgn * 230
        # модели набора environment/common/dining-set (Tripo автора, 15.11; до них — серые коробки тех же размеров):
        # стол 200 × 80 см со столешницей на 78 см и лавки 200 × 30 × 45 см, привязка — центр дна
        r.mesh(f"Table{tag}", "Common/DiningSet/SM_MessTable", (250, y, 0), foot=((200, 80, 78), (250, y, 39)))
        for j, dy in enumerate((-62, 62)):
            r.mesh(f"Bench{tag}{j + 1}", "Common/DiningSet/SM_MessBench", (250, y + dy, 0),
                   foot=((200, 30, 45), (250, y + dy, 22.5)))
        r.box(f"Tray{tag}1", (40, 30, 3), (200, y, 79.5), "Linen")
        r.box(f"Tray{tag}2", (40, 30, 3), (300, y + 8, 79.5), "Linen")
        r.cylinder(f"Cup{tag}", 5, 10, (220, y + 22, 83), "Door")
        # пакет с питьём у края стола, в стороне от подносов и мест предметов
        r.mesh(f"Table{tag}_DrinkPouch", "Bridge/CrewItems/SM_DrinkPouch", (162 if sgn < 0 else 338, y - sgn * 18, 78),
               yaw=sgn * 15)
    # камбуз вдоль южной стены, юго-восточная четверть: стойка, плита, шкаф над ней
    r.box("Galley_Counter", (60, 260, 90), (-LX / 2 + 30, 240, 45), "Furniture")
    r.box("Galley_Top", (62, 262, 4), (-LX / 2 + 30, 240, 92), "Dark")
    r.box("Galley_Hob", (40, 60, 3), (-LX / 2 + 30, 190, 95.5), "Door")
    r.cylinder("Galley_Pot", 14, 18, (-LX / 2 + 30, 190, 106), "Tank")
    r.box("Galley_Cabinet", (35, 260, 60), (-LX / 2 + 17.5, 240, 190), "Furniture")
    # раздаточный автомат у восточной стены
    # модель environment/mess/food-dispenser (третья партия): 120 × 80 × 200 см, экран светится своей картой;
    # лицо +Y -> запад, в комнату
    r.mesh("Dispenser", "Mess/FoodDispenser/SM_FoodDispenser", (-230, LY / 2 - 40, 0), yaw=180,
           foot=((120, 80, 200), (-230, LY / 2 - 40, 100)))
    r.light("Dispenser_Light", (-230, LY / 2 - 125, 160), 200, 250, (0.45, 0.90, 0.95))
    # холодильник, бак с водой и утилизатор, юго-западная четверть
    r.box("Fridge", (70, 90, 200), (-LX / 2 + 35, -320, 100), "Tank")
    r.box("Fridge_Handle", (4, 6, 60), (-LX / 2 + 72, -285, 120), "Dark")
    r.cylinder("Water_Tank", 28, 110, (-LX / 2 + 32, -210, 55), "Glow")
    r.cylinder("Water_Cap", 30, 12, (-LX / 2 + 32, -210, 116), "Furniture")
    r.box("Recycler", (50, 50, 80), (-LX / 2 + 27, -130, 40), "Furniture")
    r.box("Recycler_Slot", (4, 30, 10), (-LX / 2 + 54, -130, 60), "Dark")
    r.box("Wall_Screen", (200, 6, 90), (-200, -LY / 2 + 3, 160), "Dark")
    r.spots_for("ItemSpot", [(250, -250, 78), (300, -215, 78), (250, 250, 78), (190, 215, 78),
                             (-LX / 2 + 30, 290, 94), (-LX / 2 + 30, 130, 94), (-150, -120, 0), (-150, 150, 0)])
    r.spots_for("NoteSpot", [(310, -235, 78), (220, 240, 78), (-LX / 2 + 30, 330, 94)])
    return r


# ---------- вычислительный центр: стойки серверов, охладители, пульт оператора, кабельные лотки ----------

def computer():
    r = Room("Computer")
    shell(r)
    # по две стойки в северных четвертях, одна за другой, лицом на юг, к середине комнаты, как стояли серые коробки
    # (у них светились полосы на южной грани) — модель environment/computer/server-rack (15.11, пока с однотонными
    # зонами, import_server_rack.py). Корпус 194 × 74 × 200 см, крышка 199 × 79, ящики с ручками выходят вперёд
    # до 41,2 см от середины; привязка — середина корпуса на полу. Лицо меша +Y -> −X: yaw 90
    k = 0
    for sgn in (-1, 1):
        for x in (190, 340):
            k += 1
            y = sgn * 250
            r.mesh(f"Rack{k}", "Computer/ServerRack/SM_ServerRack", (x, y, 0), yaw=90,
                   foot=((80.7, 199, 200), (x - 0.85, y, 100)))
    r.light("Racks_LightW", (265, -250, 150), 300, 350, (0.35, 0.85, 1.0))
    r.light("Racks_LightE", (265, 250, 150), 300, 350, (0.35, 0.85, 1.0))
    # охладители в юго-восточной четверти: два цилиндра с трубами к потолку
    # бак — модель storage-tank с масштабом 0,6 (высота 1,5 м, поперечник 96 см), манометром на север
    for i, y in enumerate((190, 310)):
        r.mesh(f"Cooler{i + 1}", STORAGE_TANK, (-LX / 2 + 60, y, 0), yaw=-90, scale=(0.6, 0.6, 0.6),
               foot=((90, 90, 200), (-LX / 2 + 60, y, 100), False))
        r.cylinder(f"Cooler{i + 1}_Pipe", 10, 152, (-LX / 2 + 60, y, 224), "Tank")
    r.box("Cooler_Panel", (30, 60, 110), (-250, LY / 2 - 30, 55), "Furniture")
    # пульт оператора у южной стены, юго-западная четверть: консоль навигатора (автор, 14.11: в выгоревшей комнате
    # она может сгореть, DESIGN.md §14). Спиной к колонкам, лицом на север: лицо меша +Y -> +X. Консоль на ногах
    # стоящего оператора, кресла нет. Стол на 1,003 м; предметы — на коврике в 22 см от ближнего края
    console_x = -LX / 2 + 46
    r.mesh("Console", "Bridge/NavigatorConsole/SM_NavigatorConsole", (console_x, -230, 0), yaw=-90,
           foot=((92, 150, 158), (console_x, -230, 79)))
    # ячейка с накопителями данных: стеллаж картриджей у западной стены
    r.box("Vault", (160, 40, 180), (-200, -LY / 2 + 20, 90), "Furniture")
    for row in range(3):
        for col in range(4):
            r.box(f"Vault_Slot{row}{col}", (30, 4, 40), (-257 + col * 38, -LY / 2 + 42, 45 + row * 50), "Glow" if (row + col) % 3 else "Dark")
    # кабельные лотки под потолком
    for sgn, tag in ((-1, "W"), (1, "E")):
        r.box(f"CableTray{tag}", (LX, 30, 8), (0, sgn * 250, 280), "Dark")
    r.spots_for("ItemSpot", [(console_x + 24, -270, 100), (console_x + 24, -190, 100), (-250, LY / 2 - 30, 110),
                             (265, -130, 0), (265, 130, 0), (-150, -150, 0), (-150, 130, 0), (120, 0, 0)])
    r.spots_for("NoteSpot", [(console_x + 24, -230, 100), (265, -150, 0), (-220, 220, 0)])
    return r


# ---------- каюта героя (решение автора 15.11, вечер) ----------
#
# Вне генератора: с неё начинается каждый забег, поведение — ARunCabin (Source/MegaJam/Run/RunCabin.*). Внутри до лица
# колонок 4,5 × 3,75 м, потолок 3 м, одна дверь — на север, на оси y = 0, за ней обычный тамбур: после кода двери на
# месте каюты встаёт рубка, её южный тамбур совпадает с этим. Дверь не посередине северной стены: слева от неё одна
# колонка (на ней кодовый замок), справа две. Спальная капсула у южной стены, шкафы и зеркало у западной, у восточной —
# открытые полки с вещами быта: модели тех же вещей, что встречаются в забеге, — они и объясняют, откуда эти вещи на
# корабле. Взять их нельзя: это меши блюпринта. Колонки и потолок расставлены здесь же, не lining() и fixtures():
# те рассчитаны на коробку комнаты 9 × 7,5 м.

CABIN_CLASS = "/Script/MegaJam.RunCabin"
CAB_X = 225                  # лица колонок северной и южной стен: x = ±CAB_X (RunCabinGeo::InnerFace)
CAB_W, CAB_E = -150, 225     # лица колонок западной и восточной стен
ITEMS = "/Game/Items"        # модели вещей забега (import_props.py)


def cabin():
    r = Room("Cabin")
    r.parent = CABIN_CLASS
    ix, iw, ie = CAB_X + LIN, CAB_W - LIN, CAB_E + LIN       # внутренние грани стен, за колонками
    ox, y0, y1 = ix + T, iw - T, ie + T                      # внешние грани: север (300), запад, восток
    cy, wy = (y0 + y1) / 2, y1 - y0
    r.box("Floor", (2 * ox, wy, 20), (0, cy, -10), "Floor")
    r.box("Ceiling", (2 * ox, wy, 20), (0, cy, H + 15), "Ceiling")
    wall_with_door(r, "Wall_N", "y", ix + T / 2, y0, y1, 0)
    r.box("Wall_S", (T, wy, H), (-(ix + T / 2), cy, H / 2), "Wall")
    r.box("Wall_W", (2 * ix, T, H), (0, iw - T / 2, H / 2), "Wall")
    r.box("Wall_E", (2 * ix, T, H), (0, ie + T / 2, H / 2), "Wall")
    airlock(r, "N", ox=ox)
    r.mesh("N_Airlock_Beacon", AIRLOCK_BEACON, (ox + VD / 2, 0, H), rot=UPSIDE_DOWN)

    def col(tag, module, x, y, yaw):
        r.mesh(f"Lining_{tag}", f"{WALL_COLUMNS}/SM_WallColumn{module}", (x, y, 0), yaw)

    # север (лицо колонок на юг, yaw 90): слева от двери колонка с замком, справа портал (за ним привод створки) и шкаф
    col("N_L1", "Blank", ix, -112.5, 90)
    col("N_R1", "Blank", ix, 112.5, 90)
    col("N_R2", "LockerTwoDoors", ix, 187.5, 90)
    r.mesh("Lining_N_Header", f"{WALL_COLUMNS}/SM_WallColumnHeader", (ix, 0, 0), 90)
    for sgn, tag in ((-1, "L"), (1, "R")):
        r.mesh(f"Lining_N_FloorMarker{tag}", FLOOR_MARKER, (CAB_X - 12, sgn * (DW / 2 - 12), 0), 90)
    # кодовый замок — клавиатура набора пульта (control-console-parts, клин 8,6 × 15,4 см) на лице колонки:
    # основание к колонке, клавиши в каюту, экран вверху
    r.mesh("Lock_Keypad", "Bridge/ControlConsoleParts/SM_Keypad", (CAB_X - 0.5, -112.5, 125),
           rot=rot_from_axes((0, -1, 0), UP, (-1, 0, 0)))
    # юг: капсула закрывает колонки — глухие панели
    for k, y in enumerate((-112.5, -37.5, 37.5, 112.5, 187.5)):
        col(f"S_{k + 1}", "Blank", -ix, y, -90)
    # запад (yaw 0): два шкафа для одежды, комоды, глухая панель с зеркалом
    for k, (x, module) in enumerate(((-187.5, "LockerTwoDoors"), (-112.5, "LockerTwoDoors"), (-37.5, "Drawers"),
                                     (37.5, "Blank"), (112.5, "Drawers"), (187.5, "Blank"))):
        col(f"W_{k + 1}", module, x, iw, 0)
    r.box("Mirror_Frame", (66, 1.5, 106), (37.5, CAB_W + 0.75, 150), "Furniture")
    r.box("Mirror", (60, 1.5, 100), (37.5, CAB_W + 1.5, 150), "Dark")
    # восток (yaw 180): три открытые полки с вещами, комод, шкафчик
    for k, (x, module) in enumerate(((-187.5, "Blank"), (-112.5, "Shelf"), (-37.5, "Shelf"), (37.5, "Shelf"),
                                     (112.5, "Drawers"), (187.5, "Locker"))):
        col(f"E_{k + 1}", module, x, ie, 180)
    # вещи быта на полу ниш полок (ниша 0,98–1,52 м, глубина 0,40 от лица колонки)
    shelf_y = CAB_E + 18
    for name, x, yaw in (("FamilyPhoto", -128, 200), ("RubberDuck", -95, 150), ("DogTag", -52, 170),
                         ("VoiceRecorder", -22, 190), ("RationTin", 22, 0), ("DuctTape", 52, 30)):
        r.meshes.append((f"Shelf_{name}", f"{ITEMS}/{name}/SM_{name}", (x, shelf_y, 98), (0, yaw, 0)))
    # спальная капсула у южной стены, открытой стороной на север, как в жилой комнате; свет под её крышей
    px, py = -CAB_X + 50, 37.5
    r.mesh("Sleep", "Living/SleepCapsule/SM_SleepCapsule", (px, py, 0), yaw=-90)
    r.light("Sleep_Light", (px, py, 150), 250, 350, (0.45, 0.90, 0.95))
    r.mesh("Stool", "Common/DiningSet/SM_Stool", (130, 170, 0), yaw=20)
    # свет каюты: тёплый, один источник на шве двух светящихся панелей
    r.light("Room_Light1", (0, CAB_W + TILE * 2.5, H - 30), 900, 800, (1.0, 0.90, 0.78))
    for i in range(6):
        for j in range(5):
            k = "Light" if (i, j) in ((2, 2), (3, 2)) else "Vent" if (i, j) == (0, 2) else ""
            yaw = 90 * ((i * 7 + j * 3) % 4) if not k else 0
            r.mesh(f"CeilingTile{k}_{i:02d}_{j:02d}", TILES + k,
                   (-CAB_X + TILE / 2 + TILE * i, CAB_W + TILE / 2 + TILE * j, H), rot=(0, yaw, 180))
    return r


ROOMS = {"Living": living, "Bridge": bridge, "Lab": lab, "LifeSupport": life_support, "Engine": engine,
         "Medbay": medbay, "Cargo": cargo, "Mess": mess, "Computer": computer, "Cabin": cabin}


# ---------- колонки-шкафы вдоль стен ----------
#
# Сетка (правила набора Singula, ADR-031): колонка 75 см, две колонки — проём двери. Над проёмом — перемычка
# (Header). От края проёма к углу колонки идут вплотную; на внутреннем углу оба ряда отступают от угла на 45 см,
# лица сходятся, щель за ними не видна. Комната до лица колонок 900 × 750, поэтому на короткой стене (N, S)
# с каждой стороны двери ровно 4 колонки, на длинной (W, E) — 5. Доборы и боковины здесь не нужны.
#
# Какая колонка где — не случайно, а по месту:
# 1. Портал двери: колонка с той стороны проёма, куда уезжает створка, — глухая панель (Blank, за ней привод);
#    с другой стороны — аварийный пост (Emergency): огнетушитель и маски у каждого выхода.
# 2. Остальные места — набор комнаты PROGRAM: что в ней хранят. Main — основной модуль, Side — второй,
#    Corner — у угла. Порядок от двери к углу — ORDER: на длинных стенах основной модуль по обе стороны второго.
# 3. Мебель ближе REACH к лицу колонки. До колонки дотянуться можно только через столешницу: коробку с верхом
#    на рабочей высоте WORK_TOP, стоит на полу и не глубже WORK_DEPTH от лица колонки (кухонная стойка, стол,
#    пульт, раковина). Модуль по набору остаётся, если ему столешница не мешает (глухая панель, ящики с 1 м,
#    полка); шкаф, стойка, пост и вентиляция (BELOW_COUNTER) меняются на полку — ниша 0,98–1,52 м как раз над
#    столешницей. Мелочь на столешнице (микроскоп, колбы, кастрюля) не в счёт.
#    За любой другой мебелью — кровать, капсула, шкаф, ящики груза, бак, экран на стене — к колонке не подойти:
#    глухая панель. Если мебель закрыла аварийный пост, он переходит на другую сторону той же двери.
# Раскладка зависит только от типа комнаты и мебели в ней — одна и та же в каждом забеге.

WALL_COLUMNS = "Common/WallColumns"
COL = 75                       # ширина колонки
REACH = 40                     # мебель ближе к лицу колонки закрывает дверцы
REACH_Z = (25, 200)            # высоты, на которых до дверец достаёт рука
WORK_TOP = (70, 110)           # рабочая высота столешницы
WORK_DEPTH = 75                # через столешницу глубже этого до колонки не дотянуться
ON_TOP = 140                   # вещь, которая стоит выше WORK_TOP[0] и не выше этого, — мелочь на столешнице
# модули, которым нужен свободный пол перед колонкой: дверцы, ниша стойки и карман поста — от цоколя,
# у вентиляции решётка внизу. За столешницей вместо них полка; глухая панель и ящики (с 1 м) остаются
BELOW_COUNTER = ("Locker", "LockerTwoDoors", "Rack", "Emergency", "Vent")
OVERHANG = 4                   # столешницы и лотки, которые выступают за лицо колонок не больше этого, — не ошибка

# Аварийный пост в нише колонки Emergency (ниша 1,11–1,95 м, задняя стенка в 23 см от спинки колонки) —
# раскладка из Singula (wall-columns/source/build_wall_columns.py): всё вынимается из ниши, ничто не мешает
# другому. Огнетушитель висит низко в кольце кронштейна, коробка с маской стоит с запасом под откидную крышку,
# аптечка — на дне ниши под ней, зажим фонаря — рядом с коробкой. Фонаря в зажиме нет: фонарь — предмет забега,
# второй, которого нельзя взять, сбивал бы с толку; пустой зажим говорит, что его уже забрали.
# Координаты — в осях колонки: x вдоль ряда, y от спинки к лицу, z от пола.
SAFETY = "Common/SafetyEquipment/SM_"
EMERGENCY_KIT = (
    ("ExtinguisherBracket", "FireExtinguisherBracket", (-17, 23, 131)),
    ("Extinguisher", "FireExtinguisher", (-17, 30.5, 116.7)),
    ("MaskBox", "OxygenMaskBox", (13, 23, 151.5)),
    ("FlashlightClip", "FlashlightClip", (28, 23, 155.5)),
    ("FirstAid", "FirstAidCase", (17.5, 29, 112)),
)
# Кнопка двери — на откосе проёма (боковине колонки портала) с той стороны, куда закрывается створка, как пост
# с пультом у двери Singula; лицом поперёк проёма, ближе к комнате, на высоте руки. Так она есть у каждой двери
# и мебель перед колонками её не закрывает.
DOOR_BUTTON = ("Common/DoorHatchControls/SM_DoorButton", LIN - 12, 120)
FLOOR_MARKER = "Common/Lamps/SM_FloorMarker"

PROGRAM = {   # (Main, Side, Corner)
    "Living": ("LockerTwoDoors", "Drawers", "Shelf"),     # шкафы для одежды, комоды, открытая полка
    "Bridge": ("Rack", "Drawers", "Vent"),                # стойки приборов, ящики для карт, вентиляция
    "Lab": ("Shelf", "Drawers", "LockerTwoDoors"),        # полки с образцами, ящики инструментов, шкафы
    "LifeSupport": ("Vent", "Blank", "Locker"),           # воздуховоды, сервисные панели, запасные фильтры
    "Engine": ("Vent", "Rack", "Blank"),                  # вентиляция, щиты управления, сервисные панели
    "Medbay": ("Drawers", "LockerTwoDoors", "Shelf"),     # ящики с лекарствами, шкафы, полки
    "Cargo": ("Locker", "LockerTwoDoors", "Shelf"),       # шкафы для груза и инструмента
    "Mess": ("Drawers", "Shelf", "Locker"),               # посуда, полки, кладовая
    "Computer": ("Rack", "Vent", "Blank"),                # стойки, охлаждение, сервисные панели
}
ORDER = {"NS": ("portal", "side", "main", "corner"), "WE": ("portal", "main", "side", "main", "corner")}
CODE = {"Blank": "B", "Emergency": "E", "Drawers": "D", "Locker": "L", "LockerTwoDoors": "T", "Shelf": "S",
        "Rack": "R", "Vent": "V"}


def wall_frame(side):
    """Стена в своих координатах: точка(u, d) -> (x, y), поворот колонки, длина от двери до внутренней грани
    поперечной стены, в какую сторону u уезжает створка двери (RunRoomGeo::Slide). u идёт вдоль стены вправо,
    если смотреть на неё из комнаты, d — от внутренней грани стены в комнату. Лицо колонки (+Y меша) — в комнату."""
    ix, iy = LX / 2 + LIN, LY / 2 + LIN
    if side == "N":
        return (lambda u, d: (ix - d, u)), 90, iy, 1        # створки N и S уезжают в +Y
    if side == "S":
        return (lambda u, d: (-ix + d, -u)), -90, iy, -1
    if side == "W":
        return (lambda u, d: (u, -iy + d)), 0, ix, 1        # створки W и E уезжают в +X
    return (lambda u, d: (-u, iy - d)), 180, ix, -1


def is_shell(name):
    return (name in ("Floor", "Ceiling") or name[:7] in ("Wall_N_", "Wall_S_", "Wall_W_", "Wall_E_")
            or "_Airlock_" in name or name.endswith(("_DoorInner", "_DoorOuter")))


def footprints(room):
    """Габариты мебели по осям: (имя, x0, x1, y0, y1, z0, z1, коробка ли)."""
    out = []
    for name, size, c, _mat, yaw in room.boxes:
        if is_shell(name):
            continue
        a = math.radians(yaw)
        ca, sa = abs(math.cos(a)), abs(math.sin(a))
        ex, ey = size[0] / 2 * ca + size[1] / 2 * sa, size[0] / 2 * sa + size[1] / 2 * ca
        out.append((name, c[0] - ex, c[0] + ex, c[1] - ey, c[1] + ey, c[2] - size[2] / 2, c[2] + size[2] / 2, True))
    for name, r, h, c, _mat, rot in room.cylinders:
        if rot[0] == 90:      # лежачий: вдоль X при yaw 0, вдоль Y при yaw 90
            ex, ey, ez = (h / 2, r, r) if rot[1] == 0 else (r, h / 2, r)
        else:
            ex, ey, ez = r, r, h / 2
        out.append((name, c[0] - ex, c[0] + ex, c[1] - ey, c[1] + ey, c[2] - ez, c[2] + ez, False))
    for name, size, c, *flat in room.feet:
        out.append((name, c[0] - size[0] / 2, c[0] + size[0] / 2, c[1] - size[1] / 2, c[1] + size[1] / 2,
                    c[2] - size[2] / 2, c[2] + size[2] / 2, not flat or flat[0]))
    return out


def zone_hits(feet, point, u0, u1, d0, d1, z0, z1, min_along=10.0):
    """Мебель в прямоугольнике стены u0..u1 × d0..d1 и по высоте z0..z1. На каждую — что это для колонки:
    on_top — мелочь на столешнице, surface — столешница, block — всё остальное."""
    (ax, ay), (bx, by) = point(u0, d0), point(u1, d1)
    x0, x1, y0, y1 = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
    u_is_x = point(1, 0)[0] != point(0, 0)[0]     # стены W и E идут вдоль X, N и S — вдоль Y
    (px, py), (qx, qy) = point(0, 0), point(0, 1)
    nx, ny = qx - px, qy - py                     # в комнату
    hits = []
    for name, fx0, fx1, fy0, fy1, fz0, fz1, is_box in feet:
        ox, oy = min(x1, fx1) - max(x0, fx0), min(y1, fy1) - max(y0, fy0)
        if ox <= 0 or oy <= 0 or min(z1, fz1) <= max(z0, fz0):
            continue
        # перекрытие вдоль стены; перегородка до потолка упирается в колонку, даже если она тонкая
        if (ox if u_is_x else oy) >= min_along or fz1 >= H - 50:
            depth = max((cx - px) * nx + (cy - py) * ny for cx in (fx0, fx1) for cy in (fy0, fy1)) - LIN
            if fz0 >= WORK_TOP[0] and fz1 <= ON_TOP:
                kind = "on_top"
            elif is_box and fz0 <= 10 and WORK_TOP[0] <= fz1 <= WORK_TOP[1] and depth <= WORK_DEPTH:   # стоит на полу
                kind = "surface"
            else:
                kind = "block"
            hits.append((name, kind))
    return hits


def lining(room):
    """Колонки и перемычки по правилам выше. Возвращает раскладку для печати: сторона -> строка слева направо."""
    main, side_mod, corner = PROGRAM[room.name]
    by_role = {"main": main, "side": side_mod, "corner": corner}
    feet = footprints(room)
    rows = {}
    for side in "NSWE":
        point, yaw, span, slide = wall_frame(side)
        order = ORDER["NS" if side in "NS" else "WE"]
        n = round((span - LIN - DW / 2) / COL)
        assert abs(DW / 2 + n * COL - (span - LIN)) < 0.01 and n == len(order), (side, n)
        # мебель не должна заходить в колонки
        for name, _kind in zone_hits(feet, point, -span, span, 0, LIN - OVERHANG, 0, H, min_along=1):
            print(f"  ВНИМАНИЕ {room.name}: {name} заходит в колонки стены {side}")
        slots = {}
        for sgn in (-1, 1):
            for k, role in enumerate(order):
                a, b = DW / 2 + k * COL, DW / 2 + (k + 1) * COL
                u0, u1 = (a, b) if sgn > 0 else (-b, -a)
                if role == "portal":
                    module = "Blank" if sgn == slide else "Emergency"
                else:
                    module = by_role[role]
                hits = [h for h in zone_hits(feet, point, u0, u1, LIN - 1, LIN + REACH, *REACH_Z) if h[1] != "on_top"]
                slots[(sgn, k)] = {"module": module, "hits": hits, "u": (u0 + u1) / 2}
        for sgn in (-1, 1):
            e, other = slots[(sgn, 0)], slots[(-sgn, 0)]
            if e["module"] == "Emergency" and e["hits"] and not other["hits"]:
                e["module"], other["module"] = "Blank", "Emergency"
        for (sgn, k), s in slots.items():
            if any(kind == "block" for _n, kind in s["hits"]):
                s["module"] = "Blank"
            elif s["hits"] and s["module"] in BELOW_COUNTER:
                s["module"] = "Shelf"         # за столешницей: дверцы от цоколя упёрлись бы в неё
            x, y = point(s["u"], 0)
            tag = f"Lining_{side}_{'L' if sgn < 0 else 'R'}{k + 1}"
            room.mesh(tag, f"{WALL_COLUMNS}/SM_WallColumn{s['module']}", (x, y, 0), yaw)
            if s["module"] == "Emergency":
                for part, asset, (lx, ly, lz) in EMERGENCY_KIT:
                    px, py = point(s["u"] + lx, ly)
                    room.mesh(f"{tag}_{part}", SAFETY + asset, (px, py, lz), yaw)
        # кнопка на откосе со стороны −slide, лицом к середине проёма (в +slide по u)
        asset, d, z = DOOR_BUTTON
        (ax, ay), (bx, by) = point(0, 0), point(slide, 0)
        px, py = point(-slide * DW / 2, d)
        room.mesh(f"Lining_{side}_DoorButton", asset, (px, py, z), math.degrees(math.atan2(by - ay, bx - ax)) - 90)
        # светящиеся маркеры пола по краям проёма, сразу перед лицом колонок: выход видно и в тёмной комнате
        for sgn, tag in ((-1, "L"), (1, "R")):
            px, py = point(sgn * (DW / 2 - 12), LIN + 12)
            room.mesh(f"Lining_{side}_FloorMarker{tag}", FLOOR_MARKER, (px, py, 0), yaw)
        x, y = point(0, 0)
        room.mesh(f"Lining_{side}_Header", f"{WALL_COLUMNS}/SM_WallColumnHeader", (x, y, 0), yaw)
        left = [slots[(-1, k)] for k in reversed(range(len(order)))]
        right = [slots[(1, k)] for k in range(len(order))]
        code = lambda s: CODE[s["module"]].lower() if s["hits"] else CODE[s["module"]]
        blocked = sorted({f"{n}{'' if kind == 'block' else ' (столешница)'}" for s in left + right for n, kind in s["hits"]})
        rows[side] = (" ".join(code(s) for s in left) + "  [ ]  " + " ".join(code(s) for s in right)
                      + (f"   за мебелью: {', '.join(blocked)}" if blocked else ""))
    return rows


# ---------- потолок: панели 75 × 75 и маячки шлюзов ----------
#
# Видимая часть потолка — между лицами колонок, LX × LY = 9 × 7,5 м: ровно 12 × 10 панелей (набор ceiling-tiles,
# tools/ue/import_ceiling_tiles.py). Шаг панелей — шаг колонок, швы потолка продолжают швы колонок. Панели
# смоделированы лицом вверх, на потолок ставятся перевёрнутыми: лицо на высоте H, панель уходит вверх на 5 см,
# коробка потолка комнаты лежит над ними (shell).
# Где у комнаты общий свет (Room_Light*), над источником две светящиеся панели поперёк оси комнаты (источник стоит
# на шве между ними); между ними на оси — пары решёток приточной вентиляции; два люка обслуживания — по зерну
# комнаты (crc32 имени), не рядом со светом, решётками и друг с другом. Где к потолку подходит мебель (кран-балка,
# лотки, перегородки), свет и решётки не ставим: там глухие панели. В тамбуре шлюза — проблесковый маячок
# у его оранжевого света (меш смоделирован основанием вниз, ставится перевёрнутым).

AIRLOCK_BEACON = "Common/Lamps/SM_BeaconLight"
TILE = 75
TILES = "Common/CeilingTiles/SM_CeilingTile"      # + "", Light, Vent, Hatch
VENTS = (-75, 215)                 # x пар решёток на оси, между источниками x = −250, 100, 330
UPSIDE_DOWN = (0, 0, 180)
CEILING_GAP = 25                   # мебель выше H − этого под местом светильника мешает ему
NX, NY = LX // TILE, LY // TILE    # 12 × 10


def tile_x(i):
    return -LX / 2 + TILE / 2 + TILE * i


def tile_y(j):
    return -LY / 2 + TILE / 2 + TILE * j


def fixtures(room):
    feet = footprints(room)

    def free(x, y, r):
        return not [n for n, x0, x1, y0, y1, _z0, z1, _b in feet
                    if z1 > H - CEILING_GAP and x0 < x + r and x1 > x - r and y0 < y + r and y1 > y - r]

    def column(x):
        return min(NX - 1, max(0, math.floor((x + LX / 2) / TILE)))

    axis = (NY // 2 - 1, NY // 2)          # два ряда панелей у оси комнаты y = 0
    kind = {}
    for k, (name, (x, y, z), *rest) in enumerate(room.lights):
        if name.startswith("Room_Light"):
            i = column(x)
            if free(tile_x(i), 0, TILE):
                kind.update({(i, j): "Light" for j in axis})
            room.lights[k] = (name, (tile_x(i), y, z), *rest)     # источник — на шве под парой панелей
        elif name.endswith("_Airlock_Light"):
            room.mesh(name.replace("_Light", "_Beacon"), AIRLOCK_BEACON, (x, y, H), rot=UPSIDE_DOWN)
    for x in VENTS:
        i = column(x)
        if free(tile_x(i), 0, TILE) and (i, axis[0]) not in kind:
            kind.update({(i, j): "Vent" for j in axis})
    taken = set(kind)
    h = zlib.crc32(room.name.encode())
    for n in range(2):
        near = {(i + di, j + dj) for i, j in taken for di in (-1, 0, 1) for dj in (-1, 0, 1)}
        spots = [(i, j) for i in range(NX) for j in range(NY) if (i, j) not in near and free(tile_x(i), tile_y(j), TILE / 2)]
        if spots:
            spot = spots[(h >> (8 * n)) % len(spots)]
            kind[spot] = "Hatch"
            taken.add(spot)
    for i in range(NX):
        for j in range(NY):
            k = kind.get((i, j), "")
            # глухие панели и люки повёрнуты по зерну на четверть оборота: одинаковые соседи не совпадают
            yaw = 90 * ((h >> ((i * NY + j) % 31)) & 3) if k in ("", "Hatch") else 0
            room.mesh(f"CeilingTile{k}_{i:02d}_{j:02d}", TILES + k, (tile_x(i), tile_y(j), H), rot=(0, yaw, 180))


# ---------- сборка в редакторе ----------

def call(toolset, name, args):
    res = tool(toolset, name, args)
    if "ERROR" in res[:12]:
        raise RuntimeError(f"{name}: {res[:400]}")
    return json.loads(res).get("returnValue") if res.strip() else None


def ensure_not_playing():
    """В режиме Play инструменты ассетов не работают, а отвечают без ошибки (exists — «нет»). Тогда сборка
    просит создать уже существующий MI_Gray_*, и редактор встаёт на модальном окне «заменить?» (14.11)."""
    res = tool("EditorToolset.EditorAppToolset", "IsPIERunning", {})
    try:
        playing = json.loads(res).get("returnValue")
    except ValueError:
        playing = None
    if playing is not False:
        sys.exit(f"Редактор в режиме Play (или не ответил: {res[:120]!r}). Остановите игру и запустите сборку снова.")


def ensure_materials():
    call(AS, "create_folder", {"path": f"{ROOT}/Materials"})
    parent = {"refPath": "/Game/LevelPrototyping/Materials/M_PrototypeGrid.M_PrototypeGrid"}
    out = {}
    for name, (r, g, b) in MATERIALS.items():
        path = f"{ROOT}/Materials/MI_Gray_{name}"
        ref = {"refPath": f"{path}.MI_Gray_{name}"}
        if not call(AS, "exists", {"path": path}):
            call(MI, "create", {"folder_path": f"{ROOT}/Materials", "asset_name": f"MI_Gray_{name}", "parent": parent})
        for param, k in (("SurfaceColor", 1.0), ("TopSurfaceColor", 1.0), ("GridColor", 0.75), ("SubGridColor", 0.9)):
            call(MI, "set_vector_parameter", {"instance": ref, "name": param,
                                             "value": {"r": r * k, "g": g * k, "b": b * k, "a": 1.0}})
        call(AS, "save_assets", {"asset_paths": [path]})
        out[name] = ref
    # плитка пола (import_floor_tiles.py): пол комнат и тамбуров — она, если уже импортирована
    if call(AS, "exists", {"path": FLOOR_TILES}):
        out["Floor"] = {"refPath": f"{FLOOR_TILES}.{FLOOR_TILES.rsplit('/', 1)[1]}"}
    return out


def xform(center, yaw=0.0, rot=None):
    t = {"location": {"x": center[0], "y": center[1], "z": center[2]}}
    if rot and any(rot):
        t["rotation"] = {"pitch": rot[0], "yaw": rot[1], "roll": rot[2]}
    elif yaw:
        t["rotation"] = {"pitch": 0, "yaw": yaw, "roll": 0}
    return t


def build_blueprint(room, mats):
    bp_name = f"BP_Room_{room.name}"
    path = f"{ROOT}/Rooms/{bp_name}"
    call(AS, "create_folder", {"path": f"{ROOT}/Rooms"})
    if call(AS, "exists", {"path": path}):
        # убрать экземпляры с открытого уровня, иначе удаление блюпринта оставит битые ссылки
        for a in call(SC, "find_actors", {"name": bp_name, "tag": "", "collision_channels": []}) or []:
            call(SC, "remove_from_scene", {"actor": a})
        call(AS, "delete", {"path": path})
    bp = call(BP, "create", {"folder_path": f"{ROOT}/Rooms", "asset_name": bp_name, "asset_type": {"refPath": room.parent}})
    cdo = call(BP, "get_default_object", {"blueprint": bp})

    def paint(comp, mat):
        call(OB, "set_properties", {"instance": comp, "values": json.dumps({"OverrideMaterials": [mats[mat]]})})

    for name, size, center, mat, yaw in room.boxes:
        paint(call(PR, "add_cube", {"actor": cdo, "name": name, "dimensions": dict(zip("xyz", size)),
                                    "local_transform": xform(center, yaw)}), mat)
    for name, radius, height, center, mat, rot in room.cylinders:
        paint(call(PR, "add_cylinder", {"actor": cdo, "name": name, "radius": radius, "height": height,
                                        "local_transform": xform(center, rot=rot)}), mat)
    for name, pos, intensity, radius, (r, g, b) in room.lights:
        comp = call(AC, "add_component", {"owner": cdo, "component_type": {"refPath": "/Script/Engine.PointLightComponent"}, "name": name})
        call(OB, "set_properties", {"instance": comp, "values": json.dumps({
            "RelativeLocation": dict(zip("xyz", pos)),
            "Intensity": intensity, "AttenuationRadius": radius,
            "LightColor": {"r": int(r * 255), "g": int(g * 255), "b": int(b * 255), "a": 255},
        })})
    for name, pos in room.spots:
        comp = call(AC, "add_component", {"owner": cdo, "component_type": {"refPath": "/Script/Engine.SceneComponent"}, "name": name})
        call(OB, "set_properties", {"instance": comp, "values": json.dumps({"RelativeLocation": dict(zip("xyz", pos))})})
    for name, asset, center, (pitch, yaw, roll) in room.meshes:
        comp = call(AC, "add_component", {"owner": cdo, "component_type": {"refPath": "/Script/Engine.StaticMeshComponent"}, "name": name})
        values = {
            "StaticMesh": {"refPath": f"{asset}.{asset.rsplit('/', 1)[1]}"},
            "RelativeLocation": dict(zip("xyz", center)),
            "RelativeRotation": {"pitch": pitch, "yaw": yaw, "roll": roll},
        }
        if name in room.scales:
            values["RelativeScale3D"] = dict(zip("xyz", room.scales[name]))
        call(OB, "set_properties", {"instance": comp, "values": json.dumps(values)})
    call(BP, "compile_blueprint", {"blueprint": bp})
    call(AS, "save_assets", {"asset_paths": [path]})
    return path


def labels(name_part):
    out = []
    for a in call(SC, "find_actors", {"name": name_part, "tag": "", "collision_channels": []}) or []:
        out.append((call(AC, "get_label", {"actor": a}), a))
    return out


def ensure_level(level=None):
    """Уровень: создать из пустого шаблона движка, если его нет, и открыть."""
    level = level or LEVEL
    if not call(AS, "exists", {"path": level}):
        call(AS, "create_folder", {"path": f"{ROOT}/Maps"})
        call(AS, "duplicate", {"path": "/Engine/Maps/Templates/Template_Default", "new_path": level})
        call(AS, "save_assets", {"asset_paths": [level]})
    if call(SC, "get_current_level", {}) != level:
        call(SC, "load_level", {"level_path": level})
    for label, actor in labels("Floor"):
        if label == "Floor":   # пол шаблона: у комнат свой
            call(SC, "remove_from_scene", {"actor": actor})


def ensure_game_level():
    """Уровень игры: на нём только ведущий забега ARunDirector, комнаты он создаёт сам."""
    ensure_level(GAME_LEVEL)
    if not labels("RunDirector"):
        call(SC, "add_to_scene_from_class", {"actor_type": {"refPath": DIRECTOR_CLASS}, "name": "RunDirector",
                                             "xform": {"location": {"x": 0, "y": 0, "z": 0}}})
    for label, actor in labels("PlayerStart"):
        call(AC, "set_actor_transform", {"actor": actor, "worldspace": True, "xform": {
            "location": {"x": -330, "y": 0, "z": 100}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0}}})
    call(AS, "save_assets", {"asset_paths": [GAME_LEVEL]})


def place_rooms(built):
    for name, path in built.items():
        x, y, z = PLACES[name]
        call(SC, "add_to_scene_from_asset", {"asset_path": path, "name": f"BP_Room_{name}",
                                             "xform": {"location": {"x": x, "y": y, "z": z}}})
    for label, actor in labels("PlayerStart"):
        call(AC, "set_actor_transform", {"actor": actor, "worldspace": True, "xform": {
            "location": dict(zip("xyz", PLAYER_START)), "rotation": {"pitch": 0, "yaw": 0, "roll": 0}}})
    call(AS, "save_assets", {"asset_paths": [LEVEL]})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rooms = [ROOMS[n]() for n in (args or ROOMS)]
    for room in rooms:
        # у каюты колонки и потолок свои (cabin()): lining() и fixtures() рассчитаны на коробку комнаты
        rows = lining(room) if room.parent == ROOM_CLASS else {}
        if room.parent == ROOM_CLASS:
            fixtures(room)
        names = room.names()
        assert len(names) == len(set(names)), f"{room.name}: имена компонентов повторяются"
        print(f"{room.name}: {len(room.boxes)} коробок, {len(room.cylinders)} цилиндров, {len(room.lights)} источников света, "
              f"{len(room.meshes)} колонок и перемычек")
        for side, row in rows.items():
            print(f"  {side}: {row}")
    if "--dry" in sys.argv:
        return
    ensure_not_playing()
    # Редактор в фоне сам снижает себя до 3 кадров в секунду, а каждый вызов MCP занимает кадр: комната собиралась
    # 5 минут, все десять — 45 (16.11). Без этого ограничения — около минуты на комнату. В настройки не сохраняется
    call(OB, "set_properties", {"instance": {"refPath": "/Script/UnrealEd.Default__EditorPerformanceSettings"},
                                "values": json.dumps({"bThrottleCPUWhenNotForeground": False})})
    start_level = call(SC, "get_current_level", {})
    mats = ensure_materials()
    ensure_level()
    built = {room.name: build_blueprint(room, mats) for room in rooms}
    place_rooms(built)
    print("собрано и поставлено на уровень", LEVEL, "—", ", ".join(built.values()))
    ensure_game_level()
    print("уровень игры готов:", GAME_LEVEL)
    # вернуть уровень, открытый до сборки (обычно главное меню: с него Play показывает меню)
    if start_level and start_level != GAME_LEVEL:
        call(SC, "load_level", {"level_path": start_level})


if __name__ == "__main__":
    main()
