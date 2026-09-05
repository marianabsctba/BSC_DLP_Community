# BSC DLP v0.6.1 — Messaging + Host Time

- WhatsApp Desktop, Teams, Slack, Telegram e Discord: sensor Windows de clipboard + app em foreground.
- Não lê chats e não quebra E2EE.
- O clipboard bruto não é armazenado.
- BLOCK/QUARANTINE pode limpar o clipboard antes do paste.
- WhatsApp Web e upload de arquivos continuam fora da captura ativa.
- Horário: UTC no banco, `Z` explícito na API, horário local no dashboard/PDF/CSV.

Ordem:
1. APPLY-V0.6.1.cmd
2. TEST-V0.6.1.cmd
3. Reiniciar BSC DLP
4. TEST-WHATSAPP-DLP.cmd
