import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import type { Language } from '../api/types'

export function CodeEditor({
  value,
  onChange,
  language,
}: {
  value: string
  onChange: (value: string) => void
  language: Language
}) {
  const extension = language === 'python' ? python() : javascript()
  return (
    <div className="overflow-hidden rounded-lg border border-slate-300">
      <CodeMirror
        value={value}
        height="360px"
        extensions={[extension]}
        onChange={onChange}
        basicSetup={{ lineNumbers: true, highlightActiveLine: true }}
      />
    </div>
  )
}
