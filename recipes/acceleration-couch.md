# Противоперегрузочное кресло — `acceleration-couch`

Студия: `assets/environment/bridge/acceleration-couch/asset.yaml` · kind: prop · стадия сейчас: glb · в игре: `environment/bridge/acceleration-couch`

Кресло поста в рубке, откидывается к потолку-экрану. Где: рубка, все четыре комнаты.

Это ранняя модель. Сделано так:
- форма и развёртка — меш Tripo как есть, без пересборки;
- текстура — карты Tripo, поверх них в ArmorPaint доработана только подставка для ног.

Скрипт выгрузки есть. Скриптов масок подставки нет. Как они получены, восстановлено по самим картам: где сказано «по картинке» — это вывод.

## Результат

Один FBX и три текстуры 2048 × 2048 рядом с ним, PNG RGB, в FBX не вшиты:
- `SM_AccelerationCouch.fbx`;
- `T_AccelerationCouch_BaseColor.png` — цвет;
- `T_AccelerationCouch_ORM.png` — R окклюзия (везде 1), G шероховатость, B металл;
- `T_AccelerationCouch_Normal.png` — нормали, зелёный инвертирован (DirectX).

В Unreal — экземпляр `MI_AccelerationCouch` от `M_Kit` с этими тремя текстурами, переопределение Two Sided (`unreal.md`, «Импорт в Unreal»).

Поле `game` манифеста:
- `directory: environment/bridge/acceleration-couch`
- `model: [environment/bridge/acceleration-couch/source/tripo_convert_0ab65002-09d9-4d4f-b9a1-b28d9f9479b1.fbx]`
- `blend: environment/bridge/acceleration-couch/source/acceleration-couch.blend`
- `export: {blend: <тот же blend>, script: <способ выгрузки>}`
- `glb: [environment/bridge/acceleration-couch/SM_AccelerationCouch.fbx]` — поле Студии называется `glb`, в нём FBX;
- `textures` — три текстуры выше.

В `notes` оси — Blender и Unreal, без Godot: лицом к оператору −Y в Blender, +Y в Unreal.

Точка привязки — центр основания по габариту. Лицом к оператору: −Y в Blender, +Y в Unreal.

## Картинка

Шаблон `prop`, свои исключения: wheels, office chair. Картинки генерации в Студии нет — снимка нет, ниже собранный промт:

```text
3D render of a single game-ready prop with semi-realistic PBR materials for a first-person sci-fi game set aboard a bright NASA-punk spaceship. Alone, centered, filling most of the frame, on a plain seamless light-grey studio background with only a soft shadow under it.

A spacecraft acceleration couch for one person, shown upright: a contoured seat shell of satin painted metal with quilted off-white fabric padding on the seat, back and headrest, a five-point harness of graphite webbing straps meeting in a round brushed aluminium buckle, padded armrests, and a sturdy brushed aluminium pedestal with a recline hinge. An international orange pull handle under the seat and a small graphite foot rest.

Colors: off-white paint #ECEAE4, warm light-grey aluminium #B9BCC0, graphite rubber and plastic #2E3236, international orange accents and stripes #F26A21, muted teal screens and indicators #5FC6C9. No other colors.

View: three-quarter view from slightly above, the whole object fully visible.

Style: realistic proportions and materials: satin painted metal with light wear on the edges, brushed aluminium, matte rubber and plastic; subtle surface variation and a little dust in the crevices; soft physically based studio lighting.

Avoid: heavy rust, heavy grime, text, logos, table or visible floor, scenery, several objects, a base or plinth, cropped parts, glow, transparency, loose cables or cords, wheels, office chair.
```

## Модель

### Откуда форма

Картинка → Tripo → `source/tripo_convert_0ab65002-09d9-4d4f-b9a1-b28d9f9479b1.fbx`. Текстуры Tripo лежат в папке `.fbm` рядом:
- цвет `tripo_rgb_….jpg`;
- нормаль `tripo_normal_….jpg`;
- шероховатость `acceleration-couch_roughness.JPEG`;
- металл `acceleration-couch_metallic.JPEG`.

Меш взят как есть: топология, развёртка, швы Tripo. Детали не пересобирались.

### Масштаб

Tripo дал высоту 1 м и сиденье на 0,4 м — мало для взрослого. Модель увеличена в 1,2 раза:
- высота 1,2 м, ширина 0,67 м, глубина 0,89 м;
- сиденье на 0,48 м, подлокотники на 0,67 м.

Масштаб применён к мешу. У объекта масштаб 1, поворот 0, положение 0.

### Объект

Один объект `AccelerationCouch` в коллекции `AccelerationCouch`:
- 2688 вершин, 4664 треугольника;
- габарит 0,669 × 0,894 × 1,199 м: x от −0,334 до 0,334, y от −0,447 до 0,447, z от 0 до 1,199;
- начало координат — центр основания по габариту, на полу;
- оператор садится со стороны −Y.

Кресло цельное. Чтобы откидывать спинку в игре, её нужно отделить по шарниру в отдельный дочерний объект с началом координат на оси шарнира. Это не сделано.

### Шейдинг

- Нормали заданы (custom normals).
- Есть 448 рёбер, помеченных острыми, — примерно от 44°. Но среди гладких рёбер есть и более острые, так что правило пометки неизвестно: возможно, его ставили вручную или от нормалей Tripo.
- У меша Tripo 658 открытых рёбер: края ремней, тыльные стороны панелей. Поэтому материал двусторонний.

Если переделывать: острые рёбра ставить по углу около 40–45°, а остальные нормали взвешивать по площади граней — как сделано у `welding-gun`.

## Развёртка

Развёртка Tripo `UVMap` без изменений. Карты ArmorPaint ложатся на неё же.

Плотность проверена: медиана ≈ 1025 пикселей на метр на 2048, от 970 до 1060 у 80 % площади. Кресло видно вблизи, поэтому 2048, а не 1024.

## Маски

Маски есть только у подставки для ног. Это три карты 2048 в папке `.fbm`. Чем они сделаны — неизвестно, скрипта нет. Ниже — что в них по замеру.

Область подставки на развёртке (пиксели 2048, от левого верхнего угла): x 925–1978, y 76–1225. Это:
- две тёмные прямоугольные заплатки на атласе Tripo: верх и низ подставки;
- узкая полоса боковин сверху атласа.

**`acceleration-couch_footrest_a.png`:**
- **R — зона.** 1,0 — резиновая накладка (pad), 0,5 — металлический лоток (tray), 0 — всё остальное. Каждая зона около 93–96 тысяч пикселей.
- **G — кромки.** Тонкое кольцо по ободу накладки, на лотке — углы. Около 10 % площади зоны.
- **B — облачный шум «grunge»**, по всей зоне, среднее около 0,46–0,49, плавные пятна размером с ладонь.

**`acceleration-couch_footrest_b.png`:**
- **R — грязь (grime).** Широкая кайма по краю обеих зон. На лотке ещё горизонтальные полосы протирки. Около 24 % накладки и 68 % лотка.
- **G — потёртость (scuff).** Большие пятна посередине накладки, где стоят ноги, — около 62 % площади. На лотке мало.
- **B — тонкие царапины (scratch).** Прямые линии разных направлений, на лотке гуще.

**`acceleration-couch_footrest_n.png`** — нормаль подставки:
- на лотке — тонкие косые царапины и несколько вмятин;
- на накладке — неровный выступающий обод и мелкие линии.

Остальная развёртка плоская (0,5; 0,5; 1).

Если делать заново: эти маски проще запечь в Blender по мешу подставки, как в позднем конвейере наборов (`tools/blender/kit/`): кромки от выпуклых рёбер, шум в мировых координатах. Рисованные пятна потёртостей — по месту ступней.

Карты основного слоя тоже лежат в `.fbm`:
- **`acceleration-couch_basecolor.png`** — почти точная копия цвета Tripo, отличаются 0,05 % пикселей. У оранжевых полос на светлой краске убран тёплый оранжевый налёт: сделан серым.
- **`acceleration-couch_metallic.png`** — металл Tripo, но на острове подушки подлокотника и рядом с оранжевыми полосами металл снят (0,286 → 0,02, около 1,1 % пикселей). Tripo ошибочно сделал там металл.
- **`acceleration-couch_roughness.png`** — шероховатость Tripo без изменений.
- **`acceleration-couch_normal.png`** — нормаль Tripo без изменений.

## Слои ArmorPaint

Проект `source/acceleration-couch.arm`:
- меш — `source/acceleration-couch.fbx`, в масштабе Tripo (до увеличения в 1,2 раза): развёртка та же, масштаб на текстуру не влияет;
- ассеты — семь карт из `.fbm`.

Все слои — заливки 2048, 8 бит, смешивание Mix, непрозрачность слоя 1.

Маски подставки в шейдере сначала кодируются обратно в sRGB: ArmorPaint отдаёт картинки линеаризованными даже при Linear. Обратное кодирование: 1,055 × x^(1/2,4) − 0,055, не меньше 0. Пороги ниже — в единицах файла.

**Общее для слоёв подставки:**
- a — карта `footrest_a`, b — карта `footrest_b`, обе после обратного кодирования;
- pad = smoothstep от 0,7 до 0,85 по a.R;
- tray = smoothstep от 0,3 до 0,4 по a.R, умноженное на (1 − pad);
- edge = a.G, grunge = a.B, grime = b.R, scuff = b.G, scratch = b.B;
- окклюзия 1.

| # | Слой | Что красит | Цвет | Шероховатость | Металл | Непрозрачность |
|---|---|---|---|---|---|---|
| 1 | Couch | все каналы | картинка `basecolor` (sRGB) | `roughness` (Linear) | `metallic` (Linear) | 1, нормаль ← `normal` |
| 2 | Footrest dull | только шероховатость и непрозрачность | — | pad 0,85, tray 0,55 | — | smoothstep от 0,35 до 0,65 по grunge × (0,9·tray + 0,5·pad) |
| 3 | Footrest scuffs | цвет, шероховатость, металл | pad (0,43; 0,42; 0,395), tray (0,04; 0,04; 0,045) | pad 0,93, tray 0,6 | 0 | scuff × (pad + 0,9·tray) |
| 4 | Footrest edge wear | цвет, шероховатость, металл | pad (0,34; 0,345; 0,34), tray (0,86; 0,86; 0,88) | pad 0,97, tray 0,22 | tray | edge × (pad + tray) |
| 5 | Footrest scratches | цвет, шероховатость, металл | pad (0,44; 0,44; 0,43), tray (0,9; 0,9; 0,92) | pad 0,85, tray 0,2 | tray | scratch × (pad + 0,95·tray) |
| 6 | Footrest grime | цвет, шероховатость, металл | (0,12; 0,1; 0,075) × (0,8 + 0,4·grunge) | pad 0,92, tray 0,9 | 0 | grime × (0,8·pad + tray) |
| 7 | Footrest relief | только нормаль | — | — | — | smoothstep от 0,25 до 0,35 по a.R; нормаль ← `footrest_n` |

Цвета слоёв — значения шейдера: смесь pad и tray, где каждая зона взята со своим весом.

Смысл слоёв:
- **Dull** — матирует подставку пятнами.
- **Scuffs** — на резиновой накладке светлые серые затёртости от подошв, на лотке тёмные почти чёрные пятна.
- **Edge wear** — на накладке кромка темнеет и матовеет, на лотке кромки протёрты до блестящего металла.
- **Scratches** — светлые царапины, на лотке до металла.
- **Grime** — тёплая тёмная грязь по краям.
- **Relief** — рельеф накладки и царапины лотка.

Подставка в основе от Tripo тёмная: медиана цвета накладки ≈ 0,22 0,25 0,26, лотка ≈ 0,28 0,29 0,30.

Выгрузка ArmorPaint, 2048: `source/export/acceleration-couch_painted_basecolor.png`, `_roughness.png`, `_metallic.png`, `_normal.png`. Отдельной карты окклюзии нет.

## Доводка и выгрузка

Материал `AccelerationCouch` в Blender:
- painted basecolor (sRGB) → Base Color;
- roughness (Non-Color) → Roughness;
- metallic (Non-Color) → Metallic;
- normal (Non-Color) → Normal Map → Normal;
- двусторонний: Backface Culling выключен, render method Dithered;
- окклюзии нет.

Текстуры игры, 2048, без уменьшения:
- `T_AccelerationCouch_BaseColor.png` = выгруженный цвет, как данные.
- `T_AccelerationCouch_ORM.png`: R = 1, G = шероховатость, B = металл.
- `T_AccelerationCouch_Normal.png` = выгруженная нормаль. Каждый вектор (значение × 2 − 1) приведён к длине 1, зелёный инвертирован (G → 1 − G: Unreal ждёт DirectX), записан обратно × 0,5 + 0,5. Файл в `source/export/` остаётся OpenGL.

FBX — по `unreal.md`, «Выгрузка из Blender». Скрипт `source/export_acceleration_couch.py`, один объект `AccelerationCouch` → `SM_AccelerationCouch.fbx`, слот на время выгрузки — `MI_AccelerationCouch`. Свои отличия:
1. Объект и так в начале координат без поворота: начало FBX — центр основания.
2. Временно добавить Triangulate с сохранением заданных нормалей (`keep_custom_normals`). Одного `use_triangles` мало: в Blender 5.2 он сбивает заданные нормали (проверено обратным чтением FBX в Blender). После выгрузки модификатор убрать.
3. В `MI_AccelerationCouch` включить Two Sided (Details → Material Property Overrides).

## Проверка

- Высота 1,2 м, сиденье на 0,48 м, подлокотники на 0,67 м. Рядом с капсулой игрока 1,8 м кресло выглядит взрослым.
- Основание на полу, центр по габариту. В Unreal: Approx Size около 67 × 89 × 120 см, пивот в центре основания, сторона оператора в +Y.
- Подставка: накладка — серая затёртая резина, кромки лотка блестят металлом.
- На подлокотниках и у оранжевых полос нет металлического блеска.
- Сзади и у ремней нет дыр (Two Sided в `MI_AccelerationCouch`).

## Подводные камни

- **Tripo делает металлом то, что металлом не является:** подушки, краску у оранжевых полос. Карту металла проверять глазами и снимать лишнее.
- **Оранжевый налёт.** Tripo размывает оранжевый в соседнюю светлую краску. Убрать, перекрасить в цвет краски.
- **Окклюзии в ORM нет** (R = 1). Если кресло выглядит плоским в тени, запечь окклюзию в Blender и положить в R.
- **Спинка не откидывается**, пока её не отделили от сиденья. Отделённая спинка в Unreal — свой `SM_` и сборка `BP_AccelerationCouch` (`unreal.md`, «Подвижные детали»).
- **Без Triangulate с `keep_custom_normals`** FBX уходит со сбитыми нормалями: `use_triangles` заданные нормали не сохраняет.
- **Масштаб.** Проект ArmorPaint собран на меше до увеличения в 1,2 раза. Если шумы зависят от координат, а не от развёртки, размер пятен будет другим, чем в игре. У этих слоёв все маски по развёртке — не страшно.
