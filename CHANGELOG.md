# Changelog

## [0.6.9] - 2026-09-07

### Dashboard Analytics
- Novo motor gráfico nativo e local, sem dependências externas.
- 27 visualizações analíticas distribuídas em 9 módulos da console.
- Visão Geral com eventos por canal, ações DLP e evolução de risco.
- Incidentes com tipos correlacionados, distribuição e evolução de risco.
- Eventos com classificações, canais e risco conforme filtros e paginação.
- Endpoints com status, risco por dispositivo e sistemas operacionais.
- Políticas com ações, canais e severidades.
- AI Gateway com prompts por provider, decisões DLP e risco.
- Detectores com origem, status e classificações.
- Documentos & OCR com formatos observados, canais e risco documental.
- Relatórios com classificações, canais e ações de proteção.
- Layout responsivo integrado à console BSC DLP.
## [0.6.8] - 2026-09-07

### AI Gateway
- Novo canal `ai_prompt` para inspeção DLP de prompts enviados a ferramentas de IA generativa.
- Integração Browser Guard com ChatGPT, Claude, Gemini e Microsoft Copilot.
- Inspeção local antes do envio com decisões `ALLOW`, `ALERT` e `BLOCK`.
- Políticas padrão para CPF, CNPJ, RG, passaporte, CNH, CNS, e-mail, telefone, dados bancários, PIX, cartões, credenciais e secrets.
- Prompt bruto não é armazenado por padrão; eventos preservam metadados, valores mascarados, fingerprints, política, risco e destino.
- Destinos de IA são tratados como externos para cálculo de contexto e risco.
- Eventos usam semântica própria de AI Gateway: `ai_prompt`, `browser_ai_prompt` e `/prompt`.
- Novo painel administrativo AI Gateway com prompts inspecionados, bloqueios, alertas, providers recentes e eventos.
- Dashboard com atividade por ChatGPT, Claude, Gemini e Copilot.
- BLOCK validado nos quatro providers.
- ALERT e ALLOW validados no fluxo Browser Guard.
- Community permanece fail-open com aviso quando o bridge local estiver indisponível.
## [0.6.7] - 2026-09-06

### Exfiltration Engine
- Correlação de transferências por janela de 5 minutos.
- Contagem de objetos transferidos por canal de exfiltração.
- Cálculo de volume total transferido.
- Persistência de `object_size_bytes`.
- Detecção de transferência em massa por Browser Upload e mídia removível.
- Incidentes `BULK_FILE_EXFILTRATION`, `HIGH_VOLUME_FILE_EXFILTRATION` e `MASS_FILE_EXFILTRATION`.
- Novos fatores de risco por quantidade de objetos e volume transferido.

### Browser DLP
- Browser Bridge passa o tamanho real do objeto inspecionado.
- Correção de eventos duplicados por múltiplos matches do mesmo dado sensível.
- Deduplicação baseada em classificação + valor normalizado.
- Normalização de CPF preservando valores distintos.

### Validação
- 10 arquivos correlacionados.
- 10 objetos únicos.
- 60 MiB transferidos.
- `DUPLICATE_OBJECT_PATHS: 0`.
- Incidente final: `BULK_FILE_EXFILTRATION`.
- Bloqueio de CPF confirmado.
- Deduplicação confirmada com `EVENT_COUNT: 1`.

## 0.6.6.3 - 2026-09-06

- Browser Guard Presence Watch para Chrome, Edge e Firefox.
- A extensÃ£o envia heartbeat local periÃ³dico ao bridge do agente.
- O agente verifica se o navegador estÃ¡ em execuÃ§Ã£o e alerta quando o heartbeat da extensÃ£o desaparece.
- Novo evento `BROWSER_GUARD_DISABLED_OR_MISSING` em `channel=browser_guard`, severidade HIGH e aÃ§Ã£o ALERT.
- Novo evento `BROWSER_GUARD_RESTORED` quando a proteÃ§Ã£o retorna.
- Anti-spam por transiÃ§Ã£o de estado: um alerta por perda, um evento por restauraÃ§Ã£o.
- Navegador fechado nÃ£o Ã© tratado como extensÃ£o desabilitada.
- Edge/Chrome usam MV3 service worker; Firefox mantÃ©m `background.scripts` compatibility path.
- Browser Upload e Browser Guard adicionados aos filtros de canal do dashboard.

## 0.6.6 - 2026-09-06

- Novo **Sensitive Data Catalog & Confidence Engine** baseado em LGPD/ANPD, NIST PII, GDPR, PCI DSS e prÃ¡ticas de DLP por confianÃ§a/evidÃªncia.
- CatÃ¡logo separa PII, linkable data, dado pessoal sensÃ­vel, financeiro, payment card, credenciais/secrets e business data.
- CPF/CNPJ/PAN continuam independentes de palavra-chave quando checksum valida; contexto passa a elevar confianÃ§a, nÃ£o ser requisito absoluto.
- Novos detectores: telefone BR formatado, data de nascimento contextual, nome completo contextual, endereÃ§o fÃ­sico, IP/MAC contextuais, IMEI contextual+Luhn, placa BR, geolocalizaÃ§Ã£o contextual, CNH/PIS-NIS/tÃ­tulo/CNS/matrÃ­culas/prontuÃ¡rio contextuais.
- PCI DSS: CVV/CVC/CID, PIN e track data entram como Sensitive Authentication Data e recebem BLOCK em canais externos.
- Novos sinais de correlaÃ§Ã£o: `pii_bundle`, `pii_profile`, `special_category_linked_identity`, `pci_account_plus_authentication`.
- CEP permanece evidÃªncia auxiliar de endereÃ§o, nÃ£o um detector PII independente.
- Classes sem detecÃ§Ã£o segura por regex (biometria, genÃ©tica, raÃ§a/etnia, religiÃ£o, polÃ­tica, sindicato, vida sexual/orientaÃ§Ã£o, saÃºde clÃ­nica ampla) entram no catÃ¡logo como `semantic_required`, sem fingir cobertura.

## 0.6.5 - 2026-09-05

- Novo **Generic Browser Upload DLP** no BSC DLP Browser Guard.
- A extensÃ£o passa a observar seletores de arquivo, drag & drop e paste de arquivo/imagem em pÃ¡ginas HTTP/HTTPS.
- Arquivos sÃ£o enviados em chunks apenas para o bridge local `127.0.0.1:8765`; o conteÃºdo nÃ£o sai do endpoint para inspeÃ§Ã£o.
- O bridge reconstrÃ³i um arquivo temporÃ¡rio local, reutiliza os extratores/OCR existentes e apaga o temporÃ¡rio ao final.
- Novo canal `browser_upload` com destino igual ao hostname da pÃ¡gina e `destination_trust=external`.
- Policies padrÃ£o: CPF/cartÃ£o/secrets/credenciais em BLOCK; CPF-like/CNPJ/dados bancÃ¡rios/PIX em ALERT.
- ExtensÃµes textuais sensÃ­veis `.env`, `.pem`, `.key` e `.sql` entram no pipeline de extraÃ§Ã£o textual.
- WhatsApp Web text guard continua ativo e separado do pipeline de upload.
- Limite atual por arquivo: 25 MiB. Tipos ainda nÃ£o suportados ficam fail-open com aviso; ZIP/7z/encrypted archives ficam para a prÃ³xima camada.
- Limite tÃ©cnico: interceptaÃ§Ã£o DOM Ã© best-effort; aplicaÃ§Ãµes web que processam arquivos fora dos eventos DOM convencionais podem exigir integraÃ§Ã£o especÃ­fica.

## 0.6.4.1 - 2026-09-05

- Hotfix do OCR de screenshots no clipboard Windows.
- Corrige falha `pixReadMemBmp: cannot read compressed BMP files` observada com `CF_DIBV5`.
- O sensor agora prioriza `CF_BITMAP` e usa GDI `GetDIBits` para normalizar a captura para BMP 24-bit `BI_RGB` antes do Tesseract.
- DIB/DIBV5 permanece apenas como fallback seguro quando jÃ¡ estiver em formato nÃ£o comprimido.
- Nenhuma imagem bruta Ã© enviada ao backend; o BMP temporÃ¡rio continua sendo removido apÃ³s OCR.

## 0.6.4 - 2026-09-05

- Novo **Windows Clipboard Screenshot OCR Sensor**.
- Imagens que chegam ao clipboard via captura de tela (incluindo fluxo `Win+Shift+S`) sÃ£o convertidas temporariamente de DIB/DIBV5 para BMP e inspecionadas localmente por OCR.
- A imagem bruta nÃ£o Ã© enviada ao backend e o BMP temporÃ¡rio Ã© removido imediatamente apÃ³s o OCR.
- Eventos usam `channel=screenshot`, `destination=clipboard` e `document_type=clipboard_image`.
- PolÃ­ticas `BLOCK`/`QUARANTINE` no canal screenshot podem limpar a imagem sensÃ­vel do clipboard apÃ³s a detecÃ§Ã£o.
- Novas polÃ­ticas padrÃ£o de screenshot: CPF/cartÃ£o/segredos/credenciais com proteÃ§Ã£o forte; CPF-like/CNPJ/banking/PIX em ALERT.
- Capturas salvas em arquivo continuam usando o sensor de filesystem/screenshot jÃ¡ existente.
- Limite honesto: a v0.6.4 **nÃ£o bloqueia o ato de capturar pixels antes da captura**; ela protege o artefato quando ele chega ao clipboard ou ao filesystem.

## 0.6.3 - 2026-09-05

- Novo **Evasion-Resistant Detection Engine** para identificadores sensÃ­veis.
- CPF/CNPJ/cartÃ£o passam por extraÃ§Ã£o local de candidatos + normalizaÃ§Ã£o limitada + checksum/Luhn.
- Detecta separadores incomuns (`#`, `|`, `_`, sÃ­mbolos), espaÃ§amento excessivo, quebras e caracteres zero-width.
- Detecta dÃ­gitos Unicode comuns e converte para forma canÃ´nica antes da validaÃ§Ã£o.
- Detecta CPF/CNPJ/cartÃ£o escritos com nÃºmeros por extenso em PT/EN/ES quando existe contexto explÃ­cito.
- `CPF_LIKE` sinaliza CPF mutilado (10/12 dÃ­gitos ou checksum invÃ¡lido) somente quando existe contexto forte de CPF; padrÃ£o em mensageria Ã© ALERT.
- Novas tags de risco: `obfuscated_identifier`, `evasive_obfuscation`, `malformed_identifier`, `embedded_identifier`.
- EvasÃ£o forte e identificadores malformados aumentam o risk score explicÃ¡vel.
- `PHONE_BR` deixa de ser classificador nativo e passa a ser exemplo opcional/custom, assim como CEP.
- O motor **nÃ£o concatena todos os nÃºmeros de um documento**; a normalizaÃ§Ã£o Ã© limitada a janelas locais para reduzir falsos positivos.

## 0.6.2 - 2026-09-05

- Novo Browser Guard MV3 para WhatsApp Web em Chrome/Edge.
- ExtensÃ£o inspeciona somente conteÃºdo de saÃ­da do composer: paste, clique em enviar e Enter.
- A extensÃ£o nÃ£o lÃª histÃ³rico de chats e nÃ£o persiste texto bruto.
- Bridge local no agente (`127.0.0.1:8765`) reutiliza o mesmo detector, classificador e motor de polÃ­ticas do endpoint.
- Eventos usam `channel=messaging` e `destination=whatsapp_web`.
- PolÃ­ticas BLOCK/QUARANTINE impedem o paste/envio antes da aÃ§Ã£o do WhatsApp Web.
- Em indisponibilidade do bridge local, o comportamento padrÃ£o Ã© fail-open com aviso visual.
- Upload de arquivos pelo navegador ainda nÃ£o Ã© captura ativa nesta versÃ£o.

## 0.6.1 - 2026-09-05

- Windows Messaging Clipboard Sensor para WhatsApp Desktop, Teams, Slack, Telegram e Discord.
- InspeÃ§Ã£o local do clipboard somente quando um app de mensageria reconhecido estÃ¡ em foreground.
- ConteÃºdo bruto do clipboard nÃ£o Ã© persistido; somente valores mascarados/fingerprinted.
- PolÃ­ticas BLOCK/QUARANTINE no canal messaging podem limpar o clipboard antes do paste.
- PII/banking em ALERT por padrÃ£o; cartÃ£o/segredos/credenciais em BLOCK para mensageria.
- NÃ£o lÃª mensagens, nÃ£o quebra E2EE e nÃ£o intercepta chats.
- WhatsApp Web e upload de arquivos ainda nÃ£o sÃ£o captura ativa nesta versÃ£o.
- Timestamps corrigidos: API emite UTC com Z explÃ­cito e a console converte para o horÃ¡rio local do host/browser.
- PDF/CSV exibem horÃ¡rio local do host.
- /api/v1/health informa server_time_utc e server_time_local.

## 0.6.0 - 2026-09-05

- Novo **Context-Aware DLP Engine** com co-occurrence, volume, nomes/extensÃµes sensÃ­veis e destination trust.
- CEP removido dos detectores nativos; continua possÃ­vel como detector customizado.
- Risk score passa a ser explicÃ¡vel por `risk_reasons`.
- Incidentes recebem `incident_key` e podem ser correlacionados em janela de 5 minutos sem perder eventos brutos.
- Console de Incidentes passa a consumir a visÃ£o correlacionada.
- Adicionado `risk-preview` para testar cenÃ¡rios de polÃ­tica sem gravar evento nem executar enforcement.
- Fundamentos de canais futuros `clipboard`, `messaging`, `email` e `ai`.
- WhatsApp, Teams, Slack, Telegram e Discord sÃ£o modelados como destinos futuros de mensageria, mas **captura ativa de mensagens nÃ£o Ã© anunciada nesta versÃ£o**.
- Mantidos como canais ativos: filesystem, download, screenshot e removable.

## 0.5.4 - 2026-09-05

- Console administrativa agora Ã© trilÃ­ngue: **PortuguÃªs, English e EspaÃ±ol**, com seletor no login e na barra superior.
- PreferÃªncia de idioma do administrador Ã© persistida localmente no navegador e aplicada sem reiniciar a console.
- PDF, CSV e visualizaÃ§Ã£o de impressÃ£o respeitam o idioma selecionado, incluindo tÃ­tulos, filtros, KPIs, colunas, paginaÃ§Ã£o e mensagens de privacidade.
- Mensagens de autenticaÃ§Ã£o e erros administrativos comuns tambÃ©m recebem localizaÃ§Ã£o PT/EN/ES.
- Adicionados testes automatizados para os trÃªs idiomas e validaÃ§Ã£o de sintaxe JavaScript no fluxo de CI.
- RelatÃ³rios agora sÃ£o gerados como PDF real (`application/pdf`) pelo backend via ReportLab.
- BotÃ£o principal da console passa a baixar `bsc-dlp-report-*.pdf`; o antigo fluxo de impressÃ£o fica apenas como visualizaÃ§Ã£o secundÃ¡ria.
- PDF respeita os mesmos filtros da console e inclui KPIs, top classificaÃ§Ãµes/canais/aÃ§Ãµes e tabela detalhada de eventos.
- Dados sensÃ­veis nÃ£o sÃ£o incluÃ­dos em claro no PDF; a tabela usa metadados operacionais e nomes de objetos.
- Download de PDF no frontend ganhou tratamento de erro e feedback visual ao administrador.
- Build Windows inclui ReportLab no backend self-contained.
- Adicionado workflow de CI para testes Python/Go em push e pull request.
- Estrutura limpa e versionada como base GitHub-ready, sem DB, tokens, logs, secrets ou caches locais.

## 0.5.3 â€” 2026-09-05

- Fixed Python 3.10 startup failure in the printable HTML report (`f-string expression part cannot include a backslash`).
- Launcher now shows explicit startup stages instead of appearing frozen after `pip`.
- Python dependencies are installed only when `requirements.txt` changes.
- Disabled automatic OCR installation during normal START; missing OCR is reported clearly instead of blocking startup.
- Preserved the black/pink panther branding, favicon and Windows shortcut icon.

## 0.5.2 â€” 2026-09-05

- Nova identidade visual oficial preto + rosa com Ã­cone da pantera BSC DLP.
- Ãcone aplicado ao login, sidebar e favicon da console.
- Launcher cria/atualiza o atalho `BSC DLP Community` na Ãrea de Trabalho com o Ã­cone oficial.
- Launcher agora detecta conflito na porta 8000 e escolhe automaticamente a prÃ³xima porta livre em instalaÃ§Ãµes locais.
- Falhas de inicializaÃ§Ã£o exibem as Ãºltimas linhas do log do backend diretamente no terminal.
- Build Windows inclui os assets de marca e embute o Ã­cone no executÃ¡vel do backend.
- Mantidos os filtros, paginaÃ§Ã£o, relatÃ³rios, detectores customizados, OCR e enforcement da v0.5.x.

## 0.5.1 â€” 2026-09-05

- BotÃ£o **Sair** agora fica visÃ­vel no topo da console administrativa, alÃ©m da Ã¡rea AdministraÃ§Ã£o.
- Mantidos os filtros completos de Eventos, Incidentes e RelatÃ³rios: perÃ­odo, endpoint/usuÃ¡rio, classificaÃ§Ã£o, canal, severidade, aÃ§Ã£o, bloqueio, texto livre e risco mÃ­nimo.
- RelatÃ³rios continuam exportÃ¡veis em CSV e em versÃ£o pronta para imprimir/salvar como PDF.
- Primeiro acesso continua obrigatÃ³rio em instalaÃ§Ãµes novas; upgrades preservam a conta administrativa existente no runtime local.
- Launcher atualizado para v0.5.1.

## 0.5.0 â€” 2026-09-05

- Motor de classificaÃ§Ã£o ampliado: e-mail, RG, CEP, telefone, PIX, conta bancÃ¡ria, passaporte, credenciais e novos tipos de secret, alÃ©m de CPF/CNPJ/cartÃ£o.
- Detectores customizados por regex RE2, criados pelo administrador e distribuÃ­dos automaticamente aos agentes.
- Nova Ã¡rea **RelatÃ³rios** com resumo, CSV e versÃ£o imprimÃ­vel/salvÃ¡vel como PDF.
- Valores sensÃ­veis permanecem mascarados/fingerprinted nos relatÃ³rios; CSV protegido contra formula injection.
- Eventos e incidentes ganharam filtros por perÃ­odo, endpoint/usuÃ¡rio, classificaÃ§Ã£o, canal, severidade, aÃ§Ã£o, bloqueio, texto e risco mÃ­nimo.
- PaginaÃ§Ã£o de 10/25/50/100 itens para evitar tabelas infinitas e melhorar desempenho da console.
- Novos endpoints paginados `/events/query` e `/incidents/query`, preservando compatibilidade com os endpoints anteriores.
- RelatÃ³rios e detectores customizados permanecem restritos Ã  sessÃ£o administrativa.
- Testes de integraÃ§Ã£o ampliados para filtros, relatÃ³rios e distribuiÃ§Ã£o de regras customizadas.

## 0.4.2 â€” 2026-09-05

- Corrigida detecÃ§Ã£o de imagens baixadas por navegador em `Downloads`.
- O agente agora espera o arquivo estabilizar antes da inspeÃ§Ã£o, evitando OCR em arquivos ainda incompletos.
- Renames de browser (`.crdownload`/temporÃ¡rios â†’ arquivo final) acionam rescan recente da pasta para nÃ£o perder PNG/JPG/PDF finalizados.
- OCR de imagem agora tenta idiomas configurÃ¡veis e faz fallback `por+eng` â†’ `eng` quando o pacote portuguÃªs nÃ£o estÃ¡ disponÃ­vel.
- Descoberta do Tesseract ampliada para PATH, Program Files, Program Files (x86) e LocalAppData.
- Source One-Click tenta instalar Tesseract via `winget` quando OCR nÃ£o estÃ¡ disponÃ­vel; pode ser desabilitado com `BSC_DLP_SKIP_OCR_BOOTSTRAP=1`.
- Adicionado `TEST-OCR-DOWNLOAD.cmd`, que gera um PNG de laboratÃ³rio com CPF de teste em Downloads para validar o fluxo ponta a ponta.
- Adicionados testes do pipeline `download PNG â†’ OCR â†’ CPF â†’ policy/event` e do rescan pÃ³s-download.

## 0.4.1 â€” 2026-09-05

- Interface da console simplificada para uso administrativo, sem notas internas de desenvolvimento.
- Textos e rÃ³tulos da console padronizados em portuguÃªs.
- SuÃ­te de regressÃ£o ampliada para autenticaÃ§Ã£o, enrollment, polÃ­ticas, eventos, risco e revogaÃ§Ã£o.
- Testes de integraÃ§Ã£o do backend adicionados ao repositÃ³rio.

## 0.4.0 â€” 2026-09-05

- Nova console administrativa preto + rosa.
- Primeiro acesso com criaÃ§Ã£o do administrador; usuÃ¡rios de endpoint nÃ£o possuem acesso Ã  console.
- Senha administrativa armazenada com derivaÃ§Ã£o `scrypt` + salt.
- SessÃµes administrativas via cookie HttpOnly / SameSite Strict.
- APIs de endpoints, policies, eventos, incidents e stats agora exigem admin.
- Credenciais Bearer dos agents permanecem separadas das credenciais administrativas.
- BotÃ£o **Adicionar endpoint** agora gera enrollment token temporÃ¡rio, expirÃ¡vel e de uso limitado.
- Adicionado `INSTALL-ENDPOINT.cmd` para enrollment e instalaÃ§Ã£o por usuÃ¡rio no Windows.
- Adicionado `UNINSTALL-ENDPOINT.cmd`.
- Adicionado modo `START-BSC-DLP-LAN.cmd` para laboratÃ³rio com endpoints remotos.
- Novo Behavior Risk Engine com score 0â€“100 e priorizaÃ§Ã£o de incidentes.
- Endpoint risk agregado das Ãºltimas 24h.
- Suporte documental: PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON, XML, LOG, MD, INI, CONF, YAML/YML.
- PDF usa `pdftotext` quando disponÃ­vel, parser interno best-effort e OCR fallback com `pdftoppm + Tesseract`.
- OCR de imagens mantido.
- Novos classificadores: CNPJ checksum, cartÃ£o/Luhn e secrets bÃ¡sicos, alÃ©m de CPF checksum.
- `BLOCK`/`QUARANTINE` agora executam enforcement real no endpoint por quarentena + remoÃ§Ã£o do objeto original.
- Eventos sÃ³ registram `blocked=true` apÃ³s enforcement bem-sucedido.
- Quarentena funciona entre volumes (importante para USB).
- Policies default de screenshot/removable atualizadas para BLOCK.
- Upgrade automÃ¡tico das policies v0.3 equivalentes para BLOCK.
- Tipo do documento, risk score e tipo de incidente adicionados Ã  telemetria.
- Testes adicionados para CNPJ/Luhn, OpenXML, PDF built-in e endpoint quarantine.
- Bloqueio pre-write kernel nÃ£o Ã© alegado; requer futuro Windows minifilter assinado.

## 0.3.0 â€” 2026-09-05

- Community local-first, one-click Windows, Known Folders, USB/removable, OCR de screenshot, enrollment/token, dashboard e build self-contained.

## 0.2.0 â€” 2026-09-05

- Primeiro port do agente para Windows preservando Linux.

