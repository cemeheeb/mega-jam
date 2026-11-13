<script>
  import { fileUrl } from './api.js';

  let { asset, onopen } = $props();
</script>

<button class="card" class:later={asset.later} onclick={() => onopen(asset.id)} title={asset.id}>
  <div class="thumb">
    {#if asset.thumb}
      <img src={fileUrl(asset.id, asset.thumb.path, asset.thumb.v)} alt="" loading="lazy" />
    {:else}
      <span class="empty">{asset.kind === 'texture' ? '▦' : '◇'}</span>
    {/if}
    {#if asset.warnings.length}
      <span class="warn" title={asset.warnings.join('\n')}>!</span>
    {/if}
    {#if asset.kind === 'texture'}<span class="kind">текстура</span>{/if}
  </div>
  <div class="title">{asset.title}</div>
  <div class="dots">
    {#each asset.steps as s (s.key)}
      <i class={s.state}></i>
    {/each}
  </div>
  <div class="next" class:mine={asset.next?.who === 'author' && !asset.later} class:done={!asset.next}>
    {#if asset.later}отложен{:else if asset.next}{asset.next.label}{:else}готово{/if}
  </div>
</button>

<style>
  .card {
    all: unset;
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
