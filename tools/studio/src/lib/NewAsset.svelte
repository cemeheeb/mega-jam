<script>
  import { post } from './api.js';
  import { act } from './studio.svelte.js';

  let { groups, onclose, oncreated } = $props();
  let title = $state('');
  let kind = $state('model');
  let group = $state(groups[0] ?? 'items');
  let idea = $state('');

  async function create(e) {
    e.preventDefault();
    const r = await act(() => post('/assets', { title, kind, group, idea }));
    if (r) oncreated(r.id);
  }
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="veil" onclick={onclose}></div>
<form class="dialog" onsubmit={create}>
  <h2>Новый ассет</h2>
  <label>
    Название по-английски
    <!-- svelte-ignore a11y_autofocus -->
    <input bind:value={title} placeholder="Flashlight" required autofocus />
  </label>
  <div class="row">
    <span class="seg">
      <button type="button" class:on={kind === 'model'} onclick={() => (kind = 'model')}>модель</button>
      <button type="button" class:on={kind === 'texture'} onclick={() => (kind = 'texture')}>текстура</button>
    </span>
    <label class="grow">
      Папка
      <input bind:value={group} list="groups" placeholder="items" />
      <datalist id="groups">
        {#each groups as g}<option value={g}></option>{/each}
      </datalist>
    </label>
  </div>
  <label>
    Идея (можно позже)
    <textarea bind:value={idea} rows="2" placeholder="Что это и зачем"></textarea>
  </label>
  <div class="row end">
    <button type="button" onclick={onclose}>Отмена</button>
    <button class="primary" disabled={!title.trim()}>Создать</button>
  </div>
</form>

<style>
  .veil {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 0.5);
    z-index: 30;
  }
  .dialog {
    position: fixed;
    z-index: 31;
    top: 14vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(460px, 94vw);
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  h2 {
    margin: 0;
    font-size: 17px;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 5px;
    font-size: 12px;
    color: var(--muted);
  }
  input,
  textarea {
    background: var(--field);
    color: var(--text);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 7px 9px;
    font: inherit;
    font-size: 14px;
    resize: vertical;
  }
  input:focus,
  textarea:focus {
    outline: none;
    border-color: var(--accent);
  }
  .row {
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }
  .row.end {
    justify-content: flex-end;
  }
  .grow {
    flex: 1;
  }
</style>
