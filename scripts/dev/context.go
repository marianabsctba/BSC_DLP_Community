package main

import (
	"path/filepath"
	"sort"
	"strings"
)

type ObjectContext struct {
	DetectionCount      int
	ClassificationCount int
	Classifications     []string
	SensitiveFilename   bool
	FilenameSignals     []string
	ContextTags         []string
	DestinationTrust    string
}

var sensitiveFilenameSignals = map[string][]string{
	"payroll":       {"folha_pagamento", "folha-de-pagamento", "payroll", "salario", "salários", "salary", "nomina", "nómina"},
	"customer_data": {"clientes", "cliente", "customers", "customer", "customer_export", "client_export"},
	"employee_data": {"funcionarios", "funcionários", "colaboradores", "employees", "employee", "empleados"},
	"credentials":   {"credenciais", "credentials", "credential", "passwords", "senhas", "secrets", "api_keys"},
	"finance":       {"financeiro", "financial", "banking", "bancario", "bancário", "pagamentos", "payment"},
	"personal_data": {"dados_pessoais", "personal_data", "pii", "datos_personales"},
	"database":      {"database", "banco_dados", "db_dump", "sql_dump", "backup", "full_export", "export_completo"},
}

var highValueExtensions = map[string]bool{
	".env": true, ".pem": true, ".key": true, ".pfx": true, ".p12": true,
	".kdbx": true, ".sql": true, ".dump": true, ".bak": true,
}

func normalizeFilename(path string) string {
	name := strings.ToLower(filepath.Base(path))
	r := strings.NewReplacer(" ", "_", ".", "_", "(", "_", ")", "_", "[", "_", "]", "_")
	return r.Replace(name)
}

func destinationTrustForChannel(channel string) string {
	switch strings.ToLower(strings.TrimSpace(channel)) {
	case "removable":
		return "untrusted"
	case "filesystem", "download", "screenshot":
		return "local"
	case "messaging", "email", "ai":
		return "external"
	default:
		return "unknown"
	}
}

func buildObjectContext(path, channel string, detections []Detection) ObjectContext {
	classSet := map[string]bool{}
	for _, d := range detections {
		c := strings.ToUpper(strings.TrimSpace(d.Classification))
		if c != "" {
			classSet[c] = true
		}
	}

	classes := make([]string, 0, len(classSet))
	for c := range classSet {
		classes = append(classes, c)
	}
	sort.Strings(classes)

	name := normalizeFilename(path)
	signals := []string{}
	for signal, keywords := range sensitiveFilenameSignals {
		for _, keyword := range keywords {
			if strings.Contains(name, strings.ToLower(keyword)) {
				signals = append(signals, signal)
				break
			}
		}
	}
	sort.Strings(signals)

	tags := []string{}
	if len(classes) >= 2 {
		tags = append(tags, "co_occurrence")
	}
	if len(detections) >= 10 {
		tags = append(tags, "bulk_data")
	}
	if len(detections) >= 50 {
		tags = append(tags, "mass_data")
	}
	if len(signals) > 0 {
		tags = append(tags, "sensitive_filename")
	}
	highValue := highValueExtensions[strings.ToLower(filepath.Ext(path))]
	if highValue {
		tags = append(tags, "high_value_extension")
	}
	sort.Strings(tags)

	return ObjectContext{
		DetectionCount:      len(detections),
		ClassificationCount: len(classes),
		Classifications:     classes,
		SensitiveFilename:   len(signals) > 0 || highValue,
		FilenameSignals:     signals,
		ContextTags:         tags,
		DestinationTrust:    destinationTrustForChannel(channel),
	}
}

func messagingProviderFromProcess(process string) string {
	p := strings.ToLower(filepath.Base(strings.TrimSpace(process)))
	switch p {
	case "whatsapp.exe", "whatsapp":
		return "whatsapp"
	case "ms-teams.exe", "teams.exe", "msteams.exe", "microsoft teams":
		return "teams"
	case "slack.exe", "slack":
		return "slack"
	case "telegram.exe", "telegram":
		return "telegram"
	case "discord.exe", "discord":
		return "discord"
	default:
		return ""
	}
}
