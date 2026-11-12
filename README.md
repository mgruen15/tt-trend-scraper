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

**Momentum** wird aus der Popularitätskurve (0–100, normiert auf den Höchstwert im Zeitraum) abgeleitet:
▲ *Steigend* (Höchstwert ganz aktuell, Kurve klar wachsend) · ● *Hoch* (≥ 60 % des Höchstwerts) ·
▼ *Abflauend* (Höhepunkt vorbei, < 60 %).

## Datenquelle & Grenzen

Das Creative Center ist inzwischen Teil von „TikTok One". Ohne Login liefert der Endpunkt
`POST /CreativeOne/KnowledgeAPI/GetHashtagList` **max. die Top 3 pro Abfrage**. Der Scraper fragt deshalb
jede Kombination aus Land × Branche × Zeitraum einzeln ab (1.107 Requests, ~2,5 Min.):

- 27 Länder × (Gesamt + 19 Branchen) × 7 und 30 Tage
- 27 Länder × Gesamt × 90 Tage (für 90 Tage gibt es nur das Gesamt-Ranking)

Video-, Creator- und Song-Trends sowie Hashtag-Details erfordern inzwischen einen Login und sind daher nicht enthalten.
Die API ist inoffiziell – ändert TikTok sie, schlägt der Lauf fehl (bei > 30 % Fehlern werden keine Daten überschrieben).

## Wo liegen die Ergebnisse?

Der Workflow schreibt das Ergebnis auf den Branch **`data`** – dieser enthält immer genau einen Commit
mit dem aktuellen Stand (so wächst das Repo nicht mit jedem Lauf):

```
index.html          # Dashboard (Daten eingebettet)
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
.github/workflows/scrape.yml   Cron 4×/Tag (05:17, 11:17, 17:17, 23:17 UTC) + manueller Start
```

## Kosten

Ein Lauf dauert ~3–4 Minuten. 4 Läufe/Tag ≈ 500 Actions-Minuten/Monat – passt in das kostenlose
Kontingent privater Repos (2.000 Min./Monat); öffentliche Repos sind ohnehin kostenlos.
