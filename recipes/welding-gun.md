# Ручной сварочный пистолет — `welding-gun`

Студия: `assets/unprocessed/welding-gun/asset.yaml` · kind: prop · стадия сейчас: glb · в игре: `environment/welding-gun`

Ассет без обработки: ни места, ни назначения в игре не задано.

Происхождение (поле `origin`): случайная модель Tripo. Картинку сгенерировали без промта, когда делали «Сдвижную дверь». Ни картинки, ни промта в Студии нет.

Модель — меш Tripo с небольшой доводкой, карты — Tripo плюс запечённые в Blender нормаль и окклюзия.

Скрипт выгрузки есть, скриптов доводки и запекания нет. Доводка восстановлена по notes и сравнению мешей.

## Результат

Один FBX и три текстуры 1024 × 1024 рядом, PNG RGB, в FBX не вшиты:
- `SM_WeldingGun.fbx`;
- `T_WeldingGun_BaseColor.png` — цвет Tripo;
- `T_WeldingGun_ORM.png` — R запечённая окклюзия `welding-gun_ao`, G шероховатость Tripo, B металл Tripo;
- `T_WeldingGun_Normal.png` — перепечённые нормали, зелёный инвертирован (DirectX).

В Unreal — экземпляр `MI_WeldingGun` от `M_Kit` с этими тремя текстурами, переопределение Two Sided (`unreal.md`, «Импорт в Unreal»). Окклюзия материала (R карты ORM) в Unreal гасит только непрямой свет.

Поле `game` манифеста:
- `directory: environment/welding-gun`
- `model: [environment/welding-gun/source/tripo_convert_532ff009-975f-43e3-965b-bd576d6f1902.fbx]`
- `blend: environment/welding-gun/source/welding-gun.blend`
- `export: {blend: <тот же blend>, script: <способ выгрузки>}`
- `glb: [environment/welding-gun/SM_WeldingGun.fbx]` — поле Студии называется `glb`, в нём FBX;
- `textures` — три текстуры выше.

В `notes` — без Godot и glTF: ствол в −X Blender и Unreal; окклюзия в Blender не подключается, она в R `T_WeldingGun_ORM.png`; в игре `SM_WeldingGun.fbx` и три текстуры `T_WeldingGun_*` 1024; в Unreal окклюзия гасит только непрямой свет.

Точка привязки — центр основания по габариту. Ствол смотрит в −X и в Blender, и в Unreal: ось X у них общая. Бок с экраном: −Y в Blender, +Y в Unreal.

## Картинка

Шаблон `prop`. Описания у ассета нет, поэтому собранный промт — только рамка шаблона, без предмета:

```text
3D render of a single game-ready prop with semi-realistic PBR materials for a first-person sci-fi game set aboard a bright NASA-punk spaceship. Alone, centered, filling most of the frame, on a plain seamless light-grey studio background with only a soft shadow under it.

Colors: off-white paint #ECEAE4, warm light-grey aluminium #B9BCC0, graphite rubber and plastic #2E3236, international orange accents and stripes #F26A21, muted teal screens and indicators #5FC6C9. No other colors.

View: three-quarter view from slightly above, the whole object fully visible.

Style: realistic proportions and materials: satin painted metal with light wear on the edges, brushed aluminium, matte rubber and plastic; subtle surface variation and a little dust in the crevices; soft physically based studio lighting.

Avoid: heavy rust, heavy grime, text, logos, table or visible floor, scenery, several objects, a base or plinth, cropped parts, glow, transparency, loose cables or cords.
```

Чтобы получить такой же предмет заново, нужно описание. Вот предложение — оно восстановлено по старой модели, такого текста у ассета не было:

```text
A handheld welding gun: a boxy off-white painted metal body with a tall front block, a vertical international orange stripe on the front block, a small muted teal screen in a graphite frame with a small orange button below it on the side, a graphite carry handle on top with an orange inner edge, a pistol grip of graphite rubber with an orange base pad, an orange trigger, a small teal indicator and an orange button above the trigger guard.
```

Вид старой модели:
- **Корпус** — светлая краска, угловатый.
- **Передний блок** высокий, по нему вертикальная оранжевая полоса. Спереди круглые колпачки.
- **Сбоку** (−Y) бирюзовый экран в графитовой рамке, под ним оранжевая кнопка.
- **Сверху** графитовая ручка для переноски с оранжевой внутренней кромкой.
- **Сзади снизу** пистолетная рукоять из графитовой резины с оранжевой пяткой.
- **Над спусковой скобой** оранжевый спуск, оранжевая кнопка и бирюзовый индикатор.

## Модель

### Откуда форма

Tripo по картинке → `source/tripo_convert_532ff009-975f-43e3-965b-bd576d6f1902.fbx`:
- 1554 вершины, 2867 треугольников, высота 1 м;
- текстуры в папке `.fbm` рядом: `tripo_rgb_….jpg`, `tripo_normal_….jpg`, `gun_roughness.JPEG`, `gun_metallic.JPEG`, все 2048.

### Масштаб

Высота 0,2 м по выбору автора: меш Tripo × 0,2. Габарит 180 × 43 × 200 мм, рукоять около 8,5 см — под ладонь.

Начало координат — центр основания по габариту: x от −89,9 до 89,9, y от −21,4 до 21,4, z от 0 до 200 мм. Масштаб применён к мешу, у объекта масштаб 1, поворот и положение 0.

### Два объекта

**`WeldingGunTripo`** — меш Tripo с правками автора. Лежит в коллекции `Source`, она исключена из сцены, в игру не идёт. С него запекаются карты.

Правки — рамка экрана и рукоять. По сравнению с исходным FBX:
- добавлено 13 вершин и 25 треугольников, стало 1567 и 2892;
- 23 вершины сдвинуты больше чем на 1 мм, до 15,6 мм. Все на боковой стороне −Y, в области x от −58 до −11, z от 45 до 126 мм — это рамка экрана;
- правка рукояти по сравнению не видна: сдвиги там меньше 1 мм или ушли в добавленные вершины.

Что именно правили — записей нет.

**`WeldingGun`** — подготовленная модель, идёт в игру. Та же топология и та же развёртка, что у `WeldingGunTripo`, вершина в вершину. Подготовка по notes:
- **Почти плоские участки выровнены в плоскость** — изломы до 5°. Вершины сдвинуты не больше чем на 3 мм. По замеру сдвинуто 136 вершин, самое большее на 0,6 мм.
- **Кромки острее 40° помечены острыми** — 981 ребро.
- **Остальные нормали взвешены по площади граней** (как Weighted Normal, режим Face Area) и записаны как заданные нормали. Модификаторов в blend нет: всё применено.

Материал двусторонний, как у Tripo: у меша есть открытые края.

## Развёртка

Развёртка Tripo `UVMap` без изменений. Плотность около 2700 пикселей на метр на 1024: предмет маленький, вблизи в руках.

## Маски

Масок для слоёв нет. Запечены две карты 2048 в Blender, в `source/`.

**`welding-gun_normal.png`** — нормаль в касательном пространстве `WeldingGun`, перепечённая с `WeldingGunTripo`.

Источник — его материал с картой нормалей Tripo, то есть мелкий рельеф Tripo сохраняется. Сама геометрия тоже даёт вклад: выровненные грани и новые острые кромки `WeldingGun` против гладких нормалей Tripo.

Как пекли — не записано. Вероятно: Cycles, Bake → Normal, Selected to Active, `WeldingGunTripo` → `WeldingGun`. Меши совпадают, поэтому достаточно маленького выноса (Extrusion в несколько миллиметров).

**`welding-gun_ao.png`** — окклюзия по мешу `WeldingGun`:
- дальность 10 % высоты, то есть 0,02 м;
- серая, среднее 0,637.

Вероятно: Cycles, Bake → Ambient Occlusion, Distance 0,02.

## Слои ArmorPaint

Не было. Цвет, шероховатость и металл — карты Tripo без изменений.

## Доводка и выгрузка

Материал `WeldingGun`:
- `tripo_rgb` (sRGB) → Base Color;
- `gun_roughness` (Non-Color) → Roughness;
- `gun_metallic` (Non-Color) → Metallic;
- `welding-gun_normal` (Non-Color) → Normal Map → Normal;
- двусторонний (Backface Culling выключен).

`welding-gun_ao` в Blender никуда не подключается: она идёт в R карты ORM, в Unreal её читает `M_Kit`. В окне Blender окклюзия не видна.

Текстуры игры, 1024, из карт 2048 усреднением блоков 2 × 2, значения файла без управления цветом:
- `T_WeldingGun_BaseColor.png` = цвет Tripo.
- `T_WeldingGun_ORM.png`: R = окклюзия `welding-gun_ao`, G = шероховатость Tripo, B = металл Tripo.
- `T_WeldingGun_Normal.png` = перепечённая нормаль `welding-gun_normal`. После уменьшения каждый вектор (значение × 2 − 1) привести к длине 1, инвертировать зелёный (G → 1 − G: Unreal ждёт DirectX), записать обратно × 0,5 + 0,5. Сама `welding-gun_normal.png` остаётся OpenGL: по ней смотрит Blender.

FBX — по `unreal.md`, «Выгрузка из Blender». Скрипт `source/export_welding_gun.py`. Выгружается только `WeldingGun` → `SM_WeldingGun.fbx`; `WeldingGunTripo` из исключённой коллекции `Source` в FBX не идёт. Слот на время выгрузки — `MI_WeldingGun`. Свои отличия:
1. Объект и так в начале координат без поворота: начало FBX — центр основания.
2. Временно добавить Triangulate с сохранением заданных нормалей (`keep_custom_normals`) — иначе острые кромки потеряются. Одного `use_triangles` мало: в Blender 5.2 он сбивает заданные нормали (проверено обратным чтением FBX в Blender). После выгрузки модификатор убрать.
3. В `MI_WeldingGun` включить Two Sided (Details → Material Property Overrides).

## Проверка

- Высота 0,2 м, рукоять около 8,5 см — в руке капсулы игрока выглядит как инструмент, а не игрушка.
- В Unreal: Approx Size около 18 × 4,3 × 20 см, пивот в центре основания, ствол в −X, экран в +Y.
- Острые кромки чёткие, плоские грани без ряби.
- В щелях темнее, но не чёрные пятна.
- Экран бирюзовый, не светится: свечения нет.

## Подводные камни

- **Без Triangulate с `keep_custom_normals`** FBX уходит со сбитыми нормалями и сглаженными кромками: `use_triangles` заданные нормали не сохраняет.
- **Выравнивание плоскостей** — только малые изломы, до 5°, со сдвигом до 3 мм. Иначе развёртка и карты Tripo поползут.
- **Нормаль перепекать с исходного меша вместе с картой Tripo.** Если просто подать карту Tripo на новый шейдинг, рельеф ляжет криво: касательное пространство Tripo рассчитано на его гладкие нормали.
- **У Tripo открытые края** — материал двусторонний.
