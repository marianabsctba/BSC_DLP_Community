# Changelog

## 0.5.4 - 2026-09-05

- Console administrativa agora é trilíngue: **Português, English e Español**, com seletor no login e na barra superior.
- Preferência de idioma do administrador é persistida localmente no navegador e aplicada sem reiniciar a console.
- PDF, CSV e visualização de impressão respeitam o idioma selecionado, incluindo títulos, filtros, KPIs, colunas, paginação e mensagens de privacidade.
- Mensagens de autenticação e erros administrativos comuns também recebem localização PT/EN/ES.
- Adicionados testes automatizados para os três idiomas e validação de sintaxe JavaScript no fluxo de CI.
- Relatórios agora são gerados como PDF real (`application/pdf`) pelo backend via ReportLab.
- Botão principal da console passa a baixar `bsc-dlp-report-*.pdf`; o antigo fluxo de impressão fica apenas como visualização secundária.
- PDF respeita os mesmos filtros da console e inclui KPIs, top classificações/canais/ações e tabela detalhada de eventos.
- Dados sensíveis não são incluídos em claro no PDF; a tabela usa metadados operacionais e nomes de objetos.
- Download de PDF no frontend ganhou tratamento de erro e feedback visual ao administrador.
- Build Windows inclui ReportLab no backend self-contained.
- Adicionado workflow de CI para testes Python/Go em push e pull request.
- Estrutura limpa e versionada como base GitHub-ready, sem DB, tokens, logs, secrets ou caches locais.

## 0.5.3 — 2026-09-05

- Fixed Python 3.10 startup failure in the printable HTML report (`f-string expression part cannot include a backslash`).
- Launcher now shows explicit startup stages instead of appearing frozen after `pip`.
- Python dependencies are installed only when `requirements.txt` changes.
- Disabled automatic OCR installation during normal START; missing OCR is reported clearly instead of blocking startup.
- Preserved the black/pink panther branding, favicon and Windows shortcut icon.

## 0.5.2 — 2026-09-05

- Nova identidade visual oficial preto + rosa com ícone da pantera BSC DLP.
- Ícone aplicado ao login, sidebar e favicon da console.
- Launcher cria/atualiza o atalho `BSC DLP Community` na Área de Trabalho com o ícone oficial.
- Launcher agora detecta conflito na porta 8000 e escolhe automaticamente a próxima porta livre em instalações locais.
- Falhas de inicialização exibem as últimas linhas do log do backend diretamente no terminal.
- Build Windows inclui os assets de marca e embute o ícone no executável do backend.
- Mantidos os filtros, paginação, relatórios, detectores customizados, OCR e enforcement da v0.5.x.

## 0.5.1 — 2026-09-05

- Botão **Sair** agora fica visível no topo da console administrativa, além da área Administração.
- Mantidos os filtros completos de Eventos, Incidentes e Relatórios: período, endpoint/usuário, classificação, canal, severidade, ação, bloqueio, texto livre e risco mínimo.
- Relatórios continuam exportáveis em CSV e em versão pronta para imprimir/salvar como PDF.
- Primeiro acesso continua obrigatório em instalações novas; upgrades preservam a conta administrativa existente no runtime local.
- Launcher atualizado para v0.5.1.

## 0.5.0 — 2026-09-05

- Motor de classificação ampliado: e-mail, RG, CEP, telefone, PIX, conta bancária, passaporte, credenciais e novos tipos de secret, além de CPF/CNPJ/cartão.
- Detectores customizados por regex RE2, criados pelo administrador e distribuídos automaticamente aos agentes.
- Nova área **Relatórios** com resumo, CSV e versão imprimível/salvável como PDF.
- Valores sensíveis permanecem mascarados/fingerprinted nos relatórios; CSV protegido contra formula injection.
- Eventos e incidentes ganharam filtros por período, endpoint/usuário, classificação, canal, severidade, ação, bloqueio, texto e risco mínimo.
- Paginação de 10/25/50/100 itens para evitar tabelas infinitas e melhorar desempenho da console.
- Novos endpoints paginados `/events/query` e `/incidents/query`, preservando compatibilidade com os endpoints anteriores.
- Relatórios e detectores customizados permanecem restritos à sessão administrativa.
- Testes de integração ampliados para filtros, relatórios e distribuição de regras customizadas.

## 0.4.2 — 2026-09-05

- Corrigida detecção de imagens baixadas por navegador em `Downloads`.
- O agente agora espera o arquivo estabilizar antes da inspeção, evitando OCR em arquivos ainda incompletos.
- Renames de browser (`.crdownload`/temporários → arquivo final) acionam rescan recente da pasta para não perder PNG/JPG/PDF finalizados.
- OCR de imagem agora tenta idiomas configuráveis e faz fallback `por+eng` → `eng` quando o pacote português não está disponível.
- Descoberta do Tesseract ampliada para PATH, Program Files, Program Files (x86) e LocalAppData.
- Source One-Click tenta instalar Tesseract via `winget` quando OCR não está disponível; pode ser desabilitado com `BSC_DLP_SKIP_OCR_BOOTSTRAP=1`.
- Adicionado `TEST-OCR-DOWNLOAD.cmd`, que gera um PNG de laboratório com CPF de teste em Downloads para validar o fluxo ponta a ponta.
- Adicionados testes do pipeline `download PNG → OCR → CPF → policy/event` e do rescan pós-download.

## 0.4.1 — 2026-09-05

- Interface da console simplificada para uso administrativo, sem notas internas de desenvolvimento.
- Textos e rótulos da console padronizados em português.
- Suíte de regressão ampliada para autenticação, enrollment, políticas, eventos, risco e revogação.
- Testes de integração do backend adicionados ao repositório.

## 0.4.0 — 2026-09-05

- Nova console administrativa preto + rosa.
- Primeiro acesso com criação do administrador; usuários de endpoint não possuem acesso à console.
- Senha administrativa armazenada com derivação `scrypt` + salt.
- Sessões administrativas via cookie HttpOnly / SameSite Strict.
- APIs de endpoints, policies, eventos, incidents e stats agora exigem admin.
- Credenciais Bearer dos agents permanecem separadas das credenciais administrativas.
- Botão **Adicionar endpoint** agora gera enrollment token temporário, expirável e de uso limitado.
- Adicionado `INSTALL-ENDPOINT.cmd` para enrollment e instalação por usuário no Windows.
- Adicionado `UNINSTALL-ENDPOINT.cmd`.
- Adicionado modo `START-BSC-DLP-LAN.cmd` para laboratório com endpoints remotos.
- Novo Behavior Risk Engine com score 0–100 e priorização de incidentes.
- Endpoint risk agregado das últimas 24h.
- Suporte documental: PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON, XML, LOG, MD, INI, CONF, YAML/YML.
- PDF usa `pdftotext` quando disponível, parser interno best-effort e OCR fallback com `pdftoppm + Tesseract`.
- OCR de imagens mantido.
- Novos classificadores: CNPJ checksum, cartão/Luhn e secrets básicos, além de CPF checksum.
- `BLOCK`/`QUARANTINE` agora executam enforcement real no endpoint por quarentena + remoção do objeto original.
- Eventos só registram `blocked=true` após enforcement bem-sucedido.
- Quarentena funciona entre volumes (importante para USB).
- Policies default de screenshot/removable atualizadas para BLOCK.
- Upgrade automático das policies v0.3 equivalentes para BLOCK.
- Tipo do documento, risk score e tipo de incidente adicionados à telemetria.
- Testes adicionados para CNPJ/Luhn, OpenXML, PDF built-in e endpoint quarantine.
- Bloqueio pre-write kernel não é alegado; requer futuro Windows minifilter assinado.

## 0.3.0 — 2026-09-05

- Community local-first, one-click Windows, Known Folders, USB/removable, OCR de screenshot, enrollment/token, dashboard e build self-contained.

## 0.2.0 — 2026-09-05

- Primeiro port do agente para Windows preservando Linux.
