<p align="center"><a href="README.md">English</a> &nbsp; / &nbsp; <a href="README.tr.md">Türkçe</a></p>

<p align="center"><img src="assets/readme-hero.en.svg" width="840" alt="CipherOps — yerel otonom yapay zeka ajanı"></p>

<p align="center">
<a href="https://github.com/idginity124/CipherOps/actions/workflows/ci.yml"><img src="https://github.com/idginity124/CipherOps/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
&nbsp;
<a href="LICENSE"><img src="https://img.shields.io/badge/lisans-MIT-blue" alt="MIT lisansı"></a>
&nbsp;
<img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python 3.10+">
&nbsp;
<img src="https://img.shields.io/badge/çalışır-tamamen%20yerel-blueviolet" alt="Tamamen yerel">
&nbsp;
<img src="https://img.shields.io/badge/testler-35%20geçti-brightgreen" alt="35 test">
&nbsp;
<img src="https://img.shields.io/badge/guardrails-4%20katman-orange" alt="4 katman güvenlik">
</p>

<p align="center">
Tamamen kendi bilgisayarınızda çalışan bir yapay zeka ajanı.<br>
Dosya okur, terminal komutları çalıştırır, kod düzeltir — <strong>dışarıya hiçbir şey göndermeden</strong>.
</p>
<p align="center"><sub><a href="https://ollama.com">Ollama</a> üzerine kurulu · Gizlilik ve kurumsal ortamlar için tasarlandı · KVKK / GDPR uyumlu</sub></p>

<p align="center"><img src="assets/terminal-demo.svg" width="840" alt="CipherOps terminal oturumu"></p>

---

<h2 align="center">Ne yapar</h2>

<table align="center">
<tr>
  <th align="center">⚡ Hareket eder</th>
  <th align="center">🛡️ Korur</th>
  <th align="center">📋 Kayıt tutar</th>
</tr>
<tr>
  <td align="center">Adım adım terminal komutları çalıştırır, dosya okur/yazar, kod hatalarını bulup düzeltir.</td>
  <td align="center">Yıkıcı komutları koşulsuz engeller. Riskli her adımda sizden onay alır. Her aracı 4 katmanlı güvenlik duvarına sokar.</td>
  <td align="center">Her işlem yapılandırılmış bir denetim günlüğüne yazılır, istediğiniz zaman inceleyebilirsiniz. Ekleme-tabanlı, asla değiştirilmez.</td>
</tr>
</table>

<p align="center">
  Model göndermeden önce hassas veri maskeleme &nbsp;·&nbsp; 4 katmanlı komut güvenlik duvarı &nbsp;·&nbsp; İnsan onaylı yürütme &nbsp;·&nbsp; Çalıştırma sarmalayıcı engelleme &nbsp;·&nbsp; Thread-safe denetim günlüğü
</p>

---

## Nasıl çalışır

CipherOps bir **ReAct döngüsü** izler: hedefe bakar, bir araç seçer, çalıştırır, çıktıyı okur ve görev bitene ya da sizin müdahaleniz gerekene kadar devam eder.

```
Kullanıcı mesajı
    │
    ▼
Gizlilik filtresi  ←── TCKN · IBAN · kredi kartı · API anahtarı · e-posta burada maskelenir
    │
    ▼
Ajan çekirdeği  ←── Düşün · planla · araç çağır · gözlemle · tekrarla (en fazla 15 adım)
    │
    ├── execute_bash    ←── 4 katman güvenlik + çalıştırma sarmalayıcı engelleme
    ├── read_file       ←── 5 MB güvenlik sınırı, satır aralığı desteği
    ├── write_file      ←── Yol güvenliği (/etc /dev /sys engeli) + 10 MB sınırı
    └── list_directory
    │
    ▼
Denetim günlüğü  ←── Her olay için ek-tabanlı JSON Lines kaydı
```

Yerel LLM (Ollama üzerinden sunulan) tek çıkarım motorudur. **OpenAI anahtarı gerekmez. Verileriniz makineden çıkmaz.**

---

## Güvenlik katmanları

| Katman | Ne yapar |
|---|---|
| **PII filtresi** | TCKN, IBAN, kredi kartı, API anahtarı, e-posta ve telefon numaralarını model görmeden önce siler |
| **Komut güvenlik duvarı** | 4 kademe: `SAFE` → serbestçe çalışır · `CAUTION` → onay gerekir · `HIGH` → onay gerekir · `BLOCKED` → asla çalışmaz |
| **Çalıştırma sarmalayıcı engeli** | `bash -c`, `eval`, `python3 -c`, `env`, `xargs`, `nohup` ve 15+ sarmalayıcı koşulsuz engellenir |
| **Yol güvenliği** | `write_file`, `/etc`, `/dev`, `/sys`, `/bin`, `/root` gibi sistem dizinlerine yazmayı reddeder |
| **Fail-safe onay** | Onay callback'i yoksa CAUTION/HIGH komutlar sessizce çalışmak yerine engellenir |

---

## Kurulum

Python 3.10 veya üzeri gereklidir.

### 1. Ollama ve model kurulumu

```bash
# AMD GPU'lu Arch / CachyOS için (ROCm)
sudo pacman -S ollama-rocm
sudo systemctl enable --now ollama
ollama pull qwen2.5-coder:14b
```

NVIDIA veya yalnızca CPU için `ollama-rocm` yerine `ollama-cuda` ya da `ollama` kullanın. Ollama'da araç çağırmayı destekleyen herhangi bir model çalışır (ör. `llama3.1`, `mistral-nemo`, `deepseek-coder-v2`).

### 2. CipherOps kurulumu

```bash
git clone https://github.com/idginity124/CipherOps.git
cd CipherOps
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Kurulumu kontrol edin

```bash
cipherops doctor
```

```
  Bileşen                Durum       Detay
  Python Sürümü          OK          3.14.9
  Ollama Servisi         AKTİF       http://localhost:11434 bağlı
  Yerel Modeller         BULUNDU     qwen2.5-coder:14b
  Denetim Günlüğü        AYARLANDI   /home/kullanici/.cipherops/audit
```

---

## Kullanım

### Tekil görev

```bash
cipherops run "Bu projedeki tüm TODO yorumlarını bulup dosyalara göre grupla"
cipherops run "src/ içinde gömülü kimlik bilgisi var mı kontrol et ve raporla"
cipherops run "Her modülün ne yaptığını özetleyen MODULES.md dosyası oluştur"
```

### Etkileşimli oturum

```bash
cipherops chat
```

```
CipherOps > src/ içinde kırık import var mı kontrol et
🧠 Adım 1: Durum analiz ediliyor ve plan yapılıyor...
⚙️  read_file: src/cipherops/core/agent.py
⚙️  execute_bash: grep -rn "^import\|^from" src/
   ↳ BAŞARILI — kırık import bulunamadı

CipherOps > clear    ← konuşma geçmişini sıfırlar
✓ Konuşma geçmişi temizlendi.

CipherOps > exit
Oturum sonlandı. Görüşmek üzere! 👋
```

### İnsan onayı sistemi

Ajan durumu değiştirecek bir komut çalıştırmak istediğinde durur ve sorar:

```
⚙️  execute_bash: rm -f eski_loglar/*.log

  ┌────────────────────────────────────────────────────┐
  │  🛡️  Operatör Onayı Gerekiyor                      │
  │  GÜVENLİK RİSK DEĞERLENDİRMESİ: HIGH              │
  │  Sebep: Yüksek riskli işlem tespit edildi: 'rm'    │
  │  Komut: rm -f eski_loglar/*.log                    │
  └────────────────────────────────────────────────────┘
  Bu komutu çalıştırayım mı? [y/N]:
```

`rm -rf /`, `mkfs`, `dd if=... of=/dev/sda`, fork bomb, `bash -c`, `eval` gibi yıkıcı kalıplar **koşulsuz engellenir** ve bu ekrana asla ulaşmaz.

---

## Gizlilik ve uyumluluk

Gizlilik filtresi, kullanıcının mesajı modele gönderilmeden önce çalışır. Hassas veri tespit edilirse maskelenir ve denetim günlüğüne güvenlik olayı olarak yazılır.

| Tür | Tespit edilen örnek | Yerine yazılan |
|---|---|---|
| TC Kimlik No (TCKN) | `10000000146` | `[REDACTED_TCKN]` |
| IBAN | `TR33 0006 1005 1112 3456 7890 12` | `[REDACTED_IBAN]` |
| Kredi kartı | `4111 1111 1111 1111` | `[REDACTED_CARD]` |
| API anahtarı / token | `sk-proj-...`, `ghp_...`, `AKIA...` | `[REDACTED_API_KEY]` |
| E-posta | `kullanici@example.com` | `[REDACTED_EMAIL]` |
| Türk telefonu | `0532 123 45 67` | `[REDACTED_PHONE]` |

TCKN için yanlış pozitifi azaltmak amacıyla resmi 11 haneli checksum algoritması kullanılır.

Her ajan eylemi yapılandırılmış bir kayıt üretir:

```json
{
  "timestamp": "2025-11-10T18:30:01.123Z",
  "event_type": "tool_execution",
  "level": "INFO",
  "tool_name": "execute_bash",
  "command_or_input": "{\"command\": \"ls -la\"}",
  "output_summary": "total 32 drwxr-xr-x ...",
  "exit_code": 0,
  "human_approved": true
}
```

Günlükler `~/.cipherops/audit/` dizinine günlük dosyalar hâlinde, ek-tabanlı JSON Lines formatında yazılır.

---

## Proje yapısı

```
CipherOps/
├── src/cipherops/
│   ├── core/
│   │   ├── agent.py           ReAct döngüsü, context budama, olay geri çağırmaları
│   │   └── llm.py             Ollama HTTP istemcisi, araç çağrısı ayrıştırma
│   ├── guardrails/
│   │   ├── pii_sanitizer.py   Regex + checksum tespiti, tek geçişli maskeleme
│   │   └── command_validator.py  4 katman güvenlik + sarmalayıcı engelleme
│   ├── tools/
│   │   ├── base.py            BaseTool arayüzü, ToolResult
│   │   ├── bash_tool.py       Fail-safe onaylı shell yürütücü
│   │   ├── file_tool.py       Okuma (5 MB) · Yazma (yol koruması + 10 MB) · Listeleme
│   │   └── registry.py        Araç kaydı ve fabrika
│   ├── audit/
│   │   └── logger.py          Thread-safe ek-tabanlı JSON Lines günlükçü
│   └── cli.py                 Typer CLI — doctor · run · chat
└── tests/
    ├── test_guardrails.py     PII maskeleme + komut güvenlik duvarı (5 test)
    ├── test_tools.py          BashTool + dosya araçları (22 test)
    └── test_audit.py          AuditLogger + thread güvenliği (7 test + 1 stress)
```

---

## Testler

```bash
source .venv/bin/activate
pytest tests/ -v
```

```
tests/test_audit.py::TestAuditLogger::test_log_creates_file               PASSED
tests/test_audit.py::TestAuditLogger::test_thread_safety                  PASSED
...
tests/test_tools.py::TestBashTool::test_execution_wrapper_blocked         PASSED
tests/test_tools.py::TestWriteFileTool::test_blocked_system_path_etc      PASSED
...
tests/test_guardrails.py::test_tckn_masking                               PASSED
tests/test_guardrails.py::test_command_firewall_blocks_catastrophic       PASSED

35 passed in 0.12s
```

---

## Özel araç ekleme

```python
from cipherops.tools.base import BaseTool, ToolResult
from cipherops.tools.registry import create_default_registry

class WebAramaTool(BaseTool):
    name = "web_search"
    description = "İnternette ara ve sonuçların özetini döndür"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Arama sorgusu"}
        },
        "required": ["query"],
    }

    def execute(self, query: str, **kwargs) -> ToolResult:
        # kendi implementasyonunuz
        return ToolResult(success=True, output=f"Sonuçlar: {query}")

# Oturum başlamadan önce kaydedin
registry = create_default_registry()
registry.register(WebAramaTool())
```

---

## Yol haritası

- [ ] Oturumlar arası vektör hafızası (ChromaDB)
- [ ] Web arama ve tarayıcı otomasyon aracı
- [ ] Çok ajanlı mimari: planlayıcı + yürütücü ayrımı
- [ ] Headless / CI kullanımı için FastAPI sunucu modu
- [ ] Docker sandboxed yürütme ortamı
- [ ] Terminalde akışlı LLM çıktısı

Bunlar bu sürümdeki özellikler değil, plandakiler.

---

## Katkı

Katkılarınızı bekliyoruz! Pull request açmadan önce lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasını okuyun.

<br>
<p align="center"><img src="assets/training-arc.en.svg" width="840" alt="The Training Arc — Ekrem Bulgan"></p>
<p align="center"><a href="https://www.ekrembulgan.com">Ekrem Bulgan</a> &nbsp; / &nbsp; <a href="https://linkedin.com/in/ekrembulgan">LinkedIn</a></p>
<p align="center"><sub>MIT lisanslı · <a href="LICENSE">Lisans</a></sub></p>
