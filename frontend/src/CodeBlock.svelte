<script>
  import { untrack } from 'svelte';
  let { block, onchange, focusRequest = null } = $props();
  let editing = $state(untrack(() => !!focusRequest));
  let value = $state(untrack(() => focusRequest ? block.code : ''));
  let textarea = $state();

  function edit() {
    if (!block.editable) return;
    value = block.code;
    editing = true;
  }

  function input() {
    onchange(block, value);
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }

  $effect(() => {
    if (editing && textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
      textarea.focus();
    }
  });

  $effect(() => { if (!block.editable) editing = false; });
</script>

{#if editing}
  <textarea class="code-block-editor" bind:this={textarea} bind:value oninput={input} onblur={() => editing = false} spellcheck="false" aria-label="Code block editor"></textarea>
{:else if block.editable}
  <div role="button" tabindex="0" onclick={edit} onkeydown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); edit(); } }} aria-label="Edit code block"><pre><code>{block.code}</code></pre></div>
{:else}
  <pre><code>{block.code}</code></pre>
{/if}
