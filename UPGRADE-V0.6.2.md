# BSC DLP v0.6.2 — WhatsApp Web Browser Guard

## O que entra
- Extensão Chromium Manifest V3 para **WhatsApp Web**.
- Chrome e Edge por carregamento `unpacked`.
- Inspeção apenas do conteúdo de saída do composer:
  - paste;
  - Enter para enviar;
  - clique no botão enviar.
- O conteúdo vai somente para `127.0.0.1:8765`, onde o **agente Go local** reutiliza os mesmos detectores e políticas.
- Eventos:
  - `channel=messaging`
  - `destination=whatsapp_web`
- `BLOCK`/`QUARANTINE` impede paste/envio.
- `ALERT` registra e permite.
- Texto bruto não é persistido.
- Histórico de chat não é lido.

## Limite desta versão
Upload de arquivos pelo WhatsApp Web ainda não é captura ativa. PDF/imagem/Office precisam passar pelo extrator local; isso será uma camada separada.

## Ordem
1. Extrair na raiz do repo.
2. `APPLY-V0.6.2.cmd`
3. `TEST-V0.6.2.cmd`
4. Reiniciar o BSC DLP.
5. `TEST-BROWSER-BRIDGE.cmd`
6. `INSTALL-BROWSER-EXTENSION.cmd`
7. Abrir WhatsApp Web e testar primeiro com dado de TESTE.
