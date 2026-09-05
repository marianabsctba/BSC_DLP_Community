# Security

## Console

A v0.5 exige autenticação administrativa para endpoints, policies, eventos, incidentes, stats e capabilities. O agente usa uma credencial Bearer independente e não recebe sessão administrativa.

O modo padrão escuta apenas em `127.0.0.1`.

`START-BSC-DLP-LAN.cmd` é destinado a laboratório/rede confiável. Para uso centralizado real, coloque o serviço atrás de TLS/reverse proxy e controles de rede. O cookie administrativo da configuração local não substitui TLS.

## Enrollment

- A chave mestra local fica no runtime da console.
- A console gera tokens temporários com expiração e limite de usos para novos endpoints.
- O instalador troca esse código por um token individual de endpoint.
- Revogar um endpoint invalida seu Bearer token.

## Dados sensíveis

O agente classifica localmente. Valores detectados são mascarados e fingerprintados antes da telemetria. O arquivo bruto não é enviado à console pela implementação atual. Relatórios usam apenas valores mascarados/fingerprints e metadados administrativos; a exportação CSV neutraliza células iniciadas por `=`, `+`, `-` ou `@` para reduzir risco de formula injection.

## Detectores customizados

Regras customizadas são expressões regulares compatíveis com RE2, limitadas em tamanho e entregues somente a agentes autenticados. Evite incluir dados reais ou segredos dentro da própria regex.

## Enforcement

`BLOCK`/`QUARANTINE` significa que o agente move o objeto para quarentena local e remove o original depois da notificação de filesystem. `blocked=true` só é registrado quando isso termina com sucesso.

Isso não é pre-write kernel enforcement. Um Windows minifilter assinado é necessário para impedir I/O antes da gravação.

## Reporting

Ao reportar vulnerabilidades, não envie tokens, senhas, documentos sensíveis ou dumps reais. Forneça uma reprodução mínima e dados sintéticos.
