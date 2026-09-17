<script>
  import { onMount } from "svelte";
  import DocumentPane from "./DocumentPane.svelte";

  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get("token") || sessionStorage.getItem("imd-token") || "";
  if (token) sessionStorage.setItem("imd-token", token);
  if (params.has("token"))
    history.replaceState(null, "", location.pathname + location.search);

  let documents = $state([]);

  onMount(async () => {
    const response = await fetch("/api/session", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The session does not open.");
    documents = data.documents;
    document.title = `${documents.map((item) => item.path.split("/").pop()).join(" | ")} · IMD`;
  });
</script>

{#if documents.length}
  <div class="session-layout" class:split={documents.length === 2}>
    {#each documents as item, index (item.path)}
      <DocumentPane base={item.base} {token} paneId={`document-${index}`} />
    {/each}
  </div>
{:else}
  <div class="loading-state">Opening the session…</div>
{/if}
