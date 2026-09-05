# Rodrigo Adversarial Test Set — v0.6.3

Use somente dados sintéticos/de teste.

## Deve detectar CPF
- `CPF: 123 # 456 # 789 # 09`
- `CPF: 123|456|789|09`
- `CPF: 123​456​789​09` (zero-width)
- `CPF assim: um dois tres quatro cinco seis sete oito nove zero nove`
- `CPF: one two three four five six seven eight nine zero nine`
- `CPF: uno dos tres cuatro cinco seis siete ocho nueve cero nueve`

## Deve sinalizar CPF_LIKE (ALERT, não CPF validado)
- `CPF: 123 # 456 # 789 # 0`
- `CPF: 123456789090`

## Deve detectar CNPJ/cartão
- `CNPJ: 11 # 222 # 333 # 0001 # 81`
- `Cartão: 4111 # 1111 # 1111 # 1111`

## Não deve juntar números sem relação
Pedido 123
Cliente 456
Ramal 789
Andar 09

## Mudança de escopo
Telefone e CEP não são classificadores nativos prioritários na v0.6.3; podem ser criados como detectores custom.
