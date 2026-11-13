<script>
  import { downloadUrl, fileUrl, post, upload } from './api.js';
  import Field from './Field.svelte';
  import { fullPrompt } from './prompt.js';
  import { STAGE_LABEL, act, age, refresh, size, toast } from './studio.svelte.js';

  let { asset, config, downloads, onclose, onprev, onnext } = $props();

  let zoom = $state(null);
  let dragging = $state(false);
  let showFull = $state(false);

  const id = $derived(asset.id);
  const stepState = $derived(Object.fromEntries(asset.steps.map((s) => [s.key, s.state])));
  const isModel = $derived(asset.kind === 'model');
  const prompt = $derived(fullPrompt(config, asset));
  const styles = $derived(Object.entries(config.styles ?? {}));
  const styleTitle = (key) => config.styles?.[key]?.title ?? key;

  const save = (fields) => act(() => post('/asset/update', { id, fields }));
  const open = (target, path) => act(() => post('/open', { id, target, path }));
  const take = (name, as) => act(() => post('/asset/take', { id, name, as }), 'Забрал из Загрузок');
  const trash = (path) => act(() => post('/asset/trash', { id, path }), 'В Корзине');

  async function copy(text, done = 'Скопировано') {
    try {
      await navigator.clipboard.writeText(text);
      toast(done);
    } catch {
      toast('Браузер не дал скопировать', true);
    }
  }

  async function sendFiles(files) {
    for (const f of files) await act(() => upload(id, f), 'Файл добавлен');
  }

  function paste(e) {
    const files = [...(e.clipboardData?.files ?? [])];
    if (!files.length) return;
    e.preventDefault();
    sendFiles(files);
  }

  function drop(e) {
    e.preventDefault();
    dragging = false;
    sendFiles([...(e.dataTransfer?.files ?? [])]);
  }

  async function makeTexture(force = false) {
    try {
      const r = await post('/asset/texture', { id, force });
      toast(`Готово: ${r.name}`);
    } catch (e) {
      if (e.body?.needsForce) {
        if (confirm(`${e.message}. Перезаписать картинкой ${asset.image}?`)) return makeTexture(true);
      } else toast(e.message, true);
    } finally {
      await refresh();
    }
  }

  function key(e) {
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);
    if (e.key === 'Escape') {
      if (zoom) zoom = null;
      else if (!typing) onclose();
    }
    if (typing || zoom) return;
    if (e.key === 'ArrowLeft') onprev();
    if (e.key === 'ArrowRight') onnext();
  }
</script>

<svelte:window onkeydown={key} onpaste={paste} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="veil" onclick={onclose}></div>
<!-- svelte-ignore a11y_no_static_element_interactions -->
<aside
  class="panel"
  class:dragging
  ondragover={(e) => {
    e.preventDefault();
    dragging = true;
  }}
  ondragleave={() => (dragging = false)}
  ondrop={drop}
>
  <header>
    <div class="head-main">
      <Field single big value={asset.title} placeholder="Название" onsave={(v) => save({ title: v })} />
      <div class="meta">
        <code>{asset.id}</code>
        <span class="seg">
          <button class:on={isModel} onclick={() => save({ kind: 'model' })}>модель</button>
          <button class:on={!isModel} onclick={() => save({ kind: 'texture' })}>текстура</button>
        </span>
        {#if styles.length}
          <label class="style" title="Общий стиль промта. «По папке» — как задано в studio.yml">
            стиль
            <select value={asset.style && config.styles[asset.style] ? asset.style : ''} onchange={(e) => save({ style: e.target.value })}>
              <option value="">по папке: {styleTitle(asset.styleResolved)}</option>
              {#each styles as [key, st] (key)}
                <option value={key}>{st.title ?? key}</option>
              {/each}
            </select>
          </label>
        {/if}
        <label class="check"><input type="checkbox" checked={asset.later} onchange={(e) => save({ later: e.target.checked })} /> отложен</label>
      </div>
    </div>
    <div class="head-tools">
      <button onclick={() => open('folder')} title="Открыть папку ассета">Finder</button>
      <button onclick={onprev} title="Предыдущий (←)">‹</button>
      <button onclick={onnext} title="Следующий (→)">›</button>
      <button onclick={onclose} title="Закрыть (Esc)">✕</button>
    </div>
  </header>

  {#each asset.warnings as w}
    <p class="warning">⚠ {w}</p>
  {/each}

  <ol class="steps">
    <li class={stepState.idea}>
      <h3>{STAGE_LABEL.idea}</h3>
      <Field value={asset.idea} placeholder="Что это за предмет и зачем он в игре" onsave={(v) => save({ idea: v })} />
    </li>

    <li class={stepState.prompt}>
      <h3>
        {STAGE_LABEL.prompt}
        <span class="actions">
          <button class="primary" disabled={!asset.prompt.trim()} onclick={() => copy(prompt, 'Промт скопирован')}>Копировать промт</button>
        </span>
      </h3>
      <Field value={asset.prompt} placeholder="Описание предмета по-английски. Общий стиль допишется сам" onsave={(v) => save({ prompt: v })} />
      <div class="sub">Не рисовать — добавится к Avoid стиля, через запятую</div>
      <Field single value={asset.avoid} placeholder="light rays, lit glowing bulbs" onsave={(v) => save({ avoid: v })} />
      {#if asset.prompt.trim()}
        <div class="sub">
          <button class="link" onclick={() => (showFull = !showFull)}>{showFull ? 'Скрыть' : 'Показать'} полный промт со стилем «{styleTitle(asset.styleResolved)}»</button>
        </div>
        {#if showFull}<pre class="full">{prompt}</pre>{/if}
      {/if}
    </li>

    <li class={stepState.image}>
      <h3>
        {STAGE_LABEL.image}
        <span class="hint">⌘V — вставить из буфера, или перетащите файл в панель</span>
      </h3>
      {#if asset.images.length}
        <div class="grid">
          {#each asset.images as img (img.name)}
            {@const approved = img.name === asset.image}
            <figure class:approved>
              <button class="pic" onclick={() => (zoom = fileUrl(id, `images/${img.name}`, img.mtime))} title="Увеличить">
                <img src={fileUrl(id, `images/${img.name}`, img.mtime)} alt={img.name} loading="lazy" />
              </button>
              <figcaption>
                {#if approved}
                  <button class="ok" onclick={() => save({ image: '' })} title="Снять утверждение">✓ Утверждена</button>
                {:else}
                  <button class="primary" onclick={() => save({ image: img.name })}>Утвердить</button>
                {/if}
                <button class="quiet" onclick={() => trash(`images/${img.name}`)} title="В Корзину">🗑</button>
              </figcaption>
            </figure>
          {/each}
        </div>
      {:else}
        <p class="muted">Картинок пока нет. Скопируйте промт, сгенерируйте картинку и заберите её отсюда.</p>
      {/if}
      {#if downloads.images.length}
        <div class="inbox">
          <span class="inbox-title">Из Загрузок</span>
          <div class="grid small">
            {#each downloads.images as f (f.name)}
              <figure>
                <button class="pic" onclick={() => take(f.name, 'image')} title={`${f.name} · ${age(f.mtime)} — забрать`}>
                  <img src={downloadUrl(f.name, f.mtime)} alt={f.name} loading="lazy" />
                  <span class="take">Взять</span>
                </button>
                <figcaption class="muted">{age(f.mtime)}</figcaption>
              </figure>
            {/each}
          </div>
        </div>
      {/if}
    </li>

    {#if isModel}
      <li class={stepState.tripo}>
        <h3>
          {STAGE_LABEL.tripo}
          <span class="actions">
            {#if asset.image && stepState.image === 'done'}
              <button onclick={() => open('reveal', `images/${asset.image}`)} title="Показать утверждённую картинку в Finder, чтобы перетащить её в Tripo">
                Картинка в Finder
              </button>
            {/if}
            <a class="btn" href="https://www.tripo3d.ai/" target="_blank" rel="noreferrer">Tripo ↗</a>
          </span>
        </h3>
        {#each asset.tripo as f (f.name)}
          <div class="file">
            <span>{f.name}</span><span class="muted">{size(f.size)}</span>
            <button class="quiet" onclick={() => open('reveal', `source/tripo/${f.name}`)}>Finder</button>
            <button class="quiet" onclick={() => trash(`source/tripo/${f.name}`)} title="В Корзину">🗑</button>
          </div>
        {:else}
          <p class="muted">Меша пока нет. Сделайте его в Tripo по утверждённой картинке и скачайте.</p>
        {/each}
        {#if downloads.models.length}
          <div class="inbox">
            <span class="inbox-title">Из Загрузок</span>
            {#each downloads.models as f (f.name)}
              <div class="file">
                <span>{f.name}</span><span class="muted">{size(f.size)} · {age(f.mtime)}</span>
                <button class="primary" onclick={() => take(f.name, 'tripo')}>Взять</button>
              </div>
            {/each}
          </div>
        {/if}
      </li>

      <li class={stepState.blend}>
        <h3>{STAGE_LABEL.blend}</h3>
        {#each asset.blends as f (f.name)}
          <div class="file">
            <span>{f.name}</span><span class="muted">{size(f.size)} · {age(f.mtime)}</span>
            <button class="primary" onclick={() => open('blender', `source/${f.name}`)}>Открыть в Blender</button>
          </div>
        {:else}
          <p class="muted">
            Файла blend пока нет. Его собирает Claude.
            <button class="link" onclick={() => copy(`Собери модель ${id} в Blender`, 'Фраза для Claude скопирована')}>Скопировать просьбу</button>
          </p>
        {/each}
      </li>
    {/if}

    <li class={stepState.ready}>
      <h3>
        {STAGE_LABEL.ready}
        <span class="actions">
          {#if !isModel && asset.image && stepState.image === 'done'}
            <button class:primary={!asset.textures.length} onclick={() => makeTexture()}>
              {asset.textures.length ? 'Обновить из картинки' : 'Сделать текстурой'}
            </button>
          {/if}
          {#if asset.meshes.length || asset.textures.length}
            <button onclick={() => open('folder')}>Показать в Finder</button>
          {/if}
        </span>
      </h3>
      {#each [...asset.meshes, ...asset.textures] as f (f.name)}
        <div class="file"><span>{f.name}</span><span class="muted">{size(f.size)} · {age(f.mtime)}</span></div>
      {:else}
        <p class="muted">
          {#if isModel}
            Файлов для Unreal пока нет. FBX выгружает Claude.
            {#if asset.blends.length}
              <button class="link" onclick={() => copy(`Выгрузи ${id} в FBX`, 'Фраза для Claude скопирована')}>Скопировать просьбу</button>
            {/if}
          {:else}
            Текстуры пока нет. Утвердите картинку и нажмите «Сделать текстурой».
          {/if}
        </p>
      {/each}
      {#if asset.meshes.length || asset.textures.length}
        <p class="muted">Импорт в Unreal: <code>{asset.unreal}</code></p>
      {/if}
    </li>
  </ol>

  <section class="notes">
    <h3>Заметки</h3>
    <Field value={asset.notes} placeholder="Размеры, решения, что поправить" onsave={(v) => save({ notes: v })} />
  </section>

  {#if dragging}<div class="dropzone">Отпустите файл: картинка или меш</div>{/if}
</aside>

{#if zoom}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="zoom" onclick={() => (zoom = null)}><img src={zoom} alt="" /></div>
{/if}

<style>
  .veil {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 0.45);
    z-index: 10;
  }
  .panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(760px, 100vw);
    background: var(--panel);
    border-left: 1px solid var(--line);
    z-index: 11;
    overflow-y: auto;
    padding: 18px 22px 40px;
  }
  .panel.dragging {
    outline: 2px dashed var(--accent);
    outline-offset: -6px;
  }
  header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin-bottom: 14px;
  }
  .head-main {
    flex: 1;
    min-width: 0;
  }
  .head-tools {
    display: flex;
    gap: 6px;
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 6px;
    flex-wrap: wrap;
    color: var(--muted);
    font-size: 13px;
  }
  .style {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .style select {
    font: inherit;
    font-size: 13px;
    color: var(--text);
    background: var(--field);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 3px 6px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 5px;
    cursor: pointer;
  }
  .warning {
    background: color-mix(in srgb, var(--bad) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--bad) 50%, transparent);
    border-radius: 6px;
    padding: 7px 10px;
    margin: 0 0 8px;
  }
  .steps {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: step;
  }
  .steps li {
    counter-increment: step;
    position: relative;
    padding: 12px 12px 14px 44px;
    border-radius: 8px;
    border: 1px solid transparent;
  }
  .steps li + li {
    margin-top: 2px;
  }
  .steps li::before {
    content: counter(step);
    position: absolute;
    left: 10px;
    top: 11px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 12px;
    font-weight: 700;
    background: var(--field);
    color: var(--muted);
  }
  .steps li.done::before {
    content: '✓';
    background: var(--ok);
    color: #fff;
  }
  .steps li.skipped::before {
    content: '–';
  }
  .steps li.next {
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
    background: color-mix(in srgb, var(--accent) 7%, transparent);
  }
  .steps li.next::before {
    background: var(--accent);
    color: #1a1206;
  }
  h3 {
    margin: 0 0 8px;
    font-size: 14px;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 26px;
  }
  .actions {
    margin-left: auto;
    display: flex;
    gap: 6px;
  }
  .hint {
    margin-left: auto;
    font-weight: 400;
    font-size: 12px;
    color: var(--muted);
  }
  .muted {
    color: var(--muted);
    font-size: 13px;
    margin: 4px 0;
  }
  .sub {
    font-size: 12px;
    color: var(--muted);
    margin: 10px 0 4px;
  }
  .full {
    white-space: pre-wrap;
    border: 1px dashed var(--line);
    border-radius: 6px;
    padding: 8px 10px;
    font-family: inherit;
    font-size: 12px;
    color: var(--muted);
    margin: 0;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }
  .grid.small {
    grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  }
  figure {
    margin: 0;
    min-width: 0;
  }
  .pic {
    all: unset;
    cursor: pointer;
    display: block;
    position: relative;
    aspect-ratio: 1;
    width: 100%;
    border-radius: 6px;
    overflow: hidden;
    background: var(--field);
    outline: 2px solid transparent;
  }
  .approved .pic {
    outline-color: var(--ok);
  }
  .pic img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .take {
    position: absolute;
    inset: auto 0 0 0;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    padding: 3px;
    background: var(--accent);
    color: #1a1206;
    opacity: 0;
  }
  .pic:hover .take,
  .pic:focus-visible .take {
    opacity: 1;
  }
  figcaption {
    display: flex;
    gap: 6px;
    margin-top: 6px;
    align-items: center;
  }
  figcaption .primary,
  figcaption .ok {
    flex: 1;
  }
  .inbox {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px dashed var(--line);
  }
  .inbox-title {
    display: block;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 6px;
  }
  .file {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0;
    font-size: 13px;
  }
  .file span:first-child {
    font-family: var(--mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .file .muted {
    margin: 0 auto 0 0;
    white-space: nowrap;
  }
  .notes {
    margin-top: 16px;
    padding: 0 12px;
  }
  .dropzone {
    position: sticky;
    bottom: 0;
    margin-top: 12px;
    padding: 14px;
    text-align: center;
    border-radius: 8px;
    background: var(--accent);
    color: #1a1206;
    font-weight: 600;
    pointer-events: none;
  }
  .zoom {
    position: fixed;
    inset: 0;
    z-index: 20;
    background: rgb(0 0 0 / 0.85);
    display: grid;
    place-items: center;
    cursor: zoom-out;
  }
  .zoom img {
    max-width: 94vw;
    max-height: 94vh;
    border-radius: 6px;
  }
</style>
