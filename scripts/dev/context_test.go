package main

import "testing"

func TestContextEngine(t *testing.T) {
	detections := []Detection{}
	for i := 0; i < 50; i++ {
		detections = append(detections, Detection{Classification: "CPF", Value: "x"})
	}
	detections = append(detections,
		Detection{Classification: "BANK_ACCOUNT", Value: "y"},
		Detection{Classification: "EMAIL_ADDRESS", Value: "z"},
	)

	ctx := buildObjectContext(`C:\dados\folha_pagamento_clientes.xlsx`, "removable", detections)
	if ctx.DetectionCount != 52 {
		t.Fatalf("detection count=%d", ctx.DetectionCount)
	}
	if ctx.ClassificationCount != 3 {
		t.Fatalf("classification count=%d", ctx.ClassificationCount)
	}
	if !ctx.SensitiveFilename {
		t.Fatal("expected sensitive filename")
	}
	if ctx.DestinationTrust != "untrusted" {
		t.Fatalf("trust=%s", ctx.DestinationTrust)
	}

	want := map[string]bool{
		"co_occurrence": false,
		"bulk_data": false,
		"mass_data": false,
		"sensitive_filename": false,
	}
	for _, tag := range ctx.ContextTags {
		if _, ok := want[tag]; ok {
			want[tag] = true
		}
	}
	for tag, found := range want {
		if !found {
			t.Fatalf("missing tag %s in %#v", tag, ctx.ContextTags)
		}
	}
}

func TestMessagingProviderFoundation(t *testing.T) {
	tests := map[string]string{
		"WhatsApp.exe": "whatsapp",
		"ms-teams.exe": "teams",
		"slack.exe": "slack",
		"Telegram.exe": "telegram",
		"Discord.exe": "discord",
	}
	for process, expected := range tests {
		if got := messagingProviderFromProcess(process); got != expected {
			t.Fatalf("%s => %s, want %s", process, got, expected)
		}
	}
}

func TestCEPIsNotNative(t *testing.T) {
	for _, d := range detectSensitive("CEP: 80000-000") {
		if d.Classification == "CEP_BR" {
			t.Fatalf("CEP must be optional/custom, got %#v", d)
		}
	}
}
