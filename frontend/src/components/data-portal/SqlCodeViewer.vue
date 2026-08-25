<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { sql } from '@codemirror/lang-sql'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'

const props = withDefaults(defineProps<{
  code: string
  minHeight?: string
  maxHeight?: string
  ariaLabel?: string
}>(), {
  minHeight: '9rem',
  maxHeight: '18rem',
  ariaLabel: '只读 SQL 内容',
})

const host = ref<HTMLDivElement | null>(null)
const editorView = shallowRef<EditorView | null>(null)

const createTheme = () => EditorView.theme({
  '&': {
    backgroundColor: '#020617',
    color: '#d1fae5',
    border: '1px solid rgb(15 23 42)',
    borderRadius: '0.75rem',
    fontSize: '0.75rem',
  },
  '&.cm-focused': {
    outline: '2px solid rgb(59 130 246 / 0.25)',
    outlineOffset: '1px',
  },
  '.cm-scroller': {
    minHeight: props.minHeight,
    maxHeight: props.maxHeight,
    overflow: 'auto',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    lineHeight: '1.625',
  },
  '.cm-content': {
    minHeight: props.minHeight,
    padding: '0.75rem 0.875rem',
  },
  '.cm-line': {
    padding: '0',
  },
  '.cm-gutters': {
    backgroundColor: '#020617',
    color: '#64748b',
    borderRight: '1px solid rgb(30 41 59)',
  },
  '.cm-activeLine': {
    backgroundColor: 'rgb(15 23 42 / 0.75)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'rgb(15 23 42)',
    color: '#cbd5e1',
  },
  '.cm-selectionBackground, ::selection': {
    backgroundColor: 'rgb(37 99 235 / 0.35) !important',
  },
})

const destroyEditor = () => {
  editorView.value?.destroy()
  editorView.value = null
}

const createEditor = () => {
  if (!host.value) return
  destroyEditor()
  const state = EditorState.create({
    doc: props.code,
    extensions: [
      basicSetup,
      sql(),
      EditorState.readOnly.of(true),
      EditorView.editable.of(false),
      createTheme(),
    ],
  })
  editorView.value = new EditorView({ state, parent: host.value })
}

watch(
  () => props.code,
  (code) => {
    const view = editorView.value
    if (!view || view.state.doc.toString() === code) return
    view.dispatch({
      changes: {
        from: 0,
        to: view.state.doc.length,
        insert: code,
      },
    })
  },
)

onMounted(createEditor)
onBeforeUnmount(destroyEditor)
</script>

<template>
  <div
    ref="host"
    class="sql-code-viewer w-full overflow-hidden rounded-xl"
    role="textbox"
    aria-readonly="true"
    :aria-label="ariaLabel"
  />
</template>
