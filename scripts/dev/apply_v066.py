#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def read(rel):
    p = ROOT / rel
    if not p.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return p.read_text(encoding="utf-8")

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"[updated] {rel}")

def replace_once(text, old, new, label):
    if new in text:
        print(f"[skip] {label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 exact match, found {count}")
    return text.replace(old, new, 1)

def patch_detectors():
    text = read("agent/detectors.go")
    anchor = "func detectSensitiveWithRules(text string, rules []CustomDetectionRule) []Detection {\n\tout := detectSensitive(text)\n"
    replacement = anchor + "\tout = augmentSensitiveCatalogDetections(text, out)\n"
    text = replace_once(text, anchor, replacement, "catalog augmentation in detector pipeline")
    write("agent/detectors.go", text)

def patch_context():
    text = read("agent/context.go")
    anchor = '\tfor _, detection := range detections {\n\t\tevidence := strings.ToLower(detection.Evidence)\n'
    replacement = '\tfor _, detection := range detections {\n\t\tfor _, catalogTag := range sensitiveCatalogTags(detection) {\n\t\t\taddTag(catalogTag)\n\t\t}\n\t\tevidence := strings.ToLower(detection.Evidence)\n'
    text = replace_once(text, anchor, replacement, "catalog tags per detection")

    anchor2 = '\ttags := make([]string, 0, len(tagSet))\n'
    replacement2 = '\tfor _, aggregateTag := range catalogAggregateTags(detections) {\n\t\taddTag(aggregateTag)\n\t}\n\n\ttags := make([]string, 0, len(tagSet))\n'
    text = replace_once(text, anchor2, replacement2, "aggregate PII tags")
    write("agent/context.go", text)

def patch_api():
    text = read("api/app.py")

    for old in ('version="0.6.5"', 'version="0.6.4.1"', 'version="0.6.4"'):
        text = text.replace(old, 'version="0.6.6"')
    for old in ('"version": "0.6.5"', '"version": "0.6.4.1"', '"version": "0.6.4"'):
        text = text.replace(old, '"version": "0.6.6"')

    if '"RG - Browser Upload Alert"' not in text:
        anchor = '        ("CPF - Browser Upload Block", "CPF", "CRITICAL", "BLOCK", "browser_upload", 5),\n'
        block = (
            '        ("RG - Browser Upload Alert", "RG_BR", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("Passport - Browser Upload Alert", "PASSPORT", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("CNH - Browser Upload Alert", "CNH_BR", "HIGH", "ALERT", "browser_upload", 20),\n'
            '        ("CNS - Browser Upload Alert", "CNS_BR", "CRITICAL", "ALERT", "browser_upload", 15),\n'
            '        ("Email - Browser Upload Alert", "EMAIL_ADDRESS", "MEDIUM", "ALERT", "browser_upload", 40),\n'
            '        ("Phone - Browser Upload Alert", "PHONE_BR", "MEDIUM", "ALERT", "browser_upload", 40),\n'
            '        ("Birth Date - Browser Upload Alert", "DATE_OF_BIRTH", "MEDIUM", "ALERT", "browser_upload", 40),\n'
            '        ("Physical Address - Browser Upload Alert", "PHYSICAL_ADDRESS", "MEDIUM", "ALERT", "browser_upload", 40),\n'
            '        ("Card Security Code - Browser Upload Block", "CARD_SECURITY_CODE", "CRITICAL", "BLOCK", "browser_upload", 1),\n'
            '        ("Card PIN - Browser Upload Block", "CARD_PIN", "CRITICAL", "BLOCK", "browser_upload", 1),\n'
            '        ("Card Track Data - Browser Upload Block", "CARD_TRACK_DATA", "CRITICAL", "BLOCK", "browser_upload", 1),\n'
        )
        text = replace_once(text, anchor, anchor + block, "browser upload sensitive-data policies")

    if '"Card Security Code - Messaging Block"' not in text:
        anchor = '        ("Card Data - Messaging Block", "CREDIT_CARD", "CRITICAL", "BLOCK", "messaging", 5),\n'
        block = (
            '        ("Card Security Code - Messaging Block", "CARD_SECURITY_CODE", "CRITICAL", "BLOCK", "messaging", 1),\n'
            '        ("Card PIN - Messaging Block", "CARD_PIN", "CRITICAL", "BLOCK", "messaging", 1),\n'
            '        ("Card Track Data - Messaging Block", "CARD_TRACK_DATA", "CRITICAL", "BLOCK", "messaging", 1),\n'
            '        ("RG - Messaging Alert", "RG_BR", "HIGH", "ALERT", "messaging", 25),\n'
            '        ("Passport - Messaging Alert", "PASSPORT", "HIGH", "ALERT", "messaging", 25),\n'
            '        ("CNH - Messaging Alert", "CNH_BR", "HIGH", "ALERT", "messaging", 25),\n'
            '        ("Email - Messaging Alert", "EMAIL_ADDRESS", "MEDIUM", "ALERT", "messaging", 40),\n'
            '        ("Phone - Messaging Alert", "PHONE_BR", "MEDIUM", "ALERT", "messaging", 40),\n'
        )
        text = replace_once(text, anchor, anchor + block, "messaging sensitive-data policies")

    if '"pii_bundle" in tags' not in text:
        anchor = '    if "high_value_extension" in tags:\n        score += 6\n        reasons.append("high_value_extension")\n'
        replacement = anchor + (
            '\n    if "pii_bundle" in tags:\n        score += 8\n        reasons.append("privacy:pii_bundle")\n'
            '    if "pii_profile" in tags:\n        score += 10\n        reasons.append("privacy:pii_profile")\n'
            '    if "special_category_linked_identity" in tags:\n        score += 18\n        reasons.append("privacy:special_category_linked_identity")\n'
            '    if "pci_account_plus_authentication" in tags:\n        score += 20\n        reasons.append("pci:account_plus_authentication")\n'
        )
        text = replace_once(text, anchor, replacement, "catalog risk signals")

    write("api/app.py", text)

def patch_versions():
    main = read("agent/main.go")
    found = False
    for old in ('const version = "0.6.5"', 'const version = "0.6.4.1"', 'const version = "0.6.4"'):
        if old in main:
            main = main.replace(old, 'const version = "0.6.6"', 1)
            found = True
            break
    if not found and 'const version = "0.6.6"' not in main:
        raise RuntimeError("agent version anchor not found")
    write("agent/main.go", main)

    dashboard = read("dashboard/index.html")
    for old in ("v0.6.5", "v0.6.4.1", "v0.6.4"):
        dashboard = dashboard.replace(old, "v0.6.6")
    write("dashboard/index.html", dashboard)

    launcher = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if launcher.exists():
        text = launcher.read_text(encoding="utf-8")
        for old in ("0.6.5", "0.6.4.1", "0.6.4"):
            text = text.replace(old, "0.6.6")
        launcher.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")

    manifest = ROOT / "browser-extension" / "manifest.json"
    if manifest.exists():
        text = manifest.read_text(encoding="utf-8")
        text = text.replace('"version": "0.6.5"', '"version": "0.6.6"')
        manifest.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] browser-extension/manifest.json")

def patch_changelog():
    text = read("CHANGELOG.md")
    if "## 0.6.6 - 2026-09-06" not in text:
        entry = '''## 0.6.6 - 2026-09-06

- Novo **Sensitive Data Catalog & Confidence Engine** baseado em LGPD/ANPD, NIST PII, GDPR, PCI DSS e práticas de DLP por confiança/evidência.
- Catálogo separa PII, linkable data, dado pessoal sensível, financeiro, payment card, credenciais/secrets e business data.
- CPF/CNPJ/PAN continuam independentes de palavra-chave quando checksum valida; contexto passa a elevar confiança, não ser requisito absoluto.
- Novos detectores: telefone BR formatado, data de nascimento contextual, nome completo contextual, endereço físico, IP/MAC contextuais, IMEI contextual+Luhn, placa BR, geolocalização contextual, CNH/PIS-NIS/título/CNS/matrículas/prontuário contextuais.
- PCI DSS: CVV/CVC/CID, PIN e track data entram como Sensitive Authentication Data e recebem BLOCK em canais externos.
- Novos sinais de correlação: `pii_bundle`, `pii_profile`, `special_category_linked_identity`, `pci_account_plus_authentication`.
- CEP permanece evidência auxiliar de endereço, não um detector PII independente.
- Classes sem detecção segura por regex (biometria, genética, raça/etnia, religião, política, sindicato, vida sexual/orientação, saúde clínica ampla) entram no catálogo como `semantic_required`, sem fingir cobertura.

'''
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        write("CHANGELOG.md", text)

def main():
    if "browser_upload" not in read("api/app.py"):
        raise RuntimeError("v0.6.5 Generic Browser Upload DLP must be applied first.")

    write("agent/sensitive_catalog.go", (HERE / "sensitive_catalog.go").read_text(encoding="utf-8"))
    write("agent/sensitive_catalog_test.go", (HERE / "sensitive_catalog_test.go").read_text(encoding="utf-8"))
    write("docs/SENSITIVE-DATA-CATALOG.md", (HERE / "SENSITIVE-DATA-CATALOG.md").read_text(encoding="utf-8"))

    patch_detectors()
    patch_context()
    patch_api()
    patch_versions()
    patch_changelog()

    print("")
    print("BSC DLP v0.6.6 Sensitive Data Catalog applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.6.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
