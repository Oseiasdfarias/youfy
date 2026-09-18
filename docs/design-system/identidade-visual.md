# Identidade Visual & Design System

Esta documentação consolida os princípios de design, identidade visual, componentes de UI/UX, animações acústicas e especificações do reprodutor musical do **Youfy**.

---

## 1. Conceito Central: "Monolith Wave"

A identidade do Youfy é ancorada na união entre o minimalismo industrial suíço (estilo Vercel / Dieter Rams) e o processamento de sinais de áudio de alta precisão:

<div align="center" style="margin: 2rem 0;">
  <div class="youfy-ds-banner" style="border-radius: 12px; border: 1px solid var(--vercel-border-color); overflow: hidden; max-width: 1000px; box-shadow: 0 16px 36px -10px rgba(0, 0, 0, 0.7); background: #09090b;">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640" width="100%" height="auto" style="display: block;">
      <!-- Background & Grid -->
      <rect width="1280" height="640" fill="#09090B"/>
      <defs>
        <pattern id="ds-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#18181B" stroke-width="1"/>
        </pattern>
        <radialGradient id="ds-glow" cx="80%" cy="30%" r="60%">
          <stop offset="0%" stop-color="#27272A" stop-opacity="0.6"/>
          <stop offset="100%" stop-color="#09090B" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="ds-eqGrad" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stop-color="#FFFFFF"/>
          <stop offset="85%" stop-color="#A1A1AA"/>
          <stop offset="100%" stop-color="#FF5500"/>
        </linearGradient>
      </defs>
      <rect width="1280" height="640" fill="url(#ds-grid)"/>
      <rect width="1280" height="640" fill="url(#ds-glow)"/>

      <!-- Top Metadata Bar -->
      <g transform="translate(80, 80)">
        <rect x="0" y="0" width="1120" height="40" rx="8" fill="#121215" stroke="#27272A" stroke-width="1"/>
        <circle cx="24" cy="20" r="4" fill="#22C55E"/>
        <text x="38" y="25" fill="#A1A1AA" font-family="'Geist Mono', monospace" font-size="13" font-weight="500">YOUFY // SPEC-1: MINIMAL CLOSED-LOOP</text>
        <text x="560" y="25" fill="#71717A" font-family="'Geist Mono', monospace" font-size="13">DATASET: fma_small (8,000 TRACKS • 30s)</text>
        <text x="980" y="25" fill="#FF5500" font-family="'Geist Mono', monospace" font-size="13" font-weight="600">STATE: ACTIVE</text>
      </g>

      <!-- Hero Main Identity -->
      <g transform="translate(80, 180)">
        <!-- Monolith Square Icon -->
        <rect x="0" y="0" width="120" height="120" rx="28" fill="#121215" stroke="#27272A" stroke-width="2"/>
        <path d="M35 32.5L53.75 60V87.5H66.25V60L85 32.5H71.25L60 50L48.75 32.5H35Z" fill="#FFFFFF"/>
        <circle cx="60" cy="98.5" r="4.5" fill="#FF5500"/>

        <!-- Typography -->
        <text x="160" y="70" fill="#FFFFFF" font-family="'Geist', -apple-system, BlinkMacSystemFont, sans-serif" font-weight="800" font-size="76" letter-spacing="-3">youfy</text>
        <circle cx="365" cy="35" r="6" fill="#FF5500"/>
        <text x="165" y="110" fill="#A1A1AA" font-family="'Geist', sans-serif" font-weight="400" font-size="22" letter-spacing="-0.5">
          Closed-Loop Music Intelligence &amp; MLOps Platform
        </text>
      </g>

      <!-- Soundwave / Equalizer Graphic (Middle-Right) -->
      <g transform="translate(840, 240)">
        <rect x="0" y="60" width="6" height="40" rx="3" fill="#3F3F46"/>
        <rect x="14" y="45" width="6" height="55" rx="3" fill="#52525B"/>
        <rect x="28" y="20" width="6" height="80" rx="3" fill="#71717A"/>
        <rect x="42" y="35" width="6" height="65" rx="3" fill="#A1A1AA"/>
        <rect x="56" y="10" width="6" height="90" rx="3" fill="#D4D4D8"/>
        <rect x="70" y="30" width="6" height="70" rx="3" fill="#FFFFFF"/>
        <rect x="84" y="5" width="6" height="95" rx="3" fill="url(#ds-eqGrad)"/>
        <rect x="98" y="25" width="6" height="75" rx="3" fill="#FFFFFF"/>
        <rect x="112" y="40" width="6" height="60" rx="3" fill="#D4D4D8"/>
        <rect x="126" y="15" width="6" height="85" rx="3" fill="#A1A1AA"/>
        <rect x="140" y="50" width="6" height="50" rx="3" fill="#71717A"/>
        <rect x="154" y="30" width="6" height="70" rx="3" fill="#52525B"/>
        <rect x="168" y="65" width="6" height="35" rx="3" fill="#3F3F46"/>
        <text x="0" y="125" fill="#71717A" font-family="'Geist Mono', monospace" font-size="11">22050 Hz • 128 MEL BINS • HOP 512</text>
      </g>

      <!-- Technical Value Cards (Bottom Grid) -->
      <g transform="translate(80, 370)">
        <rect x="0" y="0" width="260" height="150" rx="12" fill="#101014" stroke="#27272A" stroke-width="1"/>
        <text x="24" y="36" fill="#71717A" font-family="'Geist Mono', monospace" font-size="11" font-weight="600">01 // DATA PIPELINE</text>
        <text x="24" y="68" fill="#FFFFFF" font-family="'Geist', sans-serif" font-weight="700" font-size="18">Idempotent Ingestion</text>
        <text x="24" y="94" fill="#A1A1AA" font-family="'Geist', sans-serif" font-size="13">Quarentena em ingest_failures sem falhar pipeline.</text>
        <circle cx="24" cy="126" r="3" fill="#22C55E"/>
        <text x="34" y="129" fill="#22C55E" font-family="'Geist Mono', monospace" font-size="10">FAIL_RATE &lt; 2% GATE</text>

        <rect x="286" y="0" width="260" height="150" rx="12" fill="#101014" stroke="#27272A" stroke-width="1"/>
        <text x="310" y="36" fill="#71717A" font-family="'Geist Mono', monospace" font-size="11" font-weight="600">02 // CACHE INVALIDATION</text>
        <text x="310" y="68" fill="#FFFFFF" font-family="'Geist', sans-serif" font-weight="700" font-size="18">Feature Fingerprint</text>
        <text x="310" y="94" fill="#A1A1AA" font-family="'Geist', sans-serif" font-size="13">Hash SHA-256 no spec de features com cache zero poisoning.</text>
        <circle cx="310" cy="126" r="3" fill="#3B82F6"/>
        <text x="320" y="129" fill="#3B82F6" font-family="'Geist Mono', monospace" font-size="10">SAFE RESUME &amp; CACHE</text>

        <rect x="572" y="0" width="260" height="150" rx="12" fill="#101014" stroke="#27272A" stroke-width="1"/>
        <text x="596" y="36" fill="#71717A" font-family="'Geist Mono', monospace" font-size="11" font-weight="600">03 // ML INTEGRITY</text>
        <text x="596" y="68" fill="#FFFFFF" font-family="'Geist', sans-serif" font-weight="700" font-size="18">Zero Artist Leakage</text>
        <text x="596" y="94" fill="#A1A1AA" font-family="'Geist', sans-serif" font-size="13">Partições estritas de artistas provadas via Hypothesis.</text>
        <circle cx="596" cy="126" r="3" fill="#A855F7"/>
        <text x="606" y="129" fill="#A855F7" font-family="'Geist Mono', monospace" font-size="10">art(train) ∩ art(test) = ∅</text>

        <rect x="858" y="0" width="262" height="150" rx="12" fill="#101014" stroke="#27272A" stroke-width="1"/>
        <text x="882" y="36" fill="#71717A" font-family="'Geist Mono', monospace" font-size="11" font-weight="600">04 // STACK</text>
        <text x="882" y="68" fill="#FFFFFF" font-family="'Geist', sans-serif" font-weight="700" font-size="18">Modern Tooling</text>
        <text x="882" y="94" fill="#A1A1AA" font-family="'Geist', sans-serif" font-size="13">Python 3.12 • uv • PyTorch • DVC • MLflow • PostgreSQL • FastAPI</text>
        <circle cx="882" cy="126" r="3" fill="#FF5500"/>
        <text x="892" y="129" fill="#FF5500" font-family="'Geist Mono', monospace" font-size="10">REPRODUCIBLE RUNS</text>
      </g>

      <!-- Bottom Line -->
      <line x1="80" y1="580" x2="1200" y2="580" stroke="#27272A" stroke-width="1"/>
      <text x="80" y="605" fill="#52525B" font-family="'Geist Mono', monospace" font-size="11">OPEN SOURCE MIR BENCHMARK • LICENSE: MIT • REPO: github.com/Oseiasdfarias/youfy</text>
    </svg>
  </div>
</div>

### Elementos do Símbolo
- **Monograma `Y`:** Construído por hastes geométricas de espessura balanceada que evocam a convergência de canais estéreo e nós de processamento.
- **Ponto Âmbar (`#FF5500 Amber Peak`):** Representa o pico de intensidade sonora no espectrograma acústico, conferindo contraste dinâmico à base monocromática.
- **Proporção e Grid:** Concebido sob grid modular de 4px e 8px, garantindo legibilidade perfeita desde 16px (favicon) até outdoors e banners em alta resolução.

---

## 2. Tokens de Design (Design Tokens)

### 2.1 Paleta de Cores

| Token | Dark Mode | Light Mode | Uso Principal |
|---|---|---|---|
| `surface-primary` | `#000000` | `#FFFFFF` | Fundo principal da aplicação |
| `surface-secondary` | `#09090B` | `#FAFAFA` | Cartões, barras laterais e painéis |
| `surface-tertiary` | `#18181B` | `#F4F4F5` | Inputs, blocos de código e tabelas |
| `border-subtle` | `#27272A` | `#E4E4E7` | Linhas divisórias e contornos |
| `text-primary` | `#EDEDED` | `#111111` | Títulos e textos de alto contraste |
| `text-secondary` | `#A1A1AA` | `#71717A` | Metadados técnicos, legendas e rótulos |
| `accent-peak` | `#FF5500` | `#FF5500` | Pico de áudio, status ativo e indicador de volume |
| `status-ok` | `#22C55E` | `#16A34A` | Indicador de saúde, quarentena 0% e predição segura |

### 2.2 Tipografia

- **Interface & Títulos:** `Geist Sans`, `-apple-system`, `BlinkMacSystemFont` (tracking otimizado: `-0.02em`).
- **Código & Metadados Técnicos:** `Geist Mono`, `ui-monospace`, `monospace` (para fingerprints SHA-256, frequências e IDs de faixas).
- **Logotipos & Números:** `Space Grotesk` (geométrica e limpa).

---

## 3. Especificação do Reprodutor Musical (UI/UX)

O player do Youfy não é apenas um reprodutor; é o **consumidor de inferência e emissor de telemetria do sistema de MLOps**.

```
┌────────────────────────────────────────────────────────────────────────┐
│  fma:track:001005 • fma_small                     [ Rock: 94.2% ] ●    │
│  Aura of the Latent Valley                        model_version: v1.2  │
│  Synthetic Artist #14 • Album: Discrete Waveforms                      │
│                                                                        │
│  ▄ ▆ █ ▇ █ ▆ ▄ █ ▇ ▆ ▄ █ ▇ ▅ ▃ ▂ (128-mel melspec visualizer)          │
│  00:14 ─────────────────────────────●────────────────────── -00:16    │
│                                                                        │
│  ⏮   [ ▶ ]   ⏭      ● actor: human:osfarias | surface: search         │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Painel de Predição de ML em Tempo Real
- **Gênero Predito e Confiança:** Exibe a probabilidade calibrada da classe vencedora (ex: `Rock: 94.2%`).
- **`model_version` Obrigatória:** Toda tela do reprodutor indica a versão exata do modelo em execução no `serving`.
- **Modo Degradado (503):** Quando não há modelo promovido para `Production`, o badge exibe `[ No Model 503 ]` em tom neutro, sem fallback falso.

### 3.2 Visualizador de Áudio e Animação de Frequência
A animação do espectrograma utiliza CSS Keyframes sincronizados para simular as bandas de frequência mel (`128-mel bins`):

```css
@keyframes eqBar {
  0%, 100% { height: 18%; }
  50% { height: 95%; }
}

.eq-bar-active {
  animation: eqBar 1.1s ease-in-out infinite;
  background: linear-gradient(to top, #ffffff, #a1a1aa 85%, #ff5500 100%);
}
```

### 3.3 Barra de Telemetria de Eventos
Exibe a emissão atômica dos eventos para o event store:
- `actor_id` (`human:osfarias` ou `sim:u00412`).
- `event_type` (`play_start`, `pause`, `seek`, `skip`, `complete`).
- `context.surface` (`search`, `queue`, `recommendation`).

---

## 4. Adaptação para Terminal TUI (Textual)

Para a implementação da interface em terminal da Spec 1C (`packages/player`):
- **Cores ANSI:** Mapeamento direto de tokens (preto `#09090B` $\rightarrow$ ANSI 232, texto branco $\rightarrow$ ANSI 255, âmbar $\rightarrow$ ANSI 202).
- **Espectrograma ASCII/Unicode:** Uso de caracteres de bloco fracionários (` `, `▂`, `▃`, `▄`, `▅`, `▆`, `▇`, `█`) atualizados pelo tick do player a cada 100ms.
- **Teclas de Atalho:** `Space` (Play/Pause), `j`/`k` (Navegação na lista), `/` (Busca no catálogo), `q` (Sair).

---

## 5. Laboratório Interativo de Design (Showcase)

Explore o laboratório interativo com os três conceitos desenvolvidos, variações de favicon, banners e mockups de interface com alternância de tema Light/Dark:

<div style="border: 1px solid var(--vercel-border-color); border-radius: 12px; overflow: hidden; margin: 1.5rem 0;">
  <iframe src="../showcase.html" style="width: 100%; height: 720px; border: none;" title="Youfy Design Lab"></iframe>
</div>

> [!TIP]
> Você também pode abrir o laboratório interativo em tela cheia acessando [showcase.html](showcase.html).
