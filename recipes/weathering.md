# Состаривание — `weathering`

Студия: `assets/environment/common/weathering/asset.yaml` · kind: texture (шаблон grayscale-map) · стадия сейчас: image · в игре: `environment/common/weathering`

Маска износа: царапины, потёртости и грязь для старения любых материалов. Белое — износ, чёрное — чистый материал.

Пока нигде не используется. В слое Scuffs набора `wall-columns` её заменила `fine-scratches`: группы царапин, потёртости и грязь не подошли.

## Результат

В игре — `environment/common/weathering/weathering.png`: бесшовная по обеим осям версия `approved/weathering-2.png`, 1024 × 1024, PNG RGB 8 бит.

Поле `game` манифеста:
- `directory: environment/common/weathering`
- `textures: [environment/common/weathering/weathering.png]`

Обложка в Студии — `approved/weathering-2.png`.

## Картинка

Шаблон `grayscale-map`, своё исключение: round spots or blotches. Утверждены две генерации с одним промтом — снимки `approved/weathering-1.txt` и `approved/weathering-2.txt`. Тексты одинаковые, собранный промт совпадает:

```text
Grayscale texture map for a semi-realistic PBR video game: a square swatch of a material seen straight from above, filling the whole frame edge to edge, in shades of grey only. One continuous image, not a grid of repeated copies.

Weathering mask for worn plastic and painted metal, a swatch about thirty centimetres across: white marks the wear on a black background — clusters of fine short scratches in random directions, small irregular scuffs and chipped specks, faint streaky smudges of grime. About a fifth of the frame is marked, spread evenly over the whole frame.

Style: a clean scanned material map at real-world scale: pure grey values with no color, no lighting, no shadows, no highlights or reflections; the same density and brightness over the whole frame with no vignette, so that it tiles calmly.

Avoid: color, a grid of repeated copies, perspective, side view, objects, text, logos, directional shadows, specular highlights, vignette, a frame around the image, a gradient across the image, one large feature in the middle, round spots or blotches.
```

Взята вторая генерация: `weathering-2`, 1024 × 1024, WebP с расширением `.png`. Первая — PNG 1024, в игру не пошла.

## Бесшовность

Метод — `pipeline/seamless-texture.md`, режим поверхности:
- окна нет — берётся вся картинка;
- скачок на краях снимается разложением на периодическую и гладкую части;
- размер 1024 — совпадает с исходным.

Результат — `weathering.png` в папке игры.

## Как применять

Маска слоя износа и грязи поверх материала, в ArmorPaint или Blender. Сколько износа — порогом и контрастом маски. Грязь — тёмная. Круглых пятен нет.

## Если делать заново

Сколы при ужатии до текселя читаются серыми точками. Если маска снова нужна, сплошные пятна шире 4 пикселей стоит убрать: перегенерацией или чисткой маски.

Для слоя царапин на краске модулей брать не её, а `fine-scratches`.

## Проверка

- Плитка 3 × 3 без шва.
- Около пятой части кадра помечено, равномерно.
- Нет круглых пятен.

## Подводные камни

- Утверждённая картинка — WebP с расширением `.png`. Blender читает её без проблем.
- Группы царапин и грязь этой маски на модулях выглядят пятнами. Для краски модулей она не подошла.
