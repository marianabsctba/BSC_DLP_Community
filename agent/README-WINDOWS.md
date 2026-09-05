# BSC DLP Agent — Windows

A partir da v0.4.2, o uso normal da Community Edition não exige executar o agente manualmente. O launcher da raiz (`START-BSC-DLP.cmd`) faz enrollment, configura o endpoint e inicia o agente oculto.

## Descoberta padrão

O agente usa as APIs de Known Folders do Windows em vez de assumir nomes em inglês. Isso permite respeitar idioma do sistema, OneDrive e Known Folder Move corporativo.

Canais descobertos:

- Downloads → `download`
- Desktop / Documents → `filesystem`
- Screenshots → `screenshot`
- Drives `DRIVE_REMOVABLE` → `removable`

## OCR

Quando `tesseract.exe` é encontrado em `%ProgramFiles%\Tesseract-OCR\tesseract.exe`, o launcher configura OCR automaticamente. Também é possível definir `BSC_DLP_TESSERACT` manualmente.

## Build manual

```powershell
.\scripts\windows\Build-Windows.ps1
```

Ou gere a release completa a partir da raiz do projeto:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Build-Community-Release.ps1
```


## v0.4.2

The Windows agent now performs local document extraction (PDF/OpenXML/text/images), supports temporary enrollment tokens, and enforces BLOCK/QUARANTINE by moving the detected object into local endpoint quarantine and removing the source object. Pre-write kernel enforcement is not claimed.
