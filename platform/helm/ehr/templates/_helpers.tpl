{{- define "ehr.name" -}}ehr{{- end -}}
{{- define "ehr.fullname" -}}{{ printf "%s-%s" .Release.Name (include "ehr.name" .) | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "ehr.image" -}}{{ .Values.image.repository }}:{{ .Values.image.tag }}{{ if .Values.image.digest }}@{{ .Values.image.digest }}{{ end }}{{- end -}}
{{- define "ehr.webImage" -}}{{ .Values.image.webRepository }}:{{ .Values.image.webTag }}{{ if .Values.image.webDigest }}@{{ .Values.image.webDigest }}{{ end }}{{- end -}}
{{- define "ehr.serviceAccountName" -}}{{ if .Values.serviceAccount.create }}{{ default (include "ehr.fullname" .) .Values.serviceAccount.name }}{{ else }}{{ default "default" .Values.serviceAccount.name }}{{ end }}{{- end -}}
{{- define "ehr.commonLabels" -}}{{ include "ehr-library.labels" (dict "root" . "name" "ehr" "component" "application") }}{{- end -}}
{{- define "ehr.selector" -}}{{ include "ehr-library.selectorLabels" (dict "root" . "name" "ehr") }}{{- end -}}
{{- define "ehr.topology" -}}
{{- if and .Values.topologySpread.enabled (not .Values.singleNode.enabled) }}
topologySpreadConstraints:
  - maxSkew: {{ .Values.topologySpread.maxSkew }}
    topologyKey: {{ .Values.topologySpread.topologyKey | quote }}
    whenUnsatisfiable: {{ .Values.topologySpread.whenUnsatisfiable }}
    labelSelector:
      matchLabels:
{{ include "ehr.selector" . | indent 8 }}
{{- end }}
{{- end }}
