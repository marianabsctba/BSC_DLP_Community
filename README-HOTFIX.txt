# BSC DLP v0.6.2 Apply Hotfix

Corrige um bug no empacotamento do patcher v0.6.2.

Causa:
- o patcher usava `ROOT/browser-extension` como origem e destino;
- ao preparar a instalação, apagava o destino;
- como origem e destino eram o mesmo diretório, ele apagava também a própria origem;
- resultado: WinError 3.

Este hotfix move a origem para:
`scripts/dev/browser-extension-template`

e recria:
`browser-extension/`

sem edição manual.

Extraia na raiz do repositório e execute:
`FIX-V0.6.2-APPLY.cmd`
