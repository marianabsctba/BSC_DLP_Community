# BSC DLP v0.6.5 — Generic Browser Upload DLP

## O que entrou
- Browser Guard agora roda em páginas HTTP/HTTPS.
- Intercepta `input[type=file]`, drag & drop e paste de arquivos/imagens.
- Arquivo é enviado em chunks somente ao bridge local em `127.0.0.1:8765`.
- Bridge remonta arquivo temporário, reutiliza extração/OCR/detecção/policies e apaga o temporário.
- Novo canal `browser_upload`, com hostname de destino no evento.
- Limite atual: 25 MiB por arquivo.
- `.env`, `.pem`, `.key` e `.sql` passam a ser tratados como texto para inspeção.
- WhatsApp Web text guard continua funcionando.

## Limites honestos
- O Browser Guard usa interceptação DOM. Alguns apps web muito customizados podem exigir integração específica.
- Tipos ainda não suportados ficam fail-open com aviso.
- ZIP/7z/encrypted archives ainda não entram nesta versão.
- Arquivos nunca são enviados para o backend para análise; a inspeção de conteúdo ocorre no endpoint.

## Ordem
1. `APPLY-V0.6.5.cmd`
2. `TEST-V0.6.5.cmd`
3. Reiniciar BSC DLP.
4. Recarregar a extensão unpacked.
5. `TEST-BRIDGE-UPLOAD-V0.6.5.cmd`
6. `TEST-BROWSER-UPLOAD-V0.6.5.cmd`
