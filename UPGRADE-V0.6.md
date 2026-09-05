# BSC DLP v0.6.0 — Context + Messaging Foundations

Este pacote atualiza a `main` local sem criar branch ou commit.

Principais mudanças:
- CEP deixa de ser detector nativo.
- Co-occurrence, bulk/mass data e filename sensitivity.
- Risk score explicável (`risk_reasons`).
- Correlação de incidentes em janela de 5 minutos.
- Console passa a exibir incidentes correlacionados.
- `risk-preview` para simular cenário sem gravar evento.
- Fundamentos de `clipboard`, `messaging`, `email` e `ai`.
- WhatsApp/Teams/Slack/Telegram/Discord são modelados como destinos futuros.
- NÃO há alegação de interceptação ativa de mensagens nesta versão.

Como aplicar:
1. Extrair este ZIP na raiz do repositório.
2. Executar `APPLY-V0.6.cmd`.
3. Executar `TEST-V0.6.cmd`.
4. Executar `START-BSC-DLP.cmd`.
5. Só depois revisar `git status` / `git diff` e commitar.
