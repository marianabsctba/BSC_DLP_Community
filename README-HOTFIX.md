# BSC DLP v0.6.6.1 — Browser Guard Restore

Hotfix cirúrgico para restaurar o código do Generic Browser Upload DLP no `browser-extension/content.js`
e o roteamento de upload no `service-worker.js`.

Não altera o backend nem o agente v0.6.6.

Após aplicar:
1. Rode `TEST-HOTFIX-V0.6.6.1.cmd`.
2. Em `chrome://extensions`, recarregue o BSC DLP Browser Guard.
3. Atualize a página de teste e selecione novamente `BSC-DLP-PII-V066.txt`.
