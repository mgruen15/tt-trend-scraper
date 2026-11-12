# TikTok Trend Radar

**Live-Dashboard: https://mgruen15.github.io/tt-trend-scraper/**

Scraper + Dashboard für die viralsten Hashtags aus dem
[TikTok Creative Center](https://ads.tiktok.com/creative/creativeCenter/trends/hashtag).
Läuft 4× täglich über GitHub Actions und erzeugt ein einzelnes, eigenständiges
HTML-Dashboard (`index.html`, Daten eingebettet – funktioniert auch offline per Doppelklick).

## Was das Dashboard zeigt

| Bereich | Inhalt |
|---|---|
| **Auf einen Blick** | Platz 1, stärkster Aufsteiger, Views-Spitze, größter länderübergreifender Trend |
| **Offizielle Top 3** | TikToks eigenes Gesamt-Ranking mit Popularitätskurve, Views, Posts, Ø Views/Post, Top-Creators |
| **Trend-Radar** | ~55 Trend-Hashtags pro Land (Top 3 aus jeder der 19 Branchen, zusammengeführt) – filterbar nach Momentum/Branche, sortierbar, mit „NEU"-Markierung und Views-Zuwachs seit dem letzten Lauf |
| **Länderübergreifend** | Hashtags, die gleichzeitig in mehreren der 27 Länder trenden |
| **Gerade am Steigen** | Hashtags, deren Kurve aktuell am Höchststand ist und wächst |
| **Nach Branche** | Top 3 je Branche |

Land und Zeitraum (7 / 30 / 90 Tage) sind oben umschaltbar; der Zustand steht in der URL (`#DE/7`).

## Agent-Ansicht (für KI-Agents)

Oben rechts auf **Agent** umschalten (oder `#DE/7/agent`). Dort gibt es einen fertigen Prompt zum Kopieren.
Die Daten liegen zusätzlich als reiner Text vor, damit ein Agent sie mit wenigen Tokens lesen kann:

| Datei | Inhalt |
|---|---|
| [`llms.txt`](https://mgruen15.github.io/tt-trend-scraper/llms.txt) | Leseanleitung für Agents: Spalten, Score-Formel, Vorgehen vom Thema zum Skript |
| `agent/<LAND>.tsv` (z. B. [`agent/DE.tsv`](https://mgruen15.github.io/tt-trend-scraper/agent/DE.tsv)) | alle ~150 Trend-Hashtags des Landes aus 7/30/90 Tagen, nach Opportunity-Score sortiert (~7K Tokens) |
| `agent/top.tsv` | Top 10 je Land |
| `agent/global.tsv` | länderübergreifende Trends |

Pro Hashtag: Score (0–100), Branche, offizieller Rang, Momentum je Zeitraum, Views, Posts, Views/Post,
Views-Zuwachs seit dem letzten Lauf, Popularitätskurven als Ziffernfolge (`0125799`), Verbreitung über Länder,
Flags (N = neu, E = Evergreen, X = kurzfristige Welle) und Top-Creators mit Followerzahl.

Der **Opportunity-Score** setzt sich zusammen aus: Momentum der letzten 7 Tage, Views pro Post im Vergleich zum Land
(wenig Konkurrenz), ob kleine Creator unter den Top-Creators sind, Verbreitung über Länder und Frische.
Die genaue Formel steht in `llms.txt`.

Beispiel-Prompt:

```
Lies https://mgruen15.github.io/tt-trend-scraper/llms.txt und danach .../agent/DE.tsv.
Ich möchte ein TikTok-Video über <Thema> posten (Nische: <Nische>). Wähle passende Trend-Hashtags
und schreibe ein Skript, das die Chance auf Viralität maximiert.
```

**Momentum** wird aus der Popularitätskurve (0–100, normiert auf den Höchstwert im Zeitraum) abgeleitet:
▲ *Steigend* (Höchstwert ganz aktuell, Kurve klar wachsend) · ● *Hoch* (≥ 60 % des Höchstwerts) ·
▼ *Abflauend* (Höhepunkt vorbei, < 60 %).

## Datenquelle & Grenzen

Das Creative Center ist inzwischen Teil von „TikTok One". Ohne Login liefert der Endpunkt
`POST /CreativeOne/KnowledgeAPI/GetHashtagList` **max. die Top 3 pro Abfrage**. Der Scraper fragt deshalb
jede Kombination aus Land × Branche × Zeitraum einzeln ab:
27 Länder × (Gesamt + 19 Branchen) × 7/30/90 Tage = 1.620 Requests (~4 Min.).

Top Ads, Video-, Creator- und Song-Trends sowie Hashtag-Details erfordern inzwischen einen Login bzw. signierte
Anfragen und sind daher bewusst nicht enthalten.
Die API ist inoffiziell – ändert TikTok sie, schlägt der Lauf fehl (bei > 30 % Fehlern werden keine Daten überschrieben).

## Wo liegen die Ergebnisse?

Der Workflow schreibt das Ergebnis auf den Branch **`data`** – dieser enthält immer genau einen Commit
mit dem aktuellen Stand (so wächst das Repo nicht mit jedem Lauf):

```
index.html          # Dashboard (Daten eingebettet)
llms.txt            # Leseanleitung für Agents
agent/*.tsv         # token-effiziente Trenddaten für Agents
data/latest.json    # aktuelle Daten als JSON
data/history.json   # rollierende Historie (für "NEU" und Views-Zuwachs)
```

Ansehen:

- **Lokal:** `git fetch origin data && git show origin/data:index.html > trends.html && open trends.html`
- **GitHub Pages:** https://mgruen15.github.io/tt-trend-scraper/ (Quelle: Branch `data` / root, wird nach jedem Lauf automatisch neu gebaut).

## Lokal ausführen

Nur Python ≥ 3.10, keine Abhängigkeiten.

```bash
python -m tt_trends.scrape                      # alle Länder → ./site/
python -m tt_trends.scrape --countries DE US    # nur bestimmte Länder
python -m tt_trends.render site                 # Dashboard nach Template-Änderung neu rendern
python -m unittest discover -s tests            # Tests
python -m http.server 8765 --directory site     # oder einfach site/index.html öffnen
```

## Struktur

```
tt_trends/config.py     Länder, Branchen-IDs, Zeiträume
tt_trends/client.py     API-Client (Retries, Backoff)
tt_trends/analysis.py   Zusammenführen, Momentum, globale Trends, Historie
tt_trends/scrape.py     Einstiegspunkt
tt_trends/render.py     Dashboard aus dashboard/template.html erzeugen
tt_trends/agent.py      Agent-Export (llms.txt, agent/*.tsv) inkl. Opportunity-Score
.github/workflows/scrape.yml   Cron 4×/Tag (05:17, 11:17, 17:17, 23:17 UTC) + manueller Start
```

## Kosten

Öffentliches Repo: GitHub Actions und Pages sind kostenlos. Ein Lauf dauert ~5 Minuten.
Damit GitHub den Zeitplan nicht nach 60 Tagen ohne Repo-Aktivität abschaltet, aktiviert sich der Workflow
bei jedem Lauf selbst neu (Keepalive-Schritt).
