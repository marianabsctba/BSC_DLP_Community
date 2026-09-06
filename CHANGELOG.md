# Changelog

## 0.6.6.3 - 2026-09-06

- Browser Guard Presence Watch para Chrome, Edge e Firefox.
- A extensão envia heartbeat local periódico ao bridge do agente.
- O agente verifica se o navegador está em execução e alerta quando o heartbeat da extensão desaparece.
- Novo evento `BROWSER_GUARD_DISABLED_OR_MISSING` em `channel=browser_guard`, severidade HIGH e ação ALERT.
- Novo evento `BROWSER_GUARD_RESTORED` quando a proteção retorna.
- Anti-spam por transição de estado: um alerta por perda, um evento por restauração.
- Navegador fechado não é tratado como extensão desabilitada.
- Edge/Chrome usam MV3 service worker; Firefox mantém `background.scripts` compatibility path.
- Browser Upload e Browser Guard adicionados aos filtros de canal do dashboard.

## 0.6.6 - 2026-09-06

- Novo **Sensitive Data Catalog & Confidence Engine** baseado em LGPD/ANPD, NIST PII, GDPR, PCI DSS e práticas de DLP por confiança/evidência.
- Catálogo separa PII, linkable data, dado pessoal sensível, financeiro, payment card, credenciais/secrets e business data.
- CPF/CNPJ/PAN continuam independentes de palavra-chave quando checksum valida; contexto passa a elevar confiança, não ser requisito absoluto.
- Novos detectores: telefone BR formatado, data de nascimento contextual, nome completo contextual, endereço físico, IP/MAC contextuais, IMEI contextual+Luhn, placa BR, geolocalização contextual, CNH/PIS-NIS/título/CNS/matrículas/prontuário contextuais.
- PCI DSS: CVV/CVC/CID, PIN e track data entram como Sensitive Authentication Data e recebem BLOCK em canais externos.
- Novos sinais de correlação: `pii_bundle`, `pii_profile`, `special_category_linked_identity`, `pci_account_plus_authentication`.
- CEP permanece evidência auxiliar de endereço, não um detector PII independente.
- Classes sem detecção segura por regex (biometria, genética, raça/etnia, religião, política, sindicato, vida sexual/orientação, saúde clínica ampla) entram no catálogo como `semantic_required`, sem fingir cobertura.

## 0.6.5 - 2026-09-05

- Novo **Generic Browser Upload DLP** no BSC DLP Browser Guard.
- A extensão passa a observar seletores de arquivo, drag & drop e paste de arquivo/imagem em páginas HTTP/HTTPS.
- Arquivos são enviados em chunks apenas para o bridge local `127.0.0.1:8765`; o conteúdo não sai do endpoint para inspeção.
- O bridge reconstrói um arquivo temporário local, reutiliza os extratores/OCR existentes e apaga o temporário ao final.
- Novo canal `browser_upload` com destino igual ao hostname da página e `destination_trust=external`.
- Policies padrão: CPF/cartão/secrets/credenciais em BLOCK; CPF-like/CNPJ/dados bancários/PIX em ALERT.
- Extensões textuais sensíveis `.env`, `.pem`, `.key` e `.sql` entram no pipeline de extração textual.
- WhatsApp Web text guard continua ativo e separado do pipeline de upload.
- Limite atual por arquivo: 25 MiB. Tipos ainda não suportados ficam fail-open com aviso; ZIP/7z/encrypted archives ficam para a próxima camada.
- Limite técnico: interceptação DOM é best-effort; aplicações web que processam arquivos fora dos eventos DOM convencionais podem exigir integração específica.

## 0.6.4.1 - 2026-09-05

- Hotfix do OCR de screenshots no clipboard Windows.
- Corrige falha `pixReadMemBmp: cannot read compressed BMP files` observada com `CF_DIBV5`.
- O sensor agora prioriza `CF_BITMAP` e usa GDI `GetDIBits` para normalizar a captura para BMP 24-bit `BI_RGB` antes do Tesseract.
- DIB/DIBV5 permanece apenas como fallback seguro quando já estiver em formato não comprimido.
- Nenhuma imagem bruta é enviada ao backend; o BMP temporário continua sendo removido após OCR.

## 0.6.4 - 2026-09-05

- Novo **Windows Clipboard Screenshot OCR Sensor**.
- Imagens que chegam ao clipboard via captura de tela (incluindo fluxo `Win+Shift+S`) são convertidas temporariamente de DIB/DIBV5 para BMP e inspecionadas localmente por OCR.
- A imagem bruta não é enviada ao backend e o BMP temporário é removido imediatamente após o OCR.
- Eventos usam `channel=screenshot`, `destination=clipboard` e `document_type=clipboard_image`.
- Políticas `BLOCK`/`QUARANTINE` no canal screenshot podem limpar a imagem sensível do clipboard após a detecção.
- Novas políticas padrão de screenshot: CPF/cartão/segredos/credenciais com proteção forte; CPF-like/CNPJ/banking/PIX em ALERT.
- Capturas salvas em arquivo continuam usando o sensor de filesystem/screenshot já existente.
- Limite honesto: a v0.6.4 **não bloqueia o ato de capturar pixels antes da captura**; ela protege o artefato quando ele chega ao clipboard ou ao filesystem.

## 0.6.3 - 2026-09-05

- Novo **Evasion-Resistant Detection Engine** para identificadores sensíveis.
- CPF/CNPJ/cartão passam por extração local de candidatos + normalização limitada + checksum/Luhn.
- Detecta separadores incomuns (`#`, `|`, `_`, símbolos), espaçamento excessivo, quebras e caracteres zero-width.
- Detecta dígitos Unicode comuns e converte para forma canônica antes da validação.
- Detecta CPF/CNPJ/cartão escritos com números por extenso em PT/EN/ES quando existe contexto explícito.
- `CPF_LIKE` sinaliza CPF mutilado (10/12 dígitos ou checksum inválido) somente quando existe contexto forte de CPF; padrão em mensageria é ALERT.
- Novas tags de risco: `obfuscated_identifier`, `evasive_obfuscation`, `malformed_identifier`, `embedded_identifier`.
- Evasão forte e identificadores malformados aumentam o risk score explicável.
- `PHONE_BR` deixa de ser classificador nativo e passa a ser exemplo opcional/custom, assim como CEP.
- O motor **não concatena todos os números de um documento**; a normalização é limitada a janelas locais para reduzir falsos positivos.

## 0.6.2 - 2026-09-05

- Novo Browser Guard MV3 para WhatsApp Web em Chrome/Edge.
- Extensão inspeciona somente conteúdo de saída do composer: paste, clique em enviar e Enter.
- A extensão não lê histórico de chats e não persiste texto bruto.
- Bridge local no agente (`127.0.0.1:8765`) reutiliza o mesmo detector, classificador e motor de políticas do endpoint.
- Eventos usam `channel=messaging` e `destination=whatsapp_web`.
- Políticas BLOCK/QUARANTINE impedem o paste/envio antes da ação do WhatsApp Web.
- Em indisponibilidade do bridge local, o comportamento padrão é fail-open com aviso visual.
- Upload de arquivos pelo navegador ainda não é captura ativa nesta versão.

## 0.6.1 - 2026-09-05

- Windows Messaging Clipboard Sensor para WhatsApp Desktop, Teams, Slack, Telegram e Discord.
- Inspeção local do clipboard somente quando um app de mensageria reconhecido está em foreground.
- Conteúdo bruto do clipboard não é persistido; somente valores mascarados/fingerprinted.
- Políticas BLOCK/QUARANTINE no canal messaging podem limpar o clipboard antes do paste.
- PII/banking em ALERT por padrão; cartão/segredos/credenciais em BLOCK para mensageria.
- Não lê mensagens, não quebra E2EE e não intercepta chats.
- WhatsApp Web e upload de arquivos ainda não são captura ativa nesta versão.
- Timestamps corrigidos: API emite UTC com Z explícito e a console converte para o horário local do host/browser.
- PDF/CSV exibem horário local do host.
- /api/v1/health informa server_time_utc e server_time_local.

## 0.6.0 - 2026-09-05

- Novo **Context-Aware DLP Engine** com co-occurrence, volume, nomes/extensões sensíveis e destination trust.
- CEP removido dos detectores nativos; continua possível como detector customizado.
- Risk score passa a ser explicável por `risk_reasons`.
- Incidentes recebem `incident_key` e podem ser correlacionados em janela de 5 minutos sem perder eventos brutos.
- Console de Incidentes passa a consumir a visão correlacionada.
- Adicionado `risk-preview` para testar cenários de política sem gravar evento nem executar enforcement.
- Fundamentos de canais futuros `clipboard`, `messaging`, `email` e `ai`.
- WhatsApp, Teams, Slack, Telegram e Discord são modelados como destinos futuros de mensageria, mas **captura ativa de mensagens não é anunciada nesta versão**.
- Mantidos como canais ativos: filesystem, download, screenshot e removable.

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
