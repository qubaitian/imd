<script>
  import { mount, unmount, onDestroy } from 'svelte';
  import DOMPurify from 'dompurify';
  import morphdom from 'morphdom';
  import Output from './Output.svelte';

  let { rendered, session, onrun } = $props();
  let root;
  const widgets = new Map();

  $effect(() => {
    if (!root) return;
    const ids = new Set(rendered.outputs.map((output) => output.id));
    for (const [id, widget] of widgets) {
      if (!ids.has(id)) { unmount(widget.component); widgets.delete(id); }
    }
    const html = DOMPurify.sanitize(rendered.html);
    morphdom(root, `<article>${html}</article>`, {
      childrenOnly: true,
      getNodeKey: (node) => node.nodeType === 1 ? node.getAttribute('data-output-slot') : undefined,
      onBeforeElUpdated: (from, to) => !(from.hasAttribute('data-output-slot') && from.getAttribute('data-output-slot') === to.getAttribute('data-output-slot')),
    });
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

  onDestroy(() => { for (const widget of widgets.values()) unmount(widget.component); });
</script>

<!-- Run buttons are delegated from the rendered Markdown. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<article class="markdown" bind:this={root} onclick={onrun}></article>
