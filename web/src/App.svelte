<script>
  import { onMount } from "svelte";
  import DocumentPane from "./DocumentPane.svelte";
  import TextPane from "./TextPane.svelte";
  import { keepPanelState, panelOrder } from "./panelOrder.js";

  const params = new URLSearchParams(location.hash.slice(1));
  const base = location.pathname.replace(/\/$/, "");
  const tokenKey = `imd-token:${base}`;
  const token = params.get("token") || sessionStorage.getItem(tokenKey) || "";
  if (token) sessionStorage.setItem(tokenKey, token);
  if (params.has("token"))
    history.replaceState(null, "", location.pathname + location.search);

  let documents = $state([]);
  let layout = $state();
  let sessionQueue = Promise.resolve();
  let savingOrder = $state(false);
  let orderError = $state("");

  async function movePanel(id, target) {
    if (savingOrder) return;
    savingOrder = true;
    orderError = "";
    const operation = sessionQueue.then(async () => {
      const ordered = [...documents];
      const index = ordered.findIndex((item) => item.id === id);
      if (index < 0) return;
      ordered.splice(target, 0, ...ordered.splice(index, 1));
      const response = await fetch(`${base}/api/session/order`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ ids: ordered.map((item) => item.id) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Cannot save panel order.");
      await keepPanelState(layout, () => { documents = data.documents; });
    });
    sessionQueue = operation.catch(() => {});
    try { await operation; }
    catch (failure) { orderError = failure.message; }
    finally { savingOrder = false; }
  }

  function openLink(value) {
    const operation = sessionQueue.then(async () => {
      const url = /^https?:\/\//i.test(value);
      const response = await fetch(`${base}${url ? "/api/browser/open" : "/api/paths/open"}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(url ? { url: value } : { path: value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The path does not open.");
      if (data.document) documents = [...documents, data.document];
    });
    sessionQueue = operation.catch(() => {});
    return operation;
  }

  $effect(() => {
    if (documents.length)
      document.title = `${documents.map((item) => item.path.split("/").pop()).join(" | ")} · IMD`;
  });

  onMount(async () => {
    const response = await fetch(`${base}/api/session`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The session does not open.");
    documents = data.documents;
  });
</script>

{#if documents.length}
  {#if orderError}<div class="error-banner panel-order-error" role="alert">{orderError}</div>{/if}
  <div class="session-layout" bind:this={layout} aria-busy={savingOrder} use:panelOrder={{ onMove: movePanel, disabled: savingOrder }} style={`grid-template-columns: repeat(${documents.length}, minmax(0, 1fr))`}>
    {#each documents as item (item.id)}
      {#if item.readonly}
        <TextPane base={base + item.base} path={item.path} {token} paneId={item.id} onOpenLink={openLink} />
      {:else}
        <DocumentPane base={base + item.base} {token} paneId={item.id} onOpenLink={openLink} />
      {/if}
    {/each}
  </div>
{:else}
  <div class="loading-state">Opening the session…</div>
{/if}
