<script>
  // Поле с автосохранением: пишется при уходе из поля. Пока в поле курсор, сервер его не перезаписывает.
  import { tick, untrack } from 'svelte';

  let { value = '', placeholder = '', onsave, single = false, big = false } = $props();
  let draft = $state('');
  let focused = $state(false);
  let el = $state();

  $effect(() => {
    const v = value;
    untrack(() => {
      if (!focused) draft = v;
    });
  });

  // Высота по тексту. Мерить можно только после того, как текст попал в поле, поэтому ждём tick.
  $effect(() => {
    draft;
    if (!el || single) return;
    tick().then(() => {
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight + 2}px`;
    });
  });

  function commit() {
    focused = false;
    if (draft.trimEnd() !== value) onsave(draft);
  }

  function key(e) {
    if (e.key === 'Escape') {
      draft = value;
      e.target.blur();
      e.stopPropagation();
    }
    if (e.key === 'Enter' && (single || e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      e.target.blur();
    }
  }
</script>

{#if single}
  <input class="field" class:big bind:this={el} bind:value={draft} {placeholder} onfocus={() => (focused = true)} onblur={commit} onkeydown={key} />
{:else}
  <textarea
    class="field"
    rows="2"
    bind:this={el}
    bind:value={draft}
    {placeholder}
    onfocus={() => (focused = true)}
    onblur={commit}
    onkeydown={key}
  ></textarea>
{/if}

<style>
  .field {
    width: 100%;
    background: var(--field);
    color: var(--text);
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 7px 9px;
    font: inherit;
    line-height: 1.45;
    resize: none;
    overflow: hidden;
    display: block;
  }
  .field:hover {
    border-color: var(--line);
  }
  .field:focus {
    outline: none;
    border-color: var(--accent);
    background: var(--bg);
  }
  .big {
    font-size: 20px;
    font-weight: 650;
    background: transparent;
    padding: 4px 6px;
    margin-left: -6px;
  }
</style>
