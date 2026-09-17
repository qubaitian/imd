<script>
  import { onMount } from "svelte";
  import DocumentPane from "./DocumentPane.svelte";
  import TextPane from "./TextPane.svelte";

  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get("token") || sessionStorage.getItem("imd-token") || "";
  if (token) sessionStorage.setItem("imd-token", token);
  if (params.has("token"))
    history.replaceState(null, "", location.pathname + location.search);

  let documents = $state([]);
  let opening = Promise.resolve();

  function openLink(value) {
    const operation = opening.then(async () => {
      const url = /^https?:\/\//i.test(value);
      const response = await fetch(url ? "/api/browser/open" : "/api/paths/open", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(url ? { url: value } : { path: value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The path does not open.");
      if (data.document) documents = [...documents, data.document];
    });
    opening = operation.catch(() => {});
    return operation;
  }

  $effect(() => {
    if (documents.length)
      document.title = `${documents.map((item) => item.path.split("/").pop()).join(" | ")} · IMD`;
  });

  onMount(async () => {
    const response = await fetch("/api/session", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The session does not open.");
    documents = data.documents;
  });
</script>

{#if documents.length}
  <div class="session-layout" style={`grid-template-columns: repeat(${documents.length}, minmax(0, 1fr))`}>
    {#each documents as item, index (index)}
      {#if item.readonly}
        <TextPane base={item.base} path={item.path} {token} onOpenLink={openLink} />
      {:else}
        <DocumentPane base={item.base} {token} paneId={`document-${index}`} onOpenLink={openLink} />
      {/if}
    {/each}
  </div>
{:else}
  <div class="loading-state">Opening the session…</div>
{/if}
