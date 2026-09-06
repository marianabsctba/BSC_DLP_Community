<div align="center">
  <img src="dashboard/assets/bsc-dlp-icon.png" width="170" alt="BSC DLP Community logo" />

  # BSC DLP Community

  **Open-source Data Loss Prevention for Windows & Linux endpoints**  
  **Detect • Classify • Correlate • Control • Protect**

  <sub>Local-first · Context-aware · Endpoint-first · Browser Guard · PT / EN / ES · Community driven</sub>

  <br><br>

  [![CI](https://github.com/marianabsctba/BSC_DLP_Community/actions/workflows/ci.yml/badge.svg)](https://github.com/marianabsctba/BSC_DLP_Community/actions/workflows/ci.yml)
  ![Version](https://img.shields.io/badge/version-0.6.6.1-ff2d95?style=flat-square)
  ![License](https://img.shields.io/badge/license-AGPL--3.0-ff2d95?style=flat-square)
  ![Agent](https://img.shields.io/badge/agent-Go-00ADD8?style=flat-square&logo=go&logoColor=white)
  ![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
  ![Endpoints](https://img.shields.io/badge/endpoints-Windows%20%7C%20Linux-111111?style=flat-square)
  ![Browser Guard](https://img.shields.io/badge/browser%20guard-Chromium-4285F4?style=flat-square&logo=googlechrome&logoColor=white)
  ![UI](https://img.shields.io/badge/UI-PT%20%7C%20EN%20%7C%20ES-ff2d95?style=flat-square)
</div>

---

## What is BSC DLP?

**BSC DLP Community** is an open-source Data Loss Prevention project focused on **endpoint visibility, sensitive-data classification, context-aware risk, policy enforcement and investigation**.

Sensitive content is inspected **locally on the endpoint** whenever possible. The administrative console receives only the telemetry needed for investigation, such as:

- classification;
- masked evidence;
- fingerprint;
- object SHA-256;
- channel;
- destination;
- context/risk tags;
- policy action;
- enforcement result.

Raw sensitive values are not intentionally sent to the central console.

The project follows one core idea:

> **Do not only ask what sensitive data exists. Ask what is being done with it, where it is going and how risky that context is.**

### 🇧🇷 Resumo

DLP open source com agente Windows/Linux, inspeção local, OCR, proteção de arquivos, clipboard, screenshots, WhatsApp Web, uploads no navegador, políticas, risco contextual, incidentes e relatórios.

### 🇪🇸 Resumen

DLP open source con agente Windows/Linux, inspección local, OCR, protección de archivos, portapapeles, capturas de pantalla, WhatsApp Web, cargas en navegador, políticas, riesgo contextual, incidentes e informes.

---

# What is new in v0.6.x

The v0.6 generation expands BSC DLP from file-centric inspection into a **context-aware DLP engine**.

```text
DETECT
   ↓
CLASSIFY
   ↓
ADD CONTEXT
   ↓
CORRELATE
   ↓
SCORE RISK
   ↓
AUDIT / ALERT / BLOCK / QUARANTINE
```

## 💬 WhatsApp Web Browser Guard

BSC DLP can inspect outgoing text in **WhatsApp Web** before paste/send actions.

```text
WhatsApp Web
      ↓
BSC DLP Browser Guard
      ↓
Local bridge — 127.0.0.1:8765
      ↓
Go endpoint agent
      ↓
Detector + policy engine
      ↓
ALLOW / ALERT / BLOCK
```

Confirmed behavior includes **pre-send blocking** when a policy resolves to `BLOCK`.

The Browser Guard:

- inspects outgoing composer text;
- intercepts paste, Enter/send and send-button actions;
- reuses the same native/custom classifiers and policies as the endpoint;
- communicates only with the **local endpoint bridge**;
- does **not** read chat history;
- does **not** decrypt or bypass end-to-end encryption;
- does **not** behave as a chat-monitoring product.

> Current Community deployment uses an unpacked Chromium extension. Chrome has been validated in the lab. Edge/other Chromium browsers require loading the extension in that browser/profile separately.

---

## 🌐 Generic Browser Upload DLP

The Browser Guard can also inspect files selected for upload on regular HTTP/HTTPS web pages.

Supported browser interaction paths include:

- `<input type="file">`;
- file picker selection;
- drag & drop;
- paste events containing files/images.

File inspection flow:

```text
Browser page
      ↓
BSC DLP Browser Guard
      ↓
Chunked transfer to localhost bridge
      ↓
Temporary endpoint copy
      ↓
Existing extractor / OCR engine
      ↓
Sensitive-data detection + policy
      ↓
ALLOW / ALERT / BLOCK
```

Important properties:

- file bytes stay on the endpoint;
- temporary inspection copy is deleted after processing;
- backend receives masked event telemetry, not the original file;
- destination hostname is added to event context;
- `browser_upload` is treated as an external destination;
- policies can block a file **before the web page receives the upload action** when interception succeeds.

### Browser enforcement honesty

Browser Upload DLP is **DOM-level, best-effort enforcement**.

It is not a network proxy, kernel control or browser vendor security engine. Complex web applications may require specific handling.

If the local bridge/inspection path is unavailable, the current Community behavior is **fail-open** with a reason/notice rather than silently pretending enforcement happened.

---

## 🖥️ Desktop messaging clipboard sensor

On Windows, BSC DLP can inspect clipboard text while selected desktop messaging applications are in the foreground.

Current targets include:

- WhatsApp Desktop;
- Microsoft Teams;
- Slack;
- Telegram;
- Discord.

The sensor:

- does not read chats;
- does not scrape message history;
- does not decrypt messaging traffic;
- inspects clipboard content locally;
- can clear the clipboard when a `BLOCK` policy is triggered.

This is a **clipboard-based desktop control**, not message API interception.

---

## 📸 Clipboard Screenshot OCR

BSC DLP monitors screenshot images placed directly into the Windows clipboard, including common **Snipping Tool / Win+Shift+S** workflows.

The image pipeline:

```text
Windows clipboard image
      ↓
CF_BITMAP
      ↓
24-bit BI_RGB normalization
      ↓
Tesseract OCR
      ↓
Shared detector / policy engine
      ↓
AUDIT / ALERT / BLOCK
```

The raw screenshot is not intentionally sent to the backend.

When a `BLOCK`/`QUARANTINE` policy applies, BSC DLP can clear the clipboard **after OCR and detection**.

> This is reactive after capture/OCR. It is not pre-capture blocking and should not be described as such.

Saved screenshot files in monitored screenshot folders continue to use the regular filesystem/OCR channel.

---

## 🧠 Context-aware risk engine

BSC DLP v0.6 enriches detections with object and behavioral context.

Context signals include:

- co-occurrence of multiple sensitive classes;
- bulk/mass-data indicators;
- filename sensitivity;
- high-value file extensions;
- channel;
- destination trust;
- external vs local destination;
- evasive/obfuscated representation;
- recent endpoint behavior.

Examples of sensitive filename/context signals:

```text
payroll
customer_data
employee_data
credentials
finance
personal_data
database
```

Examples of high-value extensions:

```text
.env
.pem
.key
.pfx
.p12
.kdbx
.sql
.dump
.bak
```

---

## 🧩 Correlation instead of isolated regex matches

The engine can reason about combinations such as:

```text
email + phone
→ pii_bundle

email + phone + date of birth
→ pii_profile

direct identity + sensitive health identifier
→ special_category_linked_identity

card PAN + authentication data
→ pci_account_plus_authentication
```

This allows risk to rise based on **what appears together**, not merely on one isolated pattern.

---

## 🥷 Evasion-resistant detection

The detector pipeline includes normalization and anti-evasion handling for common obfuscation attempts.

Examples include:

- separators inserted between digits;
- Unicode/full-width digits;
- zero-width characters;
- contextual malformed identifiers;
- selected PT / EN / ES number-word forms when strong labels are present.

Examples:

```text
123 # 456 # 789 # 09
4111 1111 1111 1111
full-width / Unicode digit variants
```

For strong identifiers, checksum validation remains the preferred high-confidence signal.

---

# Sensitive Data Catalog & Confidence Engine

BSC DLP separates **what a data class means** from **how it was detected**.

The catalog is aligned with principles found in:

- LGPD / ANPD;
- NIST SP 800-122 concepts for PII and linked/linkable information;
- GDPR categories and online identifiers;
- PCI DSS cardholder / sensitive authentication data concepts;
- practical DLP confidence models based on pattern + evidence + context.

## Main data families

| Family | Examples | Treatment |
|---|---|---|
| `pii` | CPF, RG, CNH, passport, e-mail, phone, birth date, address, geolocation | Personal identifiers / attributes |
| `linkable_data` | IP, MAC, IMEI, vehicle plate, employee/student ID | May identify/link a person when combined with other data |
| `sensitive_personal` | health identifiers/data, biometrics, genetics, protected attributes | Higher-sensitivity personal data |
| `financial` | bank account, PIX | Personal financial data |
| `payment_card` | PAN, CVV/CVC/CID, PIN, track data | PCI-related data |
| `credential_secret` | passwords, bearer tokens, API keys, private keys, JWTs | Authentication / secret material |
| `business_data` | CNPJ | Corporate/business identifier, not automatically treated as PII |

## Confidence model

Detection does not always require a literal label such as `CPF:`.

For example, a structurally valid CPF can be detected through checksum without the word "CPF" appearing in the content.

Contextual terms can increase confidence, but are not always mandatory.

High-level confidence guidance:

- **High** — strong pattern/checksum plus corroborating context, or highly distinctive secret/authentication data;
- **Medium** — strong checksum/structure without additional context;
- **Low** — weak or ambiguous pattern requiring correlation before strong enforcement.

## Native / implemented detection examples

Current native detection includes or extends support for:

- CPF — checksum validated;
- CNPJ — checksum validated;
- credit-card PAN — Luhn validated;
- e-mail address;
- Brazilian RG;
- Brazilian phone number;
- date of birth with context;
- physical address patterns;
- passport with context;
- CNH with context;
- PIS / NIS with context;
- voter ID with context;
- CNS / health identifier with context;
- bank account with context;
- PIX key with context;
- IP address with context;
- MAC address with context;
- IMEI with context + checksum;
- Brazilian vehicle plate patterns;
- geolocation with context;
- employee/student IDs with context;
- health record IDs with context;
- card CVV/CVC/CID;
- card PIN;
- magnetic-track-style card data;
- passwords;
- bearer tokens;
- cloud/API tokens;
- private-key material;
- JWTs;
- custom RE2-compatible regex rules.

### CEP

CEP is **not treated as a standalone native PII classification**.

A postal code can support/address-context reasoning, but a postal code alone does not prove identification of a natural person.

### Semantic-only catalog classes

Some data classes belong in the privacy catalog but should **not be faked with simplistic regexes**.

Examples:

- broad clinical/health content;
- biometrics;
- genetic data;
- race/ethnicity;
- religion;
- political opinion;
- trade-union membership;
- sex life / sexual orientation.

These are cataloged as requiring **semantic or specialized detection** rather than being falsely claimed as fully detected by simple patterns.

---

# Current endpoint channels

| Channel | Status | What it covers |
|---|:---:|---|
| Filesystem | ✅ | Sensitive files observed in monitored folders |
| Downloads | ✅ | Browser/download folders, including settle/rename handling |
| Screenshots — saved files | ✅ | Image inspection with OCR |
| Screenshots — clipboard | ✅ | Snipping Tool / clipboard image OCR |
| Removable / USB | ✅ | Sensitive objects written to removable media |
| Desktop messaging clipboard | ✅ Windows | Clipboard inspection while supported messaging apps are foreground |
| WhatsApp Web text | ✅ Chromium Browser Guard | Paste/send inspection before outgoing action |
| Generic browser upload | ✅ Chromium Browser Guard | File picker / upload interception with local inspection |
| Email DLP | 🧪 Roadmap | Native subject/body/recipient/attachment-aware module |
| AI DLP | 🧪 Roadmap | Prompt/upload/model-aware gateway/browser module |

---

# Documents & OCR

Extraction occurs **on the endpoint**.

| Format | Inspection |
|---|---|
| PDF | Text extraction + OCR fallback for scanned PDFs |
| DOCX | OpenXML text extraction |
| XLSX | Worksheets/shared strings |
| PPTX | Slides/notes extraction |
| TXT / CSV / JSON / XML / LOG / MD | Text inspection |
| `.env` / `.pem` / `.key` / `.sql` | Text inspection / high-value context |
| PNG / JPG / JPEG / TIFF / BMP / WEBP | Tesseract OCR |

For scanned PDFs, OCR depends on the endpoint OCR toolchain being available.

---

# Policy engine

Policies are resolved using classification, channel and priority.

Supported actions:

| Action | Behavior |
|---|---|
| `ALLOW` | Explicitly allow |
| `AUDIT` | Record activity |
| `ALERT` | Record and raise visibility/risk |
| `BLOCK` | Prevent/contain where the channel supports enforcement |
| `QUARANTINE` | Move an observed file into endpoint quarantine |

## Enforcement varies by channel

This distinction is intentional:

| Channel | Enforcement model |
|---|---|
| Filesystem / download / removable | **Reactive** after write/observation |
| WhatsApp Web composer | **Pre-send** when Browser Guard interception succeeds |
| Generic browser upload | **Pre-upload at DOM layer** when Browser Guard interception succeeds |
| Desktop messaging clipboard | Clipboard content can be cleared on `BLOCK` |
| Screenshot clipboard | Clipboard image can be cleared **after OCR/detection** |

### Filesystem enforcement honesty

Filesystem `BLOCK` / `QUARANTINE` is currently **reactive endpoint enforcement**.

When a protected object is observed, BSC DLP can copy it into local quarantine and remove the original source file. The event should only record a successful block after enforcement succeeds.

BSC DLP **does not claim Windows kernel pre-I/O blocking**.

True pre-write prevention requires a signed Windows minifilter driver and remains a future enforcement module.

---

# Behavioral risk & incidents

Risk can consider:

- classification;
- sensitivity;
- channel;
- external/local destination;
- policy action;
- successful enforcement;
- co-occurrence;
- mass-data behavior;
- filename/context signals;
- obfuscation/evasion;
- recent endpoint activity.

Example:

```text
Possible sensitive browser upload
Endpoint: FINANCE-01
Classification: CPF
Channel: browser_upload
Destination: external.example
Action: BLOCK
Risk: 88/100
```

The objective is to correlate:

```text
DATA + CONTEXT + DESTINATION + BEHAVIOR + ACTION
```

instead of producing a flat list of regex matches.

---

# Architecture

```text
                         ┌────────────────────────────┐
                         │       Admin Console        │
                         │  FastAPI + SQLite + UI     │
                         └─────────────┬──────────────┘
                                       │
                               masked telemetry
                                       │
┌──────────────────────────────────────┴─────────────────────────────────────┐
│                         BSC DLP Endpoint Agent                             │
│                                   Go                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Filesystem │ Downloads │ USB │ Screenshot OCR │ Clipboard │ Browser Bridge │
└─────┬──────────┬────────┬──────────────┬────────────┬───────────────┬───────┘
      │          │        │              │            │               │
      └──────────┴────────┴──────────────┴────────────┴───────────────┘
                                       │
                     Extract / Normalize / OCR locally
                                       │
                       Native + custom classification
                                       │
                           Context + correlation
                                       │
                             Policy + risk
                                       │
                  ALLOW / AUDIT / ALERT / BLOCK / QUARANTINE
```

Browser Guard uses a local bridge:

```text
Chromium Browser Guard
        ↓
127.0.0.1:8765
        ↓
BSC DLP Go Agent
```

The bridge is local to the endpoint and is not intended as a public network service.

---

# Admin-only console

Endpoint users do **not** receive administrative credentials.

Administrative and endpoint authentication are separate:

- first access creates the administrator;
- passwords use derived hashes with salt;
- admin sessions use secure cookie mechanisms;
- endpoints use individual Bearer credentials;
- enrollment codes are temporary/use-limited;
- endpoint credentials can be revoked.

Console capabilities include:

- overview;
- risk;
- incidents;
- events;
- managed endpoints;
- policies;
- native/custom detectors;
- OCR/document capabilities;
- reports;
- settings.

---

# Filters, pagination & reporting

Events and incidents can be filtered by criteria such as:

- date/time;
- endpoint;
- user;
- classification;
- channel;
- severity;
- action;
- blocked state;
- minimum risk;
- search text.

Pagination supports:

```text
10 / 25 / 50 / 100
```

Reports support:

- PDF;
- CSV;
- print view;
- executive metrics;
- distribution by classification/channel/action;
- filtered event detail;
- masked values;
- spreadsheet formula-injection mitigation for CSV output.

---

# PT / EN / ES

The administrative interface supports:

- 🇧🇷 Português
- 🇺🇸 English
- 🇪🇸 Español

The selected language is remembered by the browser and is used by administrative reporting where supported.

Technical constants such as `BLOCK`, `AUDIT`, channel identifiers and classification names remain stable for investigation/integration purposes.

---

# Quick start — Windows source mode

## Requirements

Contributor/source mode currently expects:

- Windows 10/11;
- Python 3.10–3.12 recommended for the current test toolchain;
- Go 1.22+;
- Tesseract for OCR features;
- Chromium browser for Browser Guard testing.

A future/prebuilt Community release can package runtimes so normal users do not need to manage Python/Go manually.

## Clone

```powershell
git clone https://github.com/marianabsctba/BSC_DLP_Community.git
cd BSC_DLP_Community
```

## Start

```powershell
.\START-BSC-DLP.cmd
```

## Stop

```powershell
.\STOP-BSC-DLP.cmd
```

## Reset local lab data

```powershell
.\RESET-BSC-DLP.cmd
```

---

# Browser Guard — developer/community setup

Current Community Browser Guard is loaded as an unpacked extension.

For Chrome:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the repository `browser-extension` folder.
5. Allow site access as required.

> Each Chromium browser/profile maintains extensions independently. Loading the Browser Guard in Chrome does not automatically install it in Edge, and vice versa.

Current Browser Guard line:

```text
0.6.6.1
```

---

# Central console for LAN endpoints

For a trusted lab/LAN environment:

```powershell
.\START-BSC-DLP-LAN.cmd
```

Then generate a temporary enrollment code from the administrative console and install the endpoint using the generated enrollment command.

> For production or untrusted networks, publish the console behind TLS and a properly configured reverse proxy. Do not expose a plain HTTP management plane directly to the Internet.

---

# Local runtime

Windows Community runtime:

```text
%LOCALAPPDATA%\BSC-DLP-Community
```

Installed endpoint runtime:

```text
%LOCALAPPDATA%\BSC-DLP-Endpoint
```

Local quarantine and runtime secrets live outside the repository checkout.

---

# Security model

BSC DLP Community is designed to minimize unnecessary movement of sensitive data:

- extraction occurs locally;
- OCR occurs locally;
- browser upload files are inspected through localhost;
- temporary browser-upload files are deleted after inspection;
- raw clipboard images are not intentionally persisted by the clipboard sensor;
- backend telemetry uses masking/fingerprints rather than raw detected values;
- object SHA-256 supports evidence correlation;
- admin and endpoint authentication are separated;
- endpoint credentials are individually revocable;
- the project avoids claiming enforcement capabilities that are not implemented.

Please read [`SECURITY.md`](SECURITY.md) before exposing the central console beyond a local lab environment.

---

# Project structure

```text
BSC_DLP_Community/
├── agent/                       # Go endpoint agent
│   ├── browser_bridge.go
│   ├── clipboard_image.go
│   ├── context.go
│   ├── detectors.go
│   ├── evasion.go
│   ├── extractors.go
│   ├── sensitive_catalog.go
│   └── enforcement.go
├── api/                         # FastAPI backend
├── browser-extension/           # Chromium Browser Guard
│   ├── content.js
│   ├── service-worker.js
│   └── manifest.json
├── dashboard/                   # black + pink admin console
├── docs/
│   ├── architecture.svg
│   ├── screenshots/
│   └── SENSITIVE-DATA-CATALOG.md
├── scripts/windows/
├── tests/
├── .github/workflows/
├── START-BSC-DLP.cmd
├── STOP-BSC-DLP.cmd
└── README.md
```

---

# Tests

## Backend

```powershell
py -3.12 -m pytest -q
```

## Agent

```powershell
cd agent
go test ./...
```

## OCR smoke test

```powershell
.\TEST-OCR-DOWNLOAD.cmd
```

## Browser Upload bridge test

```powershell
.\TEST-BRIDGE-UPLOAD-V0.6.5.cmd
```

The bridge test validates the local upload path independently from browser DOM interception.

---

# Roadmap

- [ ] Signed Windows minifilter for true pre-write enforcement
- [ ] Advanced Device Control — VID/PID/serial, allowlists, read-only policies
- [ ] Native Email DLP — recipient/internal-external/body/subject/attachment aware
- [ ] AI DLP / AI Gateway — prompt/upload/model-aware controls
- [ ] Semantic classifiers / NER for sensitive categories that should not rely on regex
- [ ] Archive/container inspection — ZIP/7z and encrypted-archive policy handling
- [ ] Packaged Browser Guard deployment for easier Community/enterprise rollout
- [ ] Additional browser/application-specific integrations
- [ ] Additional classifier packs and policy templates
- [ ] Multi-admin RBAC
- [ ] Hardened production deployment guidance

---

# What BSC DLP does **not** claim today

To keep the project technically honest:

- it is **not** an EDR/XDR replacement;
- it does not yet provide Windows kernel pre-write blocking;
- Browser Guard is DOM-level best-effort enforcement, not a network security proxy;
- desktop messaging does not read/decrypt chats;
- WhatsApp Web protection does not bypass E2EE;
- screenshot clipboard blocking happens after capture/OCR;
- broad semantic health/biometric/genetic/protected-attribute classification is not falsely claimed through simple regex;
- Email DLP and AI DLP remain roadmap modules;
- local SQLite is the Community/default architecture, not a hyperscale storage claim;
- public/Internet deployment requires additional hardening and TLS architecture.

---

# Contributing

Community contributions are welcome.

Please read:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)

Useful contribution areas include:

- classifier accuracy;
- false-positive reduction;
- Windows/Linux endpoint telemetry;
- browser integrations;
- OCR/document parsers;
- semantic classification;
- policy/risk logic;
- tests;
- internationalization;
- documentation.

---

# License

BSC DLP Community is distributed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [`LICENSE`](LICENSE) for the complete license text.

---

<div align="center">
  <img src="dashboard/assets/bsc-dlp-icon.png" width="92" alt="BSC DLP" />

  <br>

  **BSC DLP Community**

  <sub>Detect • Classify • Correlate • Control • Protect</sub>

  <br><br>

  🩷 Open source. Community driven. Built for practical data protection.
</div>
