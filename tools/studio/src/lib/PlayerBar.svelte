<script>
  // Полоса проигрывателя внизу окна: что играет, волна с перемоткой, петля, громкость.
  import PlayButton from './PlayButton.svelte';
  import Wave from './Wave.svelte';
  import { close, player, setLoop, setVolume, step, toggle } from './player.svelte.js';

  let { onopen } = $props();

  // полоса не должна закрывать низ панели ассета и всплывающие сообщения
  $effect(() => {
    document.body.classList.toggle('has-player', Boolean(player.track));
  });

  function key(e) {
    if (e.code !== 'Space' || !player.track || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(t.tagName) || t.isContentEditable) return;
    e.preventDefault();
    toggle(player.track);
  }
</script>

<svelte:window onkeydown={key} />

{#if player.track}
  {@const t = player.track}
  <div class="bar">
    <PlayButton track={t} big />
    <div class="nav">
      <button class="quiet" onclick={() => step(-1)} disabled={player.queue.length < 2} title="Предыдущий звук в списке">⏮</button>
      <button class="quiet" onclick={() => step(1)} disabled={player.queue.length < 2} title="Следующий звук в списке">⏭</button>
    </div>
    <div class="info">
      {#if t.assetId}
        <button class="link name" onclick={() => onopen(t.assetId)} title="Открыть карточку">{t.title}</button>
      {:else}
        <span class="name">{t.title}</span>
      {/if}
      <span class="sub" class:bad={player.error}>{player.error || t.sub}</span>
    </div>
    <div class="track"><Wave track={t} /></div>
    <button class="loop" class:on={player.loop} onclick={() => setLoop(!player.loop)} title="По кругу без паузы на стыке: так слышно, бесшовная ли петля">
      ⟳ петля
    </button>
    <label class="vol" title="Громкость">
      <span aria-hidden="true">🔈</span>
      <input type="range" min="0" max="1" step="0.01" value={player.volume} oninput={(e) => setVolume(Number(e.target.value))} />
    </label>
    <button class="quiet" onclick={close} title="Остановить и закрыть">✕</button>
  </div>
{/if}

<style>
  .bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 15;
    height: var(--player-h);
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 16px;
    background: color-mix(in srgb, var(--panel) 96%, transparent);
    backdrop-filter: blur(8px);
    border-top: 1px solid var(--line);
    box-shadow: 0 -6px 24px rgb(0 0 0 / 0.25);
  }
  .nav {
    display: flex;
  }
  .info {
    width: 220px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }
  .name {
    font-weight: 600;
    text-align: left;
    color: var(--text);
    font-size: 14px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub {
    font-size: 12px;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sub.bad {
    color: var(--bad);
  }
  .track {
    flex: 1;
    min-width: 120px;
    height: 34px;
  }
  .loop.on {
    background: var(--accent);
    border-color: var(--accent);
    color: #1a1206;
    font-weight: 600;
  }
  .vol {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
  }
  .vol input {
    width: 90px;
    accent-color: var(--accent);
  }
  @media (max-width: 760px) {
    .info {
      width: 120px;
    }
    .vol,
    .nav {
      display: none;
    }
  }
</style>
