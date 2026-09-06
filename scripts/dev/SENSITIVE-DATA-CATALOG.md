# BSC DLP Sensitive Data Catalog — v0.6.6

Este catálogo separa **o que é sensível** de **como é detectado**. Regex não deve ser confundida com uma taxonomia de privacidade.

## Bases adotadas

- **LGPD / ANPD** — dado pessoal é informação relacionada a pessoa natural identificada ou identificável; dado pessoal sensível inclui origem racial/étnica, convicção religiosa, opinião política, filiação sindical/organizações correlatas, saúde, vida sexual, genética e biometria.
- **NIST SP 800-122** — inclui identificadores diretos e informação linked/linkable, como dados médicos, educacionais, financeiros e de emprego.
- **GDPR** — reforça identificadores online e categorias especiais de dados.
- **PCI DSS** — separa Cardholder Data (CHD) de Sensitive Authentication Data (SAD).
- **Prática de DLP/SIT** — padrão primário + evidência corroborativa + proximidade + nível de confiança. Checksum sozinho pode ter confiança média; checksum mais contexto pode elevar a confiança.

## Famílias do BSC DLP

| Família | Exemplos | Tratamento |
|---|---|---|
| `pii` | CPF, RG, passaporte, CNH, e-mail, telefone, nascimento, endereço, geolocalização | Identificação direta ou pessoal |
| `linkable_data` | IP, MAC, IMEI, placa, matrícula de empregado/aluno | Pode identificar quando ligada a outras informações |
| `sensitive_personal` | saúde, CNS, biometria, genética, raça/etnia, religião, política, sindicato, vida sexual/orientação | Categoria de maior sensibilidade |
| `financial` | conta bancária, PIX | Financeiro pessoal |
| `payment_card` | PAN, CVV/CVC/CID, PIN, track data | PCI DSS |
| `credential_secret` | senha, bearer token, API key, private key, JWT | Segredo/autenticação |
| `business_data` | CNPJ e outros identificadores corporativos | Não tratar automaticamente como PII |

## Confiança

- **High (>=85)**: checksum/padrão forte + evidência corroborativa; ou dado de autenticação/segredo fortemente identificado.
- **Medium (75–84)**: checksum ou estrutura forte sem contexto textual obrigatório.
- **Low (<75)**: padrão fraco/linkable/contexto insuficiente. Não deve gerar BLOCK isoladamente por padrão.

### Exemplo CPF

`123.456.789-09` pode ser detectado pelo checksum **sem a palavra CPF**.  
A presença de termos como `CPF`, `cadastro`, `identificação` ou `receita` funciona como evidência extra, não como requisito absoluto.

## Combinações

O motor agrega contexto:

- `pii_bundle`: 2+ identificadores pessoais/linkable no mesmo objeto.
- `pii_profile`: 3+ tipos pessoais/linkable.
- `special_category_linked_identity`: dado sensível + identificador direto.
- `pci_account_plus_authentication`: PAN + SAD.

Esses sinais aumentam risco sem exigir que cada elemento, isoladamente, seja suficiente para BLOCK.

## O que é catalogado mas ainda não é detectado semanticamente

As classes abaixo fazem parte do catálogo, mas **não devem ser fingidas por regex**:

- saúde clínica ampla;
- biometria real;
- genética;
- raça/etnia;
- religião;
- opinião política;
- filiação sindical;
- vida sexual/orientação.

Para isso, versões futuras devem usar dicionários controlados, NER/classificadores ou integrações especializadas. O catálogo marca esses itens como `semantic_required`.

## CEP

CEP continua **não sendo um detector PII independente**. Ele pode reforçar uma detecção de endereço, mas `80000-000` sozinho não prova identidade de pessoa natural.

## Referências oficiais

- LGPD: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- ANPD: https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes
- NIST SP 800-122: https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-122.pdf
- GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04
- PCI DSS: https://www.pcisecuritystandards.org/standards/pci-dss/
- Microsoft Purview SIT model: https://learn.microsoft.com/pt-br/purview/sit-sensitive-information-type-learn-about
