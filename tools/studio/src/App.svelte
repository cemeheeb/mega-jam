<script>
  import { onMount } from 'svelte';
  import AssetPanel from './lib/AssetPanel.svelte';
  import Card from './lib/Card.svelte';
  import NewAsset from './lib/NewAsset.svelte';
  import PlayerBar from './lib/PlayerBar.svelte';
  import { mainTrack } from './lib/player.svelte.js';
  import { STAGES, refresh, studio } from './lib/studio.svelte.js';

  let stage = $state(null);
  let mine = $state(false);
  let prio = $state(0);
  // сортировка: по папкам (как лежат на диске) или по приоритету — очередь работы сверху вниз
  let byPrio = $state(localStorage.getItem('studio.byPrio') === '1');
  function toggleSort() {
    byPrio = !byPrio;
    localStorage.setItem('studio.byPrio', byPrio ? '1' : '0');
  }
  let query = $state('');
  let creating = $state(false);
  let openId = $state(readHash());

  function readHash() {
    return decodeURIComponent(location.hash.replace(/^#\/?/, '')) || null;
  }
  function go(id) {
    location.hash = id ? `#/${id}` : '';
    if (!id) history.replaceState(null, '', location.pathname);
    openId = id;
  }

  onMount(() => {
    refresh();
    const tick = setInterval(() => document.visibilityState === 'visible' && refresh(), 4000);
    const onfocus = () => refresh();
    const onhash = () => (openId = readHash());
    window.addEventListener('focus', onfocus);
    window.addEventListener('hashchange', onhash);
    return () => {
      clearInterval(tick);
      window.removeEventListener('focus', onfocus);
      window.removeEventListener('hashchange', onhash);
    };
  });

  const assets = $derived(studio.data?.assets ?? []);
  const isMine = (a) => a.next?.who === 'author' && !a.later;
  const counts = $derived(Object.fromEntries(STAGES.map((s) => [s.key, assets.filter((a) => a.stage === s.key).length])));
  const mineCount = $derived(assets.filter(isMine).length);

  const visible = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return assets.filter(
      (a) =>
        (!stage || a.stage === stage) &&
        (!mine || isMine(a)) &&
        (!prio || a.priority === prio) &&
        (!q || `${a.title} ${a.id} ${a.idea} ${a.prompt}`.toLowerCase().includes(q)),
    );
  });
  const groups = $derived.by(() => {
    const map = new Map();
    if (byPrio) {
      // сначала первый приоритет; внутри — несделанное выше отмеченного «сгенерирован» и отложенного
      const rest = (a) => Number(a.generated) + 2 * Number(a.later);
      for (const p of [1, 2, 3, 0]) {
        const list = visible.filter((a) => a.priority === p).sort((x, y) => rest(x) - rest(y) || x.id.localeCompare(y.id, 'en', { numeric: true }));
        if (list.length) map.set(p ? `Приоритет ${p}` : 'Без приоритета', list);
      }
      return [...map.entries()];
    }
    for (const a of visible) {
      if (!map.has(a.group)) map.set(a.group, []);
      map.get(a.group).push(a);
    }
    return [...map.entries()];
  });
  const allGroups = $derived([...new Set(assets.map((a) => a.group).filter(Boolean))]);
  const current = $derived(assets.find((a) => a.id === openId) ?? null);
  // ⏮ ⏭ у звука, запущенного с карточки, идут по звукам на экране в том же порядке
  const soundQueue = $derived(groups.flatMap(([, l]) => l).map(mainTrack).filter(Boolean));

  function step(d) {
    const shown = groups.flatMap(([, l]) => l);
    const list = shown.length ? shown : assets;
    const i = list.findIndex((a) => a.id === openId);
    if (list.length) go(list[(i + d + list.length) % list.length].id);
  }
</script>

<div class="top">
  <strong class="logo">Студия</strong>
  <nav class="pipe">
    {#each STAGES as s, i (s.key)}
      {#if i}<span class="arrow">›</span>{/if}
      <button class:on={stage === s.key} class:zero={!counts[s.key]} onclick={() => (stage = stage === s.key ? null : s.key)}>
        {s.label} <b>{counts[s.key]}</b>
      </button>
    {/each}
  </nav>
  <button class="toggle" class:on={mine} onclick={() => (mine = !mine)} title="Только то, что ждёт вас: сгенерировать, утвердить, сделать меш">
    Мой ход <b>{mineCount}</b>
  </button>
  {#each [1, 2, 3] as n (n)}
    <button class="toggle prio{n}" class:on={prio === n} onclick={() => (prio = prio === n ? 0 : n)} title="Только приоритет {n}">
      П{n} <b>{assets.filter((a) => a.priority === n).length}</b>
    </button>
  {/each}
  <button class="toggle sort" class:on={byPrio} onclick={toggleSort} title="Сортировка: по папкам или по приоритету">
    По приоритету
  </button>
  <input class="search" type="search" placeholder="Поиск" bind:value={query} />
  <button class="primary" onclick={() => (creating = true)}>+ Ассет</button>
</div>

{#if studio.error}<p class="banner">{studio.error}</p>{/if}
{#if studio.data?.config?.error}<p class="banner">{studio.data.config.error}</p>{/if}
{#if studio.data?.downloads?.error}<p class="banner soft">{studio.data.downloads.error}</p>{/if}

<main>
  {#if studio.data && !assets.length}
    <div class="blank">
      <p>Ассетов пока нет.</p>
      <p class="muted">Каждый ассет — папка с файлом <code>asset.yml</code> в <code>{studio.data.root}</code>.</p>
      <button class="primary" onclick={() => (creating = true)}>+ Ассет</button>
    </div>
  {:else if studio.data && !visible.length}
    <div class="blank"><p class="muted">Под фильтр ничего не подходит.</p></div>
  {/if}
  {#each groups as [group, list] (group)}
    <section>
      <h2>{group || 'без папки'} <span>{list.length}</span></h2>
      <div class="cards">
        {#each list as a (a.id)}
          <Card asset={a} onopen={go} queue={soundQueue} />
        {/each}
      </div>
    </section>
  {/each}
</main>

{#if current}
  {#key current.id}
    <AssetPanel
      asset={current}
      config={studio.data.config}
      downloads={studio.data.downloads}
      onclose={() => go(null)}
      onprev={() => step(-1)}
      onnext={() => step(1)}
    />
  {/key}
{/if}

{#if creating}
  <NewAsset
    groups={allGroups}
    onclose={() => (creating = false)}
    oncreated={(id) => {
      creating = false;
      go(id);
    }}
  />
{/if}

<PlayerBar onopen={go} />

{#if studio.toast}<div class="toast" class:bad={studio.toast.bad}>{studio.toast.text}</div>{/if}

<style>
  .top {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    background: color-mix(in srgb, var(--bg) 92%, transparent);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line);
    flex-wrap: wrap;
  }
  .logo {
    font-size: 15px;
  }
  .pipe {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }
  .arrow {
    color: var(--muted);
  }
  .pipe button,
  .toggle {
    background: transparent;
    border-color: transparent;
  }
  .pipe button.zero {
    color: var(--muted);
  }
  .pipe button.on,
  .toggle.on {
    background: var(--accent);
    color: #1a1206;
    border-color: var(--accent);
  }
  .toggle {
    margin-left: auto;
    border-color: var(--line);
  }
  /* фильтры по приоритету стоят рядом с «Мой ход», цвет — как у рамки карточек */
  .toggle.prio1,
  .toggle.prio2,
  .toggle.prio3,
  .toggle.sort {
    margin-left: 0;
  }
  .toggle.prio1 {
    box-shadow: inset 0 -3px 0 #f26a21;
  }
  .toggle.prio2 {
    box-shadow: inset 0 -3px 0 #5fc6c9;
  }
  .toggle.prio3 {
    box-shadow: inset 0 -3px 0 #8a8f96;
  }
  b {
    font-weight: 700;
    margin-left: 2px;
  }
  .search {
    width: 170px;
    background: var(--field);
    color: var(--text);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 6px 9px;
    font: inherit;
  }
  .search:focus {
    outline: none;
    border-color: var(--accent);
  }
  main {
    padding: 8px 20px calc(60px + var(--player-h));
  }
  h2 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin: 18px 0 10px;
    font-weight: 600;
  }
  h2 span {
    opacity: 0.6;
    margin-left: 4px;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
  }
  .blank {
    text-align: center;
    padding: 80px 20px;
  }
  .muted {
    color: var(--muted);
  }
  .banner {
    margin: 10px 20px 0;
    padding: 8px 12px;
    border-radius: 6px;
    background: color-mix(in srgb, var(--bad) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--bad) 50%, transparent);
  }
  .banner.soft {
    background: var(--field);
    border-color: var(--line);
    color: var(--muted);
  }
  .toast {
    position: fixed;
    bottom: calc(22px + var(--player-h));
    left: 50%;
    transform: translateX(-50%);
    z-index: 40;
    background: var(--text);
    color: var(--bg);
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
    box-shadow: 0 6px 24px rgb(0 0 0 / 0.35);
  }
  .toast.bad {
    background: var(--bad);
    color: #fff;
  }
</style>
