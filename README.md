# BSC DLP Community Edition

Open-source Data Loss Prevention para Windows/Linux, com agente em Go, console administrativa FastAPI, SQLite, políticas por canal, classificação local de documentos, risk engine e enforcement de endpoint.

## v0.5.4 - GitHub Ready + PDF Reporting + PT/EN/ES

A v0.5.4 é a base **GitHub-ready** do projeto. A console administrativa é trilíngue (**Português, English e Español**) e lembra a preferência do administrador. O relatório administrativo é gerado como **PDF real** pelo backend, respeitando filtros e idioma da console; CSV e visualização de impressão seguem a mesma preferência. O PDF inclui métricas, distribuição por classificação/canal/ação e tabela detalhada sem expor valores sensíveis em claro.

A Community Edition foi desenhada para ser simples para dois públicos diferentes:

- **Administrador:** inicia a console, cria a conta admin no primeiro acesso, define policies, acompanha risco/incidentes e gera códigos temporários de enrollment.
- **Usuário do endpoint:** instala somente o Agent. Não recebe login, senha ou acesso aos dados da console.

A identidade visual oficial da console é **preto + rosa**, com o ícone da pantera BSC DLP. No Windows, o primeiro start cria/atualiza um atalho na Área de Trabalho usando a marca oficial.

Se a porta `8000` já estiver ocupada no modo local, o launcher escolhe automaticamente a próxima porta livre e abre a console no endereço correto.


### Idiomas

O seletor de idioma aparece na tela de login e na barra superior da console. A escolha fica armazenada localmente no navegador do administrador e pode ser alterada a qualquer momento:

- Português (`pt`)
- English (`en`)
- Español (`es`)

PDF, CSV e visualização de impressão usam automaticamente o idioma selecionado. Constantes técnicas como `BLOCK`, `AUDIT`, nomes de classificadores e canais permanecem estáveis para facilitar investigação e integração.

## Começar no Windows

### Teste local / laboratório

1. Extraia a release.
2. Execute `START-BSC-DLP.cmd`.
3. O navegador abre a console.
4. No primeiro acesso, crie o administrador.
5. O endpoint local é iniciado automaticamente.

Para parar: `STOP-BSC-DLP.cmd`.

Para zerar DB, credenciais e configuração local: `RESET-BSC-DLP.cmd`.

### Console central para endpoints da LAN

Execute `START-BSC-DLP-LAN.cmd`. A API passa a escutar nas interfaces de rede. Use apenas em rede confiável para laboratório; para produção, publique a console atrás de TLS/reverse proxy.

Na console, clique em **Adicionar endpoint**, gere um código temporário e, no pacote copiado para o endpoint, execute:

```powershell
.\INSTALL-ENDPOINT.cmd "http://SERVIDOR:8000" "CODIGO-DE-ENROLLMENT"
```

O instalador registra o endpoint, salva somente o token individual do agente e configura inicialização no logon do usuário. Ele não cria credenciais de console.

## O que funciona

### Console administrativa

- Primeiro acesso com criação de um único administrador.
- Senha derivada com `scrypt`; valor em texto puro não é armazenado.
- Sessão administrativa via cookie HttpOnly / SameSite Strict.
- Endpoints, policies, eventos, incidents e stats protegidos por autenticação administrativa.
- Endpoint agent usa autenticação Bearer separada e não pode consultar dados administrativos.
- Enrollment temporário de uso limitado gerado pelo admin.
- Revogação da credencial do endpoint.

### Behavior / Risk

O backend calcula risco por evento considerando severidade, canal, ação e burst recente. USB/removable, screenshot, email/AI (quando os canais forem ativados) e repetição em poucos minutos aumentam o score.

Eventos com `risk_score >= 40` aparecem como incidentes priorizados.

### Document DLP

Extração ocorre **no endpoint**. O documento bruto não é enviado para a console.

- PDF: `pdftotext` quando disponível, parser interno best-effort e OCR para PDF escaneado quando `pdftoppm + Tesseract` estão disponíveis.
- DOCX: extração OpenXML local.
- XLSX: worksheets/shared strings OpenXML.
- PPTX: slides/notes OpenXML.
- TXT, CSV, JSON, XML, LOG, MD, INI, CONF, YAML/YML.
- Imagens: PNG, JPG/JPEG, TIFF, BMP, WEBP via Tesseract. No Windows Source One-Click, o launcher procura o OCR automaticamente e tenta bootstrap via `winget` quando necessário. O agente usa fallback `por+eng` → `eng`.

### Classificadores atuais

- CPF e CNPJ com checksum.
- Cartão com validação Luhn.
- E-mail.
- RG, CEP, telefone, PIX, conta bancária e passaporte com detecção contextual.
- Credenciais: password/senha, Bearer tokens e padrões de autenticação.
- Secrets: AWS, GitHub, Google API, Slack, JWT, private keys e assignments de secrets.
- Regras customizadas pelo administrador usando regex compatível com RE2; os agentes atualizam essas regras automaticamente.

A console recebe masked value, fingerprint SHA-256, hash do objeto, tipo de documento, canal e evidência — não o valor sensível em claro.

### Canais atuais

- `filesystem`
- `download`
- `screenshot`
- `removable` / USB

Windows descobre Known Folders reais via `SHGetKnownFolderPath`, respeitando localização, OneDrive e Known Folder Move. Downloads de navegador recebem tratamento de settle/rename para que arquivos temporários finalizados não escapem da inspeção.

## Filtros, paginação e relatórios

A console evita listas infinitas de telemetria. Eventos e incidentes podem ser filtrados por período, endpoint/usuário, classificação, canal, severidade, ação, bloqueio e risco mínimo, com 10/25/50/100 registros por página.

A área **Relatórios** oferece:

- resumo de eventos, incidentes, bloqueios, endpoints e risco máximo;
- distribuição por classificação e canal;
- exportação CSV com valores sensíveis mascarados e proteção contra CSV/Excel formula injection;
- relatório imprimível pelo navegador, pronto para **Salvar como PDF**;
- limite operacional de até 10.000 eventos por exportação para proteger a console local.

## Detectores customizados

O administrador pode criar uma classificação própria informando nome, classificação e regex compatível com RE2. A regra é armazenada na console e distribuída aos agentes autenticados. Exemplo: `CONTRATO-[0-9]{8}` com classificação `CONTRACT_ID`. Se não existir policy específica, a classificação cai em `AUDIT` por padrão.

## BLOCK de verdade — o que v0.4 faz

Policies `BLOCK` e `QUARANTINE` agora executam enforcement no endpoint.

Quando um objeto sensível é detectado, o agente copia o arquivo para a quarentena local protegida e remove o original. Isso funciona inclusive entre volumes, como USB → disco local. O evento registra `blocked=true` somente quando o enforcement realmente terminou com sucesso.

Por padrão, screenshot e removable media com CPF são policies de `BLOCK`.

### Limite técnico declarado

A v0.4 faz **bloqueio reativo após o write ser observado**. Ela não afirma bloquear o write antes de chegar ao filesystem.

Bloqueio pré-I/O no Windows exige um **minifilter driver assinado**. Esse é um módulo de enforcement separado para uma versão futura. O projeto não declara capacidade kernel que ainda não existe.

## Arquitetura

```text
                        ADMIN ONLY
                    ┌─────────────────┐
                    │ BSC DLP Console │
                    │ login / risk    │
                    │ incidents       │
                    │ policies        │
                    │ enrollment      │
                    └────────┬────────┘
                             │
                        FastAPI/SQLite
                             │
             authenticated agent API
                             │
          ┌──────────────────┴──────────────────┐
          │                                     │
   Windows Endpoint                       Linux Endpoint
   BSC DLP Agent                          BSC DLP Agent
          │
   ┌──────┼────────┬──────────┐
   │      │        │          │
 files  downloads  USB     screenshots
   │      │        │          │
   └──────┴────┬───┴──────────┘
               │
       Local extraction/OCR
               │
         classifiers
               │
         policy resolve
               │
      audit / alert / block
               │
       endpoint quarantine
```

## Runtime local

Console local:

`%LOCALAPPDATA%\BSC-DLP-Community`

Endpoint instalado:

`%LOCALAPPDATA%\BSC-DLP-Endpoint`

A quarentena fica dentro do runtime do endpoint/console e não dentro da pasta da aplicação.

## Testes

Backend/API:

```powershell
python -m pip install -r requirements-dev.txt
pytest -q
```

Teste manual de OCR em Downloads:

```powershell
.\TEST-OCR-DOWNLOAD.cmd
```

O teste cria `bsc-dlp-ocr-cpf-test.png` em Downloads com um CPF fictício válido para checksum. O esperado é evento `channel=download`, `document_type=png` e evidência `image_ocr`.

Agente Go:

```powershell
cd agent
go test ./...
```


## Build para comunidade

A release binária Windows é construída por:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Build-Community-Release.ps1 -Version 0.5.4
```

O workflow `.github/workflows/windows-release.yml` compila o agente Go e empacota o backend com PyInstaller. O usuário da release final não precisa instalar Python ou Go.

## Próximos módulos

- Windows minifilter para pre-write enforcement.
- Device Control avançado: VID/PID/serial, allowlist, read-only e policy por dispositivo.
- Email DLP.
- AI DLP / AI Gateway para prompts e uploads.
- Packs adicionais de classificadores e templates de políticas.
- RBAC multi-admin para ambientes maiores.

## Licença

MIT. Veja `LICENSE`.
