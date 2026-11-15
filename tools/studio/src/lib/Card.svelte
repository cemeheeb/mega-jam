<script>
  import { fileUrl, post } from './api.js';
  import PlayButton from './PlayButton.svelte';
  import { fmt, loadWave, mainTrack, player } from './player.svelte.js';
  import { act } from './studio.svelte.js';
  import Wave from './Wave.svelte';

  let { asset, onopen, queue = null } = $props();

  // звук: на месте картинки — волна главного файла, поверх — кнопка ▶
  const track = $derived(mainTrack(asset));
  const playing = $derived(track && player.track?.key === track.key);
  let seconds = $state(0);
  $effect(() => {
    if (!track) return;
    let alive = true;
    loadWave(track.peaks).then((w) => alive && (seconds = w.duration)).catch(() => {});
    return () => (alive = false);
  });

  const mark = (on) => act(() => post('/asset/update', { id: asset.id, fields: { generated: on } }));
</script>

<div class="wrap">
  <button
    class="card"
    class:later={asset.later}
    class:p1={asset.priority === 1}
    class:p2={asset.priority === 2}
    class:p3={asset.priority === 3}
    class:generated={asset.generated}
    class:playing
    onclick={() => onopen(asset.id)}
    title={asset.id}
  >
    <div class="thumb">
      {#if asset.thumb}
        <img src={fileUrl(asset.id, asset.thumb.path, asset.thumb.v)} alt="" loading="lazy" />
      {:else if track}
        <div class="wavethumb"><Wave {track} interactive={false} time={false} /></div>
      {:else}
        <span class="empty">{asset.kind === 'texture' ? '▦' : asset.kind === 'sound' ? '♪' : '◇'}</span>
      {/if}
      {#if asset.warnings.length}
        <span class="warn" title={asset.warnings.join('\n')}>!</span>
      {/if}
      {#if asset.kind === 'texture'}<span class="kind">текстура</span>{/if}
      {#if asset.kind === 'sound'}<span class="kind">{seconds ? fmt(seconds) : 'звук'}{asset.loop ? ' · петля' : ''}</span>{/if}
      {#if asset.priority}<span class="prio" title="Приоритет: 1 — сначала, 3 — в последнюю очередь">П{asset.priority}</span>{/if}
    </div>
    <div class="title">{asset.title}</div>
    <div class="dots">
      {#each asset.steps as s (s.key)}
        <i class={s.state}></i>
      {/each}
    </div>
    <div class="next" class:mine={asset.next?.who === 'author' && !asset.later} class:done={!asset.next || asset.next.who === 'done'}>
      {#if asset.later}отложен{:else if asset.next}{asset.next.label}{asset.next.who === 'done' ? ' ✓' : ''}{:else}готово{/if}
    </div>
  </button>
  {#if track}
    <div class="over"><PlayButton {track} {queue} big /></div>
  {/if}
  <label class="gen" class:on={asset.generated} title="Сгенерирован: картинка или звук сделаны, в карточку не занесены">
    <input type="checkbox" checked={asset.generated} onchange={(e) => mark(e.target.checked)} />
  </label>
</div>

<style>
  .wrap {
    position: relative;
    min-width: 0;
    display: flex;
  }
  /* слой точно над миниатюрой (рамка 1 + отступ 8): кнопка ▶ по центру, остальное кликается сквозь */
  .over {
    position: absolute;
    top: 9px;
    left: 9px;
    right: 9px;
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    pointer-events: none;
  }
  .over :global(.play) {
    pointer-events: auto;
    opacity: 0.85;
    box-shadow: 0 2px 10px rgb(0 0 0 / 0.35);
  }
  .wrap:hover .over :global(.play),
  .over :global(.play.playing),
  .over :global(.play.paused) {
    opacity: 1;
  }
  .wavethumb {
    position: absolute;
    inset: 22% 8px;
  }
  .card.playing {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .gen {
    position: absolute;
    top: 13px;
    left: 13px;
    width: 22px;
    height: 22px;
    border-radius: 5px;
    background: rgb(0 0 0 / 0.55);
    display: grid;
    place-items: center;
    cursor: pointer;
    opacity: 0.55;
  }
  .wrap:hover .gen,
  .gen.on {
    opacity: 1;
  }
  .gen.on {
    background: var(--ok);
  }
  .gen input {
    margin: 0;
    cursor: pointer;
  }
  .card {
    all: unset;
    flex: 1;
    box-sizing: border-box;
    cursor: pointer;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  .card:hover,
  .card:focus-visible {
    border-color: var(--accent);
  }
  .later {
    opacity: 0.45;
  }
  /* очередь работы: цвет рамки и лёгкий тон фона */
  .p1 {
    --prio: #f26a21;
  }
  .p2 {
    --prio: #5fc6c9;
  }
  .p3 {
    --prio: #8a8f96;
  }
  .p1,
  .p2,
  .p3 {
    border-color: var(--prio);
    box-shadow: inset 4px 0 0 var(--prio);
    background: color-mix(in srgb, var(--prio) 9%, var(--panel));
  }
  .generated {
    border-color: var(--ok);
    box-shadow: inset 4px 0 0 var(--ok);
    background: color-mix(in srgb, var(--ok) 10%, var(--panel));
  }
  .prio {
    position: absolute;
    right: 6px;
    bottom: 6px;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--prio);
    color: #111;
  }
  .thumb {
    position: relative;
    aspect-ratio: 1;
    border-radius: 6px;
    background: var(--field);
    overflow: hidden;
    display: grid;
    place-items: center;
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .empty {
    font-size: 34px;
    color: var(--muted);
    opacity: 0.5;
  }
  .warn {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--bad);
    color: #fff;
    font-weight: 700;
    font-size: 13px;
    display: grid;
    place-items: center;
  }
  .kind {
    position: absolute;
    left: 6px;
    bottom: 6px;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgb(0 0 0 / 0.6);
    color: #fff;
  }
  .title {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .dots {
    display: flex;
    gap: 4px;
  }
  .dots i {
    flex: 1;
    height: 4px;
    border-radius: 2px;
    background: var(--line);
  }
  .dots i.done {
    background: var(--ok);
  }
  .dots i.next {
    background: var(--accent);
  }
  .dots i.skipped {
    background: color-mix(in srgb, var(--ok) 35%, var(--line));
  }
  .next {
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .next.mine {
    color: var(--accent);
    font-weight: 600;
  }
  .next.done {
    color: var(--ok);
  }
</style>
