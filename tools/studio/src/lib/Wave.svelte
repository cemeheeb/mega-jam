<script>
  // Волна дорожки. Сыгранная часть — акцентным цветом. Щелчок по волне — играть с этого места.
  import { fmt, loadWave, play, player, seek } from './player.svelte.js';

  let { track, queue = null, interactive = true, time = true } = $props();

  let wave = $state(null);
  $effect(() => {
    const url = track.peaks;
    let alive = true;
    loadWave(url)
      .then((w) => alive && (wave = w))
      .catch(() => alive && (wave = { duration: 0, peaks: null }));
    return () => (alive = false);
  });

  const current = $derived(player.track?.key === track.key);
  const progress = $derived(current && player.duration ? player.time / player.duration : 0);
  const peaks = $derived(wave?.peaks ?? []);
  const cut = $derived(Math.round(progress * peaks.length));
  // тихий звук на картинке поднимается до полной высоты, но не больше чем вчетверо: почти тишина остаётся видна как тишина
  const boost = $derived(Math.min(4, 1 / Math.max(0.001, ...peaks)));

  // столбики одним путём: ширина 0.7 из 1, высота от середины в обе стороны, не меньше 2 из 100
  function bars(from, to) {
    let d = '';
    for (let i = from; i < to; i++) {
      const h = Math.max(2, Math.min(1, peaks[i] * boost) * 96);
      d += `M${i + 0.15} ${50 - h / 2}h0.7v${h}h-0.7Z`;
    }
    return d;
  }
  const played = $derived(bars(0, cut));
  const rest = $derived(bars(cut, peaks.length));

  function click(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const f = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    if (current && !player.loading && player.duration) seek(f);
    else play(track, { queue, at: f });
  }
</script>

<div class="wave" class:current>
  {#if interactive}
    <button class="area" onclick={click} title="Играть с этого места">
      {@render svg()}
    </button>
  {:else}
    <div class="area">{@render svg()}</div>
  {/if}
  {#if time}
    <span class="time">
      {current && player.duration ? `${fmt(player.time)} / ${fmt(player.duration)}` : fmt(wave?.duration)}
    </span>
  {/if}
</div>

{#snippet svg()}
  {#if wave && !wave.peaks}
    <span class="flat"></span>
  {:else}
    <svg viewBox="0 0 {peaks.length || 1} 100" preserveAspectRatio="none" aria-hidden="true">
      <path class="rest" d={rest} />
      <path class="played" d={played} />
    </svg>
  {/if}
{/snippet}

<style>
  .wave {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    height: 100%;
  }
  .area {
    all: unset;
    flex: 1;
    min-width: 0;
    height: 100%;
    display: flex;
    align-items: center;
  }
  button.area {
    cursor: pointer;
  }
  button.area:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: 3px;
  }
  svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  .rest {
    fill: var(--muted);
    opacity: 0.55;
  }
  .current .rest {
    opacity: 0.8;
  }
  .played {
    fill: var(--accent);
  }
  .flat {
    display: block;
    width: 100%;
    height: 2px;
    background: var(--line);
  }
  .time {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .current .time {
    color: var(--text);
  }
</style>
