<script>
  import { onMount } from "svelte";
  import { EditorView, keymap } from "@codemirror/view";
  import { EditorState, Compartment, Prec } from "@codemirror/state";
  import { basicSetup } from "codemirror";
  import { python } from "@codemirror/lang-python";
  import { markdown } from "@codemirror/lang-markdown";
  import { StreamLanguage } from "@codemirror/language";
  import { shell } from "@codemirror/legacy-modes/mode/shell";
  import { autocompletion } from "@codemirror/autocomplete";
  import { editorLinks } from "./links.js";

  let {
    value = "",
    language = "markdown",
    onChange = (_value) => {},
    onRun = (_cursor) => {},
    onBlur = () => {},
    readonly = false,
    focus = true,
  } = $props();
  let element;
  let view;
  const editable = new Compartment();
  let syncing = false;

  onMount(() => {
    const syntax =
      language === "markdown"
        ? markdown()
        : language === "python"
          ? python()
          : StreamLanguage.define(shell);
    view = new EditorView({
      parent: element,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          syntax,
          editorLinks,
          autocompletion({ override: [() => null], activateOnTyping: false }),
          EditorView.lineWrapping,
          editable.of(EditorState.readOnly.of(readonly)),
          Prec.highest(
            keymap.of([
              {
                key: "Shift-Enter",
                run: (editor) => {
                  onRun(editor.state.selection.main.head);
                  return true;
                },
              },
              {
                key: "Mod-s",
                run: () => {
                  onBlur();
                  return true;
                },
              },
              { key: "Tab", run: () => true },
            ]),
          ),
          EditorView.contentAttributes.of({
            "aria-label":
              language === "markdown" ? "Markdown editor" : "Code editor",
          }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged && !syncing)
              onChange(update.state.doc.toString());
          }),
          EditorView.domEventHandlers({
            blur: () => {
              onBlur();
            },
          }),
        ],
      }),
    });
    if (focus) view.focus();
    return () => {
      view.destroy();
      view = null;
    };
  });

  $effect(() => {
    const next = value;
    if (view && view.state.doc.toString() !== next) {
      syncing = true;
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: next },
      });
      syncing = false;
    }
  });
  $effect(() => {
    if (view)
      view.dispatch({
        effects: editable.reconfigure(EditorState.readOnly.of(readonly)),
      });
  });
</script>

<div class="editor-host" bind:this={element}></div>
