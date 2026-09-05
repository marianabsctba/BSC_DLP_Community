# BSC DLP v0.6.3 — Evasion-Resistant Detection Engine

A melhoria vale para filesystem, download, USB, screenshot, clipboard/messaging e WhatsApp Web.

Principais mudanças:
- normalização local/bounded de identificadores;
- `#`, `|`, `_`, símbolos, múltiplos espaços e zero-width;
- dígitos Unicode comuns;
- números por extenso em PT/EN/ES quando há contexto explícito;
- checksum CPF/CNPJ e Luhn continuam sendo a decisão de alta confiança;
- `CPF_LIKE` para identificador mutilado em contexto explícito;
- tags de evasão entram no risk score;
- telefone deixa de ser detector nativo prioritário;
- nunca concatena todos os números do documento.

Ordem:
1. `APPLY-V0.6.3.cmd`
2. `TEST-V0.6.3.cmd`
3. Reiniciar BSC DLP.
4. Em `chrome://extensions` / `edge://extensions`, clicar Reload na extensão BSC DLP Browser Guard.
5. Testar com os exemplos sintéticos em `RODRIGO-TESTS-V0.6.3.md`.
