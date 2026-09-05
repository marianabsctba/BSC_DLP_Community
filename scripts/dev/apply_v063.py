#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

def load(rel):
    p = ROOT / rel
    if not p.exists():
        raise RuntimeError(f"Required file not found: {rel}")
    return p.read_text(encoding="utf-8")

def save(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"[updated] {rel}")

def replace_once(text, old, new, label, required=True):
    if new in text:
        print(f"[skip] {label}: already applied")
        return text
    count = text.count(old)
    if count != 1:
        if required:
            raise RuntimeError(f"{label}: expected 1 exact match, found {count}")
        print(f"[skip] {label}: source pattern not found")
        return text
    return text.replace(old, new, 1)

def install_sources():
    for name in ("evasion.go", "evasion_test.go"):
        save(f"agent/{name}", (HERE / name).read_text(encoding="utf-8"))

def patch_detectors():
    text = load("agent/detectors.go")
    text = text.replace('var phoneContextRegex = regexp.MustCompile(`(?i)(?:telefone|fone|celular|mobile|whatsapp|contato)\\s*[:#-]?\\s*((?:\\+?55\\s*)?\\(?[1-9][0-9]\\)?[\\s.-]?(?:9?[0-9]{4})[\\s.-]?[0-9]{4})`)\n', "", 1)
    anchor = "\tfor _, value := range cpfRegex.FindAllString(text, 100) {\n"
    injection = "\tfor _, detection := range detectEvasiveIdentifiers(text) {\n\t\tadd(detection.Classification, detection.Value, detection.Evidence)\n\t}\n\n\tfor _, value := range cpfRegex.FindAllString(text, 100) {\n"
    if "detectEvasiveIdentifiers(text)" not in text:
        text = replace_once(text, anchor, injection, "anti-evasion detector hook")
    phone_block = "\tfor _, value := range captureMatches(phoneContextRegex, text, 1, 100) {\n\t\tadd(\"PHONE_BR\", value, \"phone_context\")\n\t}\n"
    text = text.replace(phone_block, "", 1)
    save("agent/detectors.go", text)

def patch_context():
    text = load("agent/context.go")
    old = "\ttags := []string{}\n\tif len(classes) >= 2 {\n\t\ttags = append(tags, \"co_occurrence\")\n\t}\n\tif len(detections) >= 10 {\n\t\ttags = append(tags, \"bulk_data\")\n\t}\n\tif len(detections) >= 50 {\n\t\ttags = append(tags, \"mass_data\")\n\t}\n\tif len(signals) > 0 {\n\t\ttags = append(tags, \"sensitive_filename\")\n\t}\n\thighValue := highValueExtensions[strings.ToLower(filepath.Ext(path))]\n\tif highValue {\n\t\ttags = append(tags, \"high_value_extension\")\n\t}\n\tsort.Strings(tags)\n"
    new = "\ttagSet := map[string]bool{}\n\taddTag := func(tag string) {\n\t\ttag = strings.TrimSpace(strings.ToLower(tag))\n\t\tif tag != \"\" { tagSet[tag] = true }\n\t}\n\n\tif len(classes) >= 2 { addTag(\"co_occurrence\") }\n\tif len(detections) >= 10 { addTag(\"bulk_data\") }\n\tif len(detections) >= 50 { addTag(\"mass_data\") }\n\tif len(signals) > 0 { addTag(\"sensitive_filename\") }\n\thighValue := highValueExtensions[strings.ToLower(filepath.Ext(path))]\n\tif highValue { addTag(\"high_value_extension\") }\n\n\tfor _, detection := range detections {\n\t\tevidence := strings.ToLower(detection.Evidence)\n\t\tif strings.Contains(evidence, \"obfuscated_identifier\") { addTag(\"obfuscated_identifier\") }\n\t\tif strings.Contains(evidence, \"evasive_obfuscation\") { addTag(\"evasive_obfuscation\") }\n\t\tif strings.Contains(evidence, \"malformed_identifier\") { addTag(\"malformed_identifier\") }\n\t\tif strings.Contains(evidence, \"embedded_identifier\") { addTag(\"embedded_identifier\") }\n\t}\n\n\ttags := make([]string, 0, len(tagSet))\n\tfor tag := range tagSet { tags = append(tags, tag) }\n\tsort.Strings(tags)\n"
    if "addTag(\"evasive_obfuscation\")" not in text:
        text = replace_once(text, old, new, "context anti-evasion tags")
    save("agent/context.go", text)

def patch_go_tests():
    p = ROOT / "agent" / "v05_test.go"
    if p.exists():
        text = p.read_text(encoding="utf-8").replace('\t\t"PHONE_BR":      false,\n', "", 1)
        p.write_text(text, encoding="utf-8", newline="\n")
        print("[updated] agent/v05_test.go")

def patch_versions():
    text = load("agent/main.go").replace('const version = "0.6.2"', 'const version = "0.6.3"', 1)
    save("agent/main.go", text)
    text = load("dashboard/index.html").replace("v0.6.2", "v0.6.3")
    save("dashboard/index.html", text)
    p = ROOT / "scripts" / "windows" / "Start-Community.ps1"
    if p.exists():
        p.write_text(p.read_text(encoding="utf-8").replace("0.6.2", "0.6.3"), encoding="utf-8", newline="\n")
        print("[updated] scripts/windows/Start-Community.ps1")
    p = ROOT / "browser-extension" / "manifest.json"
    if p.exists():
        p.write_text(p.read_text(encoding="utf-8").replace('"version": "0.6.2"', '"version": "0.6.3"', 1), encoding="utf-8", newline="\n")
        print("[updated] browser-extension/manifest.json")

def patch_backend():
    text = load("api/app.py")
    text = text.replace('version="0.6.2"', 'version="0.6.3"', 1)
    text = text.replace('"version": "0.6.2"', '"version": "0.6.3"', 1)
    if '"CPF-like - Messaging Alert"' not in text:
        old = '        ("CPF - Messaging Alert", "CPF", "HIGH", "ALERT", "messaging", 25),\n'
        new = old + '        ("CPF-like - Messaging Alert", "CPF_LIKE", "HIGH", "ALERT", "messaging", 30),\n'
        text = replace_once(text, old, new, "CPF_LIKE messaging policy", required=False)
    risk_anchor = '    if "high_value_extension" in tags:\n        score += 6\n        reasons.append("high_value_extension")\n'
    risk_new = risk_anchor + '\n    if "evasive_obfuscation" in tags:\n        score += 10\n        reasons.append("evasion:strong")\n    elif "obfuscated_identifier" in tags:\n        score += 5\n        reasons.append("evasion:obfuscated")\n    if "malformed_identifier" in tags:\n        score += 8\n        reasons.append("evasion:malformed_identifier")\n'
    if 'reasons.append("evasion:strong")' not in text:
        text = replace_once(text, risk_anchor, risk_new, "risk anti-evasion scoring")
    text = text.replace('"optional_custom_examples": ["CEP_BR"],', '"optional_custom_examples": ["CEP_BR", "PHONE_BR"],', 1)
    text = text.replace('            "CPF", "CNPJ", "CREDIT_CARD", "EMAIL_ADDRESS", "RG_BR", "PHONE_BR",\n', '            "CPF", "CPF_LIKE", "CNPJ", "CREDIT_CARD", "EMAIL_ADDRESS", "RG_BR",\n', 1)
    if '"anti_evasion"' not in text:
        marker = '        "optional_custom_examples": ["CEP_BR", "PHONE_BR"],\n'
        block = '        "anti_evasion": {\n            "separator_normalization": True,\n            "zero_width_detection": True,\n            "unicode_digits": True,\n            "number_words": ["pt", "en", "es"],\n            "validated_checksums": ["CPF", "CNPJ", "CREDIT_CARD"],\n            "malformed_cpf_context": True,\n            "whole_document_digit_collapse": False,\n        },\n'
        text = replace_once(text, marker, block + marker, "anti-evasion capabilities")
    save("api/app.py", text)

def patch_changelog():
    text = load("CHANGELOG.md")
    if "## 0.6.3 - 2026-09-05" not in text:
        entry = "## 0.6.3 - 2026-09-05\n\n- Novo **Evasion-Resistant Detection Engine** para identificadores sensíveis.\n- CPF/CNPJ/cartão passam por extração local de candidatos + normalização limitada + checksum/Luhn.\n- Detecta separadores incomuns (`#`, `|`, `_`, símbolos), espaçamento excessivo, quebras e caracteres zero-width.\n- Detecta dígitos Unicode comuns e converte para forma canônica antes da validação.\n- Detecta CPF/CNPJ/cartão escritos com números por extenso em PT/EN/ES quando existe contexto explícito.\n- `CPF_LIKE` sinaliza CPF mutilado (10/12 dígitos ou checksum inválido) somente quando existe contexto forte de CPF; padrão em mensageria é ALERT.\n- Novas tags de risco: `obfuscated_identifier`, `evasive_obfuscation`, `malformed_identifier`, `embedded_identifier`.\n- Evasão forte e identificadores malformados aumentam o risk score explicável.\n- `PHONE_BR` deixa de ser classificador nativo e passa a ser exemplo opcional/custom, assim como CEP.\n- O motor **não concatena todos os números de um documento**; a normalização é limitada a janelas locais para reduzir falsos positivos.\n\n"
        text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1)
        save("CHANGELOG.md", text)

def main():
    if not (ROOT / "agent" / "browser_bridge.go").exists():
        raise RuntimeError("v0.6.2 not found. Apply/pull v0.6.2 first.")
    install_sources()
    patch_detectors()
    patch_context()
    patch_go_tests()
    patch_versions()
    patch_backend()
    patch_changelog()
    print("")
    print("BSC DLP v0.6.3 Evasion-Resistant Detection upgrade applied.")
    print("No commit was created.")
    print("Run TEST-V0.6.3.cmd.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
