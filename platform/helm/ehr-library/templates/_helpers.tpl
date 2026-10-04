{{/* type-10042026-Maurice: Keep shared platform conventions in one library seam. */}}
{{- define "ehr-library.labels" -}}
app.kubernetes.io/name: {{ .name | quote }}
app.kubernetes.io/instance: {{ .root.Release.Name | quote }}
app.kubernetes.io/managed-by: {{ .root.Release.Service | quote }}
app.kubernetes.io/part-of: ehr
app.kubernetes.io/component: {{ .component | quote }}
helm.sh/chart: {{ .root.Chart.Name }}-{{ .root.Chart.Version | replace "+" "_" }}
{{- end }}
{{- define "ehr-library.selectorLabels" -}}
app.kubernetes.io/name: {{ .name | quote }}
app.kubernetes.io/instance: {{ .root.Release.Name | quote }}
{{- end }}
{{- define "ehr-library.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end }}
{{- define "ehr-library.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: [ALL]
readOnlyRootFilesystem: {{ .readOnlyRootFilesystem | default true }}
runAsNonRoot: true
{{- end }}
{{- define "ehr-library.resources" -}}
requests:
  cpu: {{ .requests.cpu | quote }}
  memory: {{ .requests.memory | quote }}
limits:
  cpu: {{ .limits.cpu | quote }}
  memory: {{ .limits.memory | quote }}
{{- end }}
{{- define "ehr-library.probes" -}}
startupProbe:
  httpGet:
    path: {{ .startup.path | quote }}
    port: {{ .port }}
  failureThreshold: {{ .startup.failureThreshold }}
  periodSeconds: {{ .startup.periodSeconds }}
readinessProbe:
  httpGet:
    path: {{ .readiness.path | quote }}
    port: {{ .port }}
  periodSeconds: {{ .readiness.periodSeconds }}
livenessProbe:
  httpGet:
    path: {{ .liveness.path | quote }}
    port: {{ .port }}
  periodSeconds: {{ .liveness.periodSeconds }}
{{- end }}
