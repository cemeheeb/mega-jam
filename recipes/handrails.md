# Поручни и ремни — `handrails`

Студия: `assets/environment/common/handrails/asset.yaml` · kind: kit · стадия сейчас: glb · в игре: `environment/common/handrails`

Поручни, петли и ремни для невесомости при развороте — на всех палубах. Оранжевые поручни — примета корабля (`assets/environment/ship.md`).

Это самый ранний набор, сделан до ArmorPaint. Модели собраны в Blender руками, меша Tripo нет. Текстура — одна картинка цвета, упакованная в blend.

Чем сделана текстура и как строились детали, кроме ручки, — записей нет. Это восстановлено по blend: где сказано «по виду» — вывод.

## Результат

Семь FBX в `environment/common/handrails/`:
- `SM_GrabHandle.fbx`, `SM_GrabHandleStandoff.fbx`;
- `SM_Handrail.fbx`, `SM_HandrailBracket.fbx`;
- `SM_FootLoop.fbx`, `SM_CamBuckle.fbx`, `SM_DRingAnchor.fbx`.

Рядом текстуры `T_Handrails_BaseColor.png` (1024 × 1024, цвет) и однотонная `T_Handrails_ORM.png` (4 × 4: AO 1, шероховатость 0,9, металл 0). Все семь мешей получают их через `MI_Handrails`, в FBX картинок нет.

У каждого FBX точка привязки — центр основания на монтажной поверхности, ось Z — от поверхности (в Blender и в Unreal одинаково). Материал двусторонний: в `MI_Handrails` включено Two Sided.

Поле `game` манифеста:
- `directory: environment/common/handrails`
- `model` нет — меша Tripo не было;
- `blend: environment/common/handrails/source/handrails.blend`
- `export: {blend: <тот же blend>, script: environment/common/handrails/source/export_handrails.py}`
- `glb` — семь FBX выше (поле Студии так называется);
- `textures: [environment/common/handrails/T_Handrails_BaseColor.png, environment/common/handrails/T_Handrails_ORM.png]`

Ручка ставится на две стойки, поручень — на кронштейны, в игре их расставляют отдельно.

## Картинка

Шаблон `kit`, своих исключений нет. Утверждённой картинки нет. В Студии лежит только кандидат `images/handrails-1.png` — WebP 1024 с расширением `.png`, без отметки. Снимка нет, ниже собранный промт:

```text
3D render of a set of game-ready props with semi-realistic PBR materials for a first-person sci-fi game set aboard a bright NASA-punk spaceship. Separate objects in a loose row on a plain seamless light-grey studio background, with clear empty space between them so that no two objects touch; each has only a soft shadow under it.

Five objects: a U-shaped grab handle of international orange painted metal on two round brushed aluminium standoffs; a straight orange handrail about one metre long on three aluminium wall brackets; a graphite matte rubber foot loop on an aluminium floor bracket; a graphite webbing strap with a brushed aluminium cam buckle; a small anchor plate with a swivelling aluminium D-ring.

Colors: off-white paint #ECEAE4, warm light-grey aluminium #B9BCC0, graphite rubber and plastic #2E3236, international orange accents and stripes #F26A21, muted teal screens and indicators #5FC6C9. No other colors.

View: three-quarter view from slightly above, all objects at the same scale and fully visible.

Style: realistic proportions and materials: satin painted metal with light wear on the edges, brushed aluminium, matte rubber and plastic; subtle surface variation and a little dust in the crevices; soft physically based studio lighting.

Avoid: heavy rust, heavy grime, text, logos, table or visible floor, scenery, objects touching or overlapping, stacked objects, a shared base or plinth, cropped parts, glow, transparency, loose cables or cords.
```

На кандидате:
- оранжевая П-образная ручка на двух круглых стойках;
- оранжевый поручень на трёх кронштейнах-хомутах;
- графитовая резиновая петля для ноги на алюминиевом основании;
- скрученный в рулон графитовый ремень с алюминиевой пряжкой-кулачком;
- маленькая пластина с откидным D-кольцом.

Модели повторяют кандидат. Рулон ремня не построен: от ремня — только короткий кусок в пряжке.

## Модель

### Общее

- Семь объектов в коллекции `Collection`, без родителей и детей. У всех масштаб 1, поворот 0.
- Начало координат — центр основания по габариту, на z = 0. Ось z смотрит от монтажной поверхности: от стены, пола или потолка.
- Размеры реальные, по руке.
- Шейдинг гладкий. Острые рёбра помечены примерно от 60° — на пряжке, кольце, петле и кронштейнах.
- Нормали заданы (custom normals). У ручки `GrabHandle` их нет: там острые только рёбра торцов.

Размеры ниже в миллиметрах, от начала объекта.

### Ручка `GrabHandle`

Габарит 42 × 523 × 95, 256 вершин, 508 треугольников. Оранжевая труба Ø 42.

Это единственная деталь со способом построения в blend. В коллекции `Source` (исключена из выгрузки) лежит путь `GrabHandlePath` — кривая POLY из 16 точек в плоскости x = 0:
- две ноги на y = ±240,7, от z 0 до 28,7;
- два изгиба на четверть круга радиусом 45,5 по осевой, по 6 отрезков на изгиб;
- верхняя прямая на z = 74,2, между y = ±195,2.

Профиль кривой — bevel глубиной 21 мм (труба Ø 42), разрешение 6 (16 граней по кругу), торцы закрыты (fill caps). Кривая переведена в меш: 16 точек × 16 граней = 256 вершин, торцы — веера треугольников.

Ноги ручки опускаются в стойки на 4 мм: в сцене ручка стоит на высоте 47,9 мм над стойкой высотой 51,8.

### Стойка ручки `GrabHandleStandoff`

Габарит Ø 83,5 × 51,8, 185 вершин, 344 треугольника. Круглая алюминиевая стойка — фланец и стакан под ногу ручки. У ручки их две, на расстоянии 481,4 мм между осями.

### Поручень `Handrail`

Труба Ø 38 × 990, оранжевая, вдоль y, торцы закрыты: 98 вершин, 16 граней по кругу. Начало координат — низ трубы посередине длины. Точкой привязки служит седло кронштейна.

### Кронштейн поручня `HandrailBracket`

Габарит 87 × 45 × 103, 146 вершин, 262 треугольника. Алюминиевый хомут на ножке с основанием. На поручень их три. В сцене труба проходит через хомут на высоте 86–125 мм.

### Петля для ноги `FootLoop`

Габарит 135 × 109 × 138, 242 вершины, 431 треугольник. Две части:
- алюминиевое основание 135 × 109 × 42;
- графитовая резиновая петля 125 × 42 × 130 — арка, стоит на основании с z 8.

### Пряжка `CamBuckle`

Габарит 64 × 79 × 44,5, 123 вершины, 224 треугольника. Четыре части:
- корпус 61 × 77 × 44;
- рычаг-кулачок 49 × 31 × 9;
- графитовый кусок ремня 43 × 11 × 11;
- ось 64 × 5 × 5 поперёк.

### Пластина с D-кольцом `DRingAnchor`

Габарит 70 × 152 × 84,5, 476 вершин, 908 треугольников. Пять частей:
- пластина 70 × 152 × 12;
- петля шарнира 35 × 64 × 25;
- ось шарнира 37 × 13 × 13;
- шайба 10 × 10 × 7;
- кольцо 67 × 13 × 74, стоит вертикально.

## Развёртка

Одна развёртка `UVMap` на все семь объектов, текстура 1024:
- **Трубы** `GrabHandle` и `Handrail` развёрнуты в одну оранжевую полосу у левого края, u от 0 до 0,168. Плотность там ниже — около 1160–1360 пикселей на метр.
- **Мелкие детали** — около 1450 пикселей на метр. Острова сложены в остальное поле, многие повторяющиеся детали и детали разных объектов делят одни острова: около 100 тысяч текселей 1024 (≈ 10 % атласа) общие у нескольких объектов.
- Острова занимают около 48 % атласа, чёрного поля в текстуре около 18 %.

## Маски

Масок нет: набор сделан до ArmorPaint.

## Слои ArmorPaint

Слоёв нет. Текстура `Handrails.BaseColor` 1024 упакована в blend и подана прямо в Base Color.

По виду:
- ровные цвета островов: оранжевый ≈ 0,749 0,275 0,098 (темнее `#F26A21`), светло-серый алюминий ≈ 0,757, графит ≈ 0,204;
- мягкие светлые и тёмные пятна внутри островов;
- на краях островов наплывы соседнего цвета;
- чёрные поля между островами.

Похоже на запекание цвета в Blender с другого, раскрашенного меша или проекцию картинки. Как именно — неизвестно.

Если переделывать: делать конвейером наборов (`tools/blender/kit/`, рецепты `door-hatch-controls`, `rack-equipment`). Зоны:
- оранжевая краска труб;
- алюминий стоек, кронштейнов, основания петли, пряжки и кольца;
- графитовая резина петли;
- графитовая ткань ремня.

Карты — base, orm, nor 1024.

## Доводка и выгрузка

Материал `Handrails` в Blender:
- картинка (sRGB) → Base Color;
- Roughness 0,9, Metallic 0, Specular IOR Level 1;
- без нормалей;
- двусторонний (Backface Culling выключен).

В Unreal — экземпляр `MI_Handrails` от `M_Kit` (`unreal.md`, «Импорт в Unreal»):
- `BaseColor` — `T_Handrails_BaseColor`, `ORM` — `T_Handrails_ORM`. `Normal` и `Emissive` не отмечать, остаются значения по умолчанию `M_Kit`;
- Material Property Overrides → Two Sided включить;
- Specular IOR Level 1 из Blender не переносится: у `M_Kit` нет входа Specular.

Выгрузка — по `unreal.md`, «Выгрузка из Blender», скрипт `source/export_handrails.py`. Отличия:
1. Текстуры. Цвет записать рядом с FBX как `T_Handrails_BaseColor.png` из упакованной в blend `Handrails.BaseColor`, как PNG 8 бит RGB (`unreal.md`). Карты ORM у набора нет, поэтому записать однотонную `T_Handrails_ORM.png` 4 × 4: (1; 0,9; 0). Нормалей и свечения нет.
2. Каждый меш коллекции `Collection` по имени — свой FBX. Имя файла — `SM_` и имя объекта: `GrabHandleStandoff` → `SM_GrabHandleStandoff.fbx`. На время выгрузки — в начало координат, слот получает временный материал `MI_Handrails`, последним в стек — модификатор Triangulate с `keep_custom_normals` = True. У набора заданные нормали (custom normals), флаг их сохраняет; опция FBX `use_triangles` остаётся False, она их сбивает (`unreal.md`, «Выгрузка из Blender», шаг 2). Потом убрать модификатор, вернуть положение и материал. Остальные настройки FBX — общие.

Путь ручки `GrabHandlePath` в игру не идёт.

## Проверка

- Поручень 0,99 м, ручка 0,52 м между внешними краями ног, труба ручки Ø 42 и поручня Ø 38 — под кисть.
- Под петлю для ноги проходит носок ботинка.
- В Unreal (`unreal.md`, «Первый импорт»): размеры в сантиметрах (поручень 99 см); пивот — центр основания; у всех семи слот `MI_Handrails` с `T_Handrails_BaseColor` и `T_Handrails_ORM`, Two Sided включено, металла нет; нормали как в Blender — острые рёбра пряжки, кольца, петли и кронштейнов острые, труба ручки гладкая.
- Ручка входит в стойку, стойки стоят на поверхности.

## Подводные камни

- **В промте пять объектов, в игре семь FBX.** Стойки ручки и кронштейны поручня — отдельные объекты, чтобы ставить их в нужном числе.
- **Рулона ремня нет.** Если ремень нужен, его надо сделать отдельно: лента по поверхности, без висящих концов.
- **Оранжевый темнее палитры** (≈ 0,749 0,275 0,098 против `#F26A21` ≈ 0,949 0,416 0,129). Если переделывать — брать цвет палитры.
- **Шероховатость 0,9 и металл 0 у всего**, включая алюминий. Металл выглядит как серая краска. В новом наборе алюминий — металл с шероховатостью около 0,3–0,4.
