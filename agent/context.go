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

	tagSet := map[string]bool{}
	addTag := func(tag string) {
		tag = strings.TrimSpace(strings.ToLower(tag))
		if tag != "" {
			tagSet[tag] = true
		}
	}

	if len(classes) >= 2 {
		addTag("co_occurrence")
	}
	if len(detections) >= 10 {
		addTag("bulk_data")
	}
	if len(detections) >= 50 {
		addTag("mass_data")
	}
	if len(signals) > 0 {
		addTag("sensitive_filename")
	}
	highValue := highValueExtensions[strings.ToLower(filepath.Ext(path))]
	if highValue {
		addTag("high_value_extension")
	}

	for _, detection := range detections {
		evidence := strings.ToLower(detection.Evidence)
		if strings.Contains(evidence, "obfuscated_identifier") {
			addTag("obfuscated_identifier")
		}
		if strings.Contains(evidence, "evasive_obfuscation") {
			addTag("evasive_obfuscation")
		}
		if strings.Contains(evidence, "malformed_identifier") {
			addTag("malformed_identifier")
		}
		if strings.Contains(evidence, "embedded_identifier") {
			addTag("embedded_identifier")
		}
	}

	tags := make([]string, 0, len(tagSet))
	for tag := range tagSet {
		tags = append(tags, tag)
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
