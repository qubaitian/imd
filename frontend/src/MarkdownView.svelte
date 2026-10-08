<script>
  import { mount, unmount, onDestroy } from 'svelte';
  import DOMPurify from 'dompurify';
  import morphdom from 'morphdom';
  import Output from './Output.svelte';
  import CodeBlock from './CodeBlock.svelte';

  let { rendered, session, onrun, oncodechange, focusBlock = null } = $props();
  let root;
  const widgets = new Map();
  const editors = new Map();

  $effect(() => {
    if (!root) return;
    const ids = new Set(rendered.outputs.map((output) => output.id));
    for (const [id, widget] of widgets) {
      if (!ids.has(id)) { unmount(widget.component); widgets.delete(id); }
    }
    for (const [index, editor] of editors) {
      if (index >= rendered.editableBlocks.length) { unmount(editor.component); editors.delete(index); }
    }
    const html = DOMPurify.sanitize(rendered.html);
    morphdom(root, `<article>${html}</article>`, {
      childrenOnly: true,
      getNodeKey: (node) => node.nodeType === 1 ? (node.hasAttribute('data-output-slot') ? `output-${node.getAttribute('data-output-slot')}` : node.hasAttribute('data-code-slot') ? `code-${node.getAttribute('data-code-slot')}` : undefined) : undefined,
      onBeforeElUpdated: (from, to) => !['data-output-slot', 'data-code-slot'].some((attribute) => from.hasAttribute(attribute) && from.getAttribute(attribute) === to.getAttribute(attribute)),
    });
    for (const [index, block] of rendered.editableBlocks.entries()) {
      const existing = editors.get(index);
      const element = root.querySelector(`[data-code-slot="${index}"]`);
      const focusRequest = focusBlock?.line === block.map[0] ? focusBlock : null;
      if (existing && existing.element === element && (!focusRequest || existing.focusRequest === focusRequest)) {
        existing.props.block = block;
        existing.props.focusRequest = focusRequest;
        continue;
      }
      if (existing) unmount(existing.component);
      if (element) {
        element.replaceChildren();
        const props = $state({ block, onchange: oncodechange, focusRequest });
        editors.set(index, { element, focusRequest, props, component: mount(CodeBlock, { target: element, props }) });
      }
    }
    for (const output of rendered.outputs) {
      const existing = widgets.get(output.id);
      if (existing) { existing.props.text = output.text; continue; }
      const element = root.querySelector(`[data-output-slot="${output.id}"]`);
      if (element) {
        const props = $state({ ...output, session });
        widgets.set(output.id, { props, component: mount(Output, { target: element, props }) });
      }
    }
  });

  onDestroy(() => { for (const widget of [...widgets.values(), ...editors.values()]) unmount(widget.component); });
</script>

<!-- Run and add buttons are delegated from the rendered Markdown. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<article class="markdown" bind:this={root} onclick={onrun}></article>
