<script>
  // Круглая кнопка ▶ / ❚❚ у дорожки. Играет через общий проигрыватель: другой звук при этом останавливается.
  import { player, toggle } from './player.svelte.js';

  let { track, queue = null, big = false } = $props();

  const current = $derived(player.track?.key === track.key);
  const state = $derived(!current ? 'idle' : player.loading ? 'loading' : player.playing ? 'playing' : 'paused');
</script>

<button
  class="play {state}"
  class:big
  onclick={(e) => {
    e.stopPropagation();
    toggle(track, { queue });
  }}
  title={state === 'playing' ? 'Пауза (пробел)' : 'Слушать'}
  aria-label={state === 'playing' ? 'Пауза' : 'Слушать'}
>
  {#if state === 'loading'}
    <span class="spin"></span>
  {:else if state === 'playing'}
    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="3" width="3" height="10" rx="0.8" /><rect x="9.5" y="3" width="3" height="10" rx="0.8" /></svg>
  {:else}
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.2v9.6a.6.6 0 0 0 .9.5l7.6-4.8a.6.6 0 0 0 0-1L5.9 2.7a.6.6 0 0 0-.9.5Z" /></svg>
  {/if}
</button>

<style>
  .play {
    flex: none;
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--field);
    border: 1px solid var(--line);
    color: var(--text);
  }
  .play.big {
    width: 42px;
    height: 42px;
  }
  .play.playing,
  .play.paused,
  .play.loading {
    background: var(--accent);
    border-color: var(--accent);
    color: #1a1206;
  }
  svg {
    width: 14px;
    height: 14px;
    fill: currentColor;
  }
  .big svg {
    width: 18px;
    height: 18px;
  }
  .spin {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-right-color: transparent;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
