# BSC DLP v0.6.4 — Clipboard Screenshot OCR

- Sensor Windows para imagens no clipboard.
- Cobre `Win + Shift + S` quando a captura chega ao clipboard.
- Lê CF_DIBV5/CF_DIB, converte localmente para BMP temporário e reutiliza o Tesseract.
- O BMP temporário é apagado após OCR; a imagem não vai ao backend.
- `BLOCK`/`QUARANTINE` pode limpar o clipboard após detecção.
- Screenshots salvos em arquivo continuam cobertos pelo sensor existente.

Limite: isso não impede a captura antes de o Windows produzir a imagem.

Ordem:
1. APPLY-V0.6.4.cmd
2. TEST-V0.6.4.cmd
3. Reiniciar BSC DLP.
4. TEST-SCREENSHOT-CLIPBOARD.cmd
