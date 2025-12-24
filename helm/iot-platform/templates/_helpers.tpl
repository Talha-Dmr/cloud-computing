{{/*
Expand the name of the chart.
*/}}
{{- define "iot-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "iot-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "iot-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "iot-platform.labels" -}}
helm.sh/chart: {{ include "iot-platform.chart" . }}
{{ include "iot-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "iot-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "iot-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Device Registry labels
*/}}
{{- define "iot-platform.deviceRegistry.labels" -}}
app.kubernetes.io/name: device-registry
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Data Ingestion labels
*/}}
{{- define "iot-platform.dataIngestion.labels" -}}
app.kubernetes.io/name: data-ingestion
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Alert Engine labels
*/}}
{{- define "iot-platform.alertEngine.labels" -}}
app.kubernetes.io/name: alert-engine
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
User Management labels
*/}}
{{- define "iot-platform.userManagement.labels" -}}
app.kubernetes.io/name: user-management
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Notification Service labels
*/}}
{{- define "iot-platform.notificationService.labels" -}}
app.kubernetes.io/name: notification-service
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
