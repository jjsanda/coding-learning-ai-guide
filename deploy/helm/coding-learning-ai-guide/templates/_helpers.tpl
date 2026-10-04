{{- define "clag.fullname" -}}
{{- .Release.Name }}
{{- end -}}

{{- define "clag.labels" -}}
app.kubernetes.io/name: coding-learning-ai-guide
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "clag.image" -}}
{{- printf "%s/%s:%s" .registry .image .tag -}}
{{- end -}}
