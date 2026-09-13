# SOLUTION-CONTEXT — UKCS Oil & Gas Production Explorer

Teknisk referanse for sammenslåing med søsterløsninger for andre land.

Dokumentet er skrevet mot kildekoden, ikke mot `README.md` eller modul-kommentarer. Der en
kommentar påstår noe koden ikke gjør, står avviket beskrevet i §11. Alle påstander har filsti,
og linjenummer der det er relevant.

**Verifisert mot:** commit `c498dcd`, med et fullt ETL-løp kjørt mot live NSTA-tjenester
2026-09-13 (83 sekunder, exit 0). Rådataeksempler er hentet live, ikke rekonstruert.

**Rettelser etter første utgave:** tre av funnene i §11 er nå rettet i koden — `episode_id`
(§11.17), `today_month_start` (§11.3) og SRI-kommentaren (§11.6). Et fjerde, `GASPIPVOLM`
(§11.2), viste seg å være riktig oppførsel som bare manglet begrunnelse. Avsnittene er merket
`RETTET 2026-09-13` og beholdt framfor å slettes: en søsterløsning som bygger det samme trenger
å vite at fellen finnes, ikke bare at den er lukket her.

**Notasjon:** `USIKKER:` markerer noe jeg ikke fikk verifisert.

---

## 1. Oversikt

**Land:** Storbritannia — UK Continental Shelf (UKCS), britisk sokkel.

**Myndighet / kilde:** North Sea Transition Authority (NSTA), tidligere Oil & Gas Authority (OGA).
Alle data kommer fra NSTA. Ingen andre datakilder inngår.

**Hva løsningen gjør:** Bygger et statisk nettsted som viser olje- og gassproduksjon på britisk
sokkel fra juni 1975 til og med juni 2026, månedlig. Tre visninger:

1. **Produksjon** — total UKCS-produksjon i mboe/d, delt på hydrokarbon, selskap eller felt.
2. **Feltkart** — feltpolygoner og produksjonsbobler, med per-felt produksjons- og eierhistorikk.
3. **Lisensportefølje** — gjeldende lisensunderområder og historiske lisenshaver-/operatørnavn.

**Sentral egenskap:** Produksjon tilskrives selskaper via **daterte egenkapitalandeler**
(`etl/equity_artifacts.py`), ikke via operatørskap. Operatørtall finnes også, men er eksplisitt
merket som en mellomstasjon (`etl/transform.py:530-545`).

**Ingen backend.** `etl/build.py` skriver JSON-filer til `docs/data/`, som committes inn i
repoet og serveres statisk. Nettleseren kontakter aldri NSTA eller ArcGIS
(`docs/app/state.js:16-20`, `docs/app/main.js:22-25` — alle URL-er er relative `./data/*`).

---

## 2. Teknologistack

### Kjøretid

| Komponent | Verdi | Kilde |
|---|---|---|
| Språk (ETL) | Python 3.12 i CI | `.github/workflows/build-data.yml:53` |
| Språk (frontend) | Vanilla ES-moduler, ingen rammeverk, ingen byggetrinn | `docs/app/*.js` |
| Database | **Ingen.** Statiske JSON-filer i git | `docs/data/` |
| Hosting | GitHub Pages, rot = `docs/` | live på `sheffielddivided.github.io/ukcs/` |
| CI | GitHub Actions, 2 workflows | `.github/workflows/` |

### Python-avhengigheter

`etl/requirements.txt` — hele listen, tre pakker:

```
requests==2.32.3
openpyxl==3.1.5
beautifulsoup4==4.12.3
```

`beautifulsoup4` brukes kun ett sted: til å skrape lenken på NSTAs Fields-side
(`etl/equity_fetch.py:69-107`). `openpyxl` leser Excel-arbeidsboken med egenkapitalandeler.

Test: `tests/requirements.txt` = `-r ../etl/requirements.txt` + `pytest==8.3.5`.
Frontendtest: `tests/frontend/requirements.txt` = `pytest==8.3.5` + `playwright==1.62.0`.

### Frontend-avhengigheter (kjøretid, fra CDN)

| Bibliotek | Versjon | Lastes som | SRI |
|---|---|---|---|
| MapLibre GL JS | 6.8.0 | ES-modulimport, `docs/app/map.js:17` | **Nei** — se §11.6 |
| MapLibre CSS | 6.8.0 | `<link>`, `docs/index.html:9-11` | Ja, `sha256-ji27qz…` |
| ECharts | 6.1.0 | Injisert `<script>`, `docs/app/charts.js:14-28` | Ja, `sha256-tmslrr…` |
| OSM-rasterfliser | — | `tile.openstreetmap.org/{z}/{x}/{y}.png` | n/a |

ECharts lastes **lazily**, først ved første diagram (`docs/app/charts.js:20-40`).

### Kjøre lokalt

```bash
pip install -r tests/requirements.txt   # trekker inn etl/requirements.txt + pytest
python etl/build.py                     # fullt innsamlingsløp, ~83 s, skriver docs/data/
pytest tests/ --ignore=tests/frontend   # 280 backendtester, ingen nettverk

# frontend (krever Chromium-nedlasting):
pip install -r tests/frontend/requirements.txt
playwright install chromium
pytest tests/frontend                   # 110 tester

# serve nettstedet:
python3 -m http.server -d docs 8000
```

`etl/build.py` tar ingen argumenter og har ingen konfigurasjonsfil. Alt er konstanter i kode.
Det finnes ingen `.env`, ingen hemmeligheter, ingen `--dry-run`.

### Deploy

GitHub Pages bygger automatisk fra `docs/` på `main` ved hver push. Ingen deploy-workflow i
repoet — `pages build and deployment` er GitHubs egen innebygde jobb.

---

## 3. Datakilder

Seks NSTA-datasett. **Ingen krever autentisering** — alt er åpent, ingen API-nøkkel, ingen
token, ingen rate-limit-håndtering utover retry.

### 3.1 PPRS produksjonsrapporter (hoveddatasettet)

| | |
|---|---|
| **Type** | ArcGIS Online FeatureServer, punktgeometri |
| **Item-ID** | `dd38204275a04618ab7ddd00f87224e3` (`etl/build.py:130`) |
| **Oppløst URL** | `https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/UKCS_hydrocarbon_field_production_reports_PPRS_points_(WGS84)/FeatureServer/0` |
| **Format** | Esri JSON (`f=json`), ikke GeoJSON |
| **Autentisering** | Nei |
| **maxRecordCount** | 2000 (verifisert live) |
| **Oppdateringsfrekvens** | Månedlig (PPRS-perioder) |

URL-en er **aldri hardkodet**. Item-ID slås opp mot
`https://www.arcgis.com/sharing/rest/content/items/{item_id}`, og tjeneste-URL leses av
`url`-egenskapen (`etl/arcgis.py:112-123`). Dette gjelder alle ArcGIS-kildene.

**Stabilitet:** Skjemaet er låst. `etl/validate.py:42-58` lister 16 felt med forventet
Esri-type; manglende felt eller typeendring bryter bygget (`validate_schema`,
`etl/validate.py:86-104`). Laget har 46 felt totalt; 14 hentes
(`OUT_FIELDS`, `etl/build.py:159-162`).

En skjema-hash (sha256 over feltnavn+typer) skrives til `docs/data/meta.json`
(`etl/build.py:172-179`), så drift er sporbar mellom bygg.

### 3.2 Field Partners — egenkapitalandeler

| | |
|---|---|
| **Type** | Excel-arbeidsbok (`.xlsx`), Azure Blob Storage |
| **URL** | `https://datanstauthority.blob.core.windows.net/external/Documents/field_partners.xlsx` |
| **Størrelse** | 332 539 byte (målt 2026-09-13) |
| **Autentisering** | Nei |
| **Oppdateringsfrekvens** | Ukentlig (observert: `Last-Modified` endret seg fra `Thu, 10 Sep 2026 12:00:02 GMT` til `Sun, 13 Sep 2026 12:00:02 GMT` på tre dager) |

**Dette er den skjøreste kilden.** URL-en er ikke publisert noe sted som en stabil lenke.
Oppløsningskjeden er tre ledd (`etl/equity_fetch.py:69-185`):

1. Hent `https://www.nstauthority.co.uk/data-and-insights/data/themes/fields/` og finn
   **den ene** `<a>`-taggen hvis synlige tekst nevner «equity»
   (`find_equity_link_and_description`, `etl/equity_fetch.py:69-107`). Null treff eller mer
   enn ett treff → feil, aldri gjetting.
2. Lenken peker ikke på en fil, men på en ArcGIS Hub-**søkeside** (en klientrendret SPA).
   `q`-parameteren trekkes ut (`extract_hub_search_query`, `etl/equity_fetch.py:109-128`).
3. Samme søketekst kjøres mot ArcGIS Online sitt søke-API, avgrenset til org
   `OZMfUznmLTnWccBc` (`resolve_workbook_item`, `etl/equity_fetch.py:131-183`). Det skal gi
   nøyaktig ett treff: «Field Partners», hvis `url` er den direkte nedlastingslenken.

Kun NSTA-sidens URL og org-ID er faste konstanter (`etl/equity_fetch.py:45,51`). Lenketekst,
søketekst og nedlastings-URL utledes på nytt hvert løp.

**Endringsdeteksjon:** sha256 av arbeidsboken skrives til `docs/data/equity/meta.json`.
I tillegg finnes en toleransesjekk på radantall: en endring større enn 10 % av forrige bygg
bryter bygget (`EQUITY_ROW_COUNT_TOLERANCE_FRACTION = 0.10`, `etl/equity_config.py:44`).

**Kolonnestabilitet:** `etl/equity_parse.py:41-58` forventer nøyaktig disse ti kolonnene i ark
`"Report 1"`, i denne rekkefølgen:

```
Field Name | On Offshore | Median Line Flag | Status | Organisation Name
| Percentage Holding | Operator Flag | Start Date | End Date | Equity Share Time Period
```

Kun de fem første feltnavnene under brukes: `Field Name`, `Organisation Name`,
`Percentage Holding`, `Start Date`, `End Date`.

### 3.3 Feltbestemmelser (polygoner)

| | |
|---|---|
| **Item-ID** | `bef8788b07464a7f8a18a18eb638b9f5` (`etl/field_polygons.py:45`) |
| **Geometri** | `esriGeometryPolygon`, WKID 4326 forventet (`etl/field_polygons.py:53-54`) |
| **Felt** | `FIELD_NO`, `FIELDNAME`, `FD_STAT` (`etl/field_polygons.py:47-51`) |
| **Rader** | 344 |

### 3.4 Lisensunderområder etter egenkapitalgruppe

| | |
|---|---|
| **Item-ID** | `40c65d96a1a14da8b066f2abbb345fed` (`etl/licence_portfolio.py:44`, `etl/company_groups.py`) |
| **Rader** | 1 803 |
| **Felt** | `SUBAREANAM, BLOCKREF, LICNO, LICREF, LICSTATUS, LICSTARTDT, LICENDDT, EQGRPHOLD, EQUITY, OPORGGRP` (`etl/licence_portfolio.py:46-57`) |

Brukes til **to** formål: gjeldende lisensportefølje **og** selskapsgrupperingstaksonomien.

### 3.5 Lisensblokk-historikk

| | |
|---|---|
| **Item-ID** | `855237fb38bb44b2afc52a3ea4a48903` (`etl/licence_history.py:47`) |
| **Rader** | 8 886 |
| **Felt** | 14, inkl. `HISTORY, BLOCKREF, BLCKSTRTDT, BLCKENDDT, LICORG, LICORGGRP, OPORG, OPORGGRP, ADMORG, ADMORGGRP` (`etl/licence_history.py:49-64`) |

Dette er det **eneste** av NSTAs lisensdatasett med reell historisk navn- og
daterekonstruksjon. Det bærer **aldri** en egenkapitalprosent, og
`validate_no_fabricated_equity_fields` (`etl/licence_history.py:227-243`) bryter bygget hvis et
slikt felt noen gang dukker opp i artefaktet.

### 3.6 PPRS polygon-følgesvenn — IKKE i bruk

Item-ID `b51887ab2c8547cfb6807cca0ca5fb88` finnes i `etl/discover.py:26`, men `discover.py`
importeres aldri — verken av `build.py` eller av noen annen modul eller test (verifisert:
`grep -rE "^(from|import) discover" etl/*.py tests/*.py` gir null treff). `discover.py` er et
frittstående engangsskript for kildeoppdagelse. Datasettet bidrar til ingen publisert artefakt.

---

## 4. Innsamlingsprosess

### Trigger

| Trigger | Hvor |
|---|---|
| Ukentlig cron, mandag 04:17 UTC | `.github/workflows/build-data.yml:22` |
| Manuell `workflow_dispatch` | `.github/workflows/build-data.yml:23` |
| Lokalt: `python etl/build.py` | — |

PPRS er månedlig; ukentlig plan er valgt for at en forsinket NSTA-publisering plukkes opp
innen dager, ikke en måned (`.github/workflows/build-data.yml:4-6`).

Samtidighetsgruppe `build-data` med `cancel-in-progress: false`
(`.github/workflows/build-data.yml:30-33`) — to løp skal aldri kappes om å committe.
Timeout 20 minutter (`:45`).

### Rekkefølge i CI

```
checkout → pip install → pytest tests/ --ignore=tests/frontend → python etl/build.py
  → last opp arbeidsboken som artifact (90 dagers retensjon)
  → oppdag substansiell endring → commit kun hvis endret
```

Testene kjører **før** bygget henter noe (`.github/workflows/build-data.yml:59-72`). Ingen
`continue-on-error` noe sted i filen.

### Stegene i `etl/build.py:main()`

| # | Steg | Linje |
|---|---|---|
| 1 | Løs item-ID → tjeneste-URL, hent lagmetadata, valider skjema, hash det | 261-267 |
| 2 | `max(PERIODYRMN)` og `min(PERIODYRMN)` via `outStatistics` | 273-274 |
| 3 | Uavhengig `count` for siste periode, så hent radene med geometri | 280-292 |
| 4 | Sjekk paginering mot uavhengig antall; sjekk negative verdier | 294-296 |
| 5 | Last enhetsklassifisering, kjør snubletråd | 298-300 |
| 6 | Aggreger siste periode til feltgrain | 302 |
| 7 | Bounding-box-sjekk (rapporterer observert utstrekning også ved pass) | 320-329 |
| 8 | Hent **full historikk** uten geometri (134 294 rader), samme pagineringssjekk | 334-353 |
| 9 | Aggreger historikk; bygg operatørrollup | 356-375 |
| 10 | Bevaringssjekker (full presisjon, så serialisert) | 377-461 |
| 11 | Feltpolygoner: hent, match mot PPRS-feltnavn | 463-489 |
| 12 | Lisensportefølje og lisenshistorikk | 491-525 |
| 13 | Egenkapitalkjeden (`run_equity_pipeline`) | 560-562 |
| 14 | Selskapsgruppering | ~570 |
| 15 | Oversiktsartefakter + avstemming | ~575 |
| 16 | Delta-sjekk mot forrige bygg | 695-703 |
| 17 | **All validering ferdig** → skriv artefakter atomisk | 539-613 |

### Er den idempotent?

**Ja, for uendret input.** Verifisert empirisk: et fullt gjenoppbygg 2026-09-13 mot committet
data fra 2026-09-10 ga **null** forskjeller i `fields.geojson`, `operators.json`,
`field_polygons.geojson` og `licence_history.geojson`. De filene som skilte seg, skilte seg fordi
kilden faktisk hadde endret seg (se under).

Determinisme sikres ved:
- sortering på slug/feltnavn overalt før serialisering (`etl/transform.py:143,313,465`)
- `orderByFields: OBJECTID` i all paginering (`etl/arcgis.py:185`)
- fast avrunding til 3 desimaler med `-0.0 → 0.0` (`etl/transform.py:36-46`, `etl/mboed.py:75-85`)
- `built_at` er det **eneste** feltet som endres uten at input endret seg — og CI reverterer
  `meta.json` og `overview/meta.json` hvis ingenting annet er endret
  (`.github/workflows/build-data.yml:136-143`)

### Hva skjer ved feil?

**Alt eller ingenting.** All validering kjører før noen fil under `docs/data/` skrives
(`etl/build.py:539-543`). En `ValidationError` eller `BuildError` gir rød jobb, null commits,
urørt `docs/data/`. Det finnes ingen delvis-skriving-sti å beskytte mot.

Hver skriving er i tillegg atomisk (`write_json_atomic`, `etl/build.py:200-209`;
`write_history_dir_atomic`, `:211-231` — staging-katalog og rename).

Nettverksfeil: eksponentiell backoff, 5 forsøk, 30 s per forespørsel
(`etl/arcgis.py:27-29,43-96`). 5xx og transporttfeil retries; **4xx retries ikke** (de er ikke
forbigående). Hard rad-tak på 500 000 (`etl/arcgis.py:30,195-200`) stopper en løpsk
pagineringsløkke.

Feilmeldingene skiller alltid nettverksfeil fra HTTP-feil fra ArcGIS-applikasjonsfeil
(`etl/arcgis.py:33-36`) — aldri en generisk «failed to fetch».

### Hvordan håndteres etterretting av historiske tall?

**Ved full erstatning.** Det finnes ingen inkrementell henting, ingen append, ingen
«hent bare siden sist». Hvert løp henter hele historikken på nytt (`where="1=1"`,
`etl/build.py:340`) og skriver alle 552 felthistorikkfiler på nytt. En NSTA-retting propagerer
automatisk.

**Dette skjer i praksis.** Gjenoppbygget 2026-09-13 mot data fra 2026-09-10 viste at NSTA hadde
rettet assosiert-gass-tall bakover:

```
ANDREW  (docs/data/history/andrew.json):  22 av 361 perioder endret
        endrede perioder: 202107-202110, 202201-202207, 202210, ...
        202107 committet: assoc_gas_mmscfd 15.344 → natural_gas_mboed 2.557 → total_mboed 4.263
        202107 nytt     : assoc_gas_mmscfd 15.819 → natural_gas_mboed 2.636 → total_mboed 4.342
ARUNDEL (docs/data/history/arundel.json):  4 av 106 perioder endret (202107-202110)
```

Ingen perioder ble lagt til eller fjernet — kun verdier rettet, fire til fem år tilbake i tid.

**Konsekvens for en sammenslått løsning:** rettinger er normaldrift, ikke unntak. En arkitektur
som antar at historiske måneder er uforanderlige, og bare henter nye perioder, vil drive fra
kilden. Denne løsningen unngår det ved å alltid hente alt — mulig fordi datasettet er lite
(134 294 rader, ~30 s å hente).

Det finnes **ingen** revisjonshistorikk eller endringslogg i artefaktene. Rettinger er kun
synlige i git-historikken til `docs/data/`.

### Endringsdeteksjon før commit

`.github/workflows/build-data.yml:89-143`. PPRS og egenkapital diffes hver for seg, fordi NSTA
oppdaterer dem uavhengig — commit-meldingen navngir hvilken kilde som faktisk endret seg.

En detalj verdt å kjenne: `docs/data/overview/` sjekkes med `git status --porcelain`, ikke
`git diff`, fordi `git diff` **aldri** rapporterer nye usporede filer uansett stifilter
(`.github/workflows/build-data.yml:120-134`). Uten det ville en helt ny avledet artefakt aldri
blitt committet.

---

## 5. Datamodell

Ingen database. Modellen er JSON-filer på disk under `docs/data/`.

### 5.1 Identifikatorer

| Entitet | ID | Opphav | Generert av |
|---|---|---|---|
| Felt | `FIELDNAME` (tekst, f.eks. `"BUZZARD"`) | **Kilde** (PPRS) | — |
| Felt | `slug` (f.eks. `"buzzard"`) | **Lokal** | `slugify()`, `etl/transform.py:49-57` |
| Rapporteringsenhet | `UNITNAME` | **Kilde** | — |
| Periode | `PERIODYRMN`, `"YYYYMM"` som **streng** | **Kilde** | — |
| Operatør | `ORGGRPNM` + `slug` | Kilde + lokal slug | `etl/transform.py:49` |
| Juridisk enhet | `Organisation Name` + `slug` | Kilde + lokal slug | — |
| Visningsgruppe | `EQGRPHOLD` + `slug` | Kilde + lokal slug | `etl/company_groups.py` |
| Feltpolygon | `FIELD_NO`, `FIELDNAME` | **Kilde** | — |
| Lisens | `LICREF` (f.eks. `"P7"`), `LICNO` | **Kilde** | — |
| Blokk | `BLOCKREF` (f.eks. `"49/26a"`) | **Kilde** | — |

`slugify()` er ren og deterministisk: små bokstaver, ikke-alfanumeriske sekvenser → én bindestrek,
trimmet. Tom slug kaster feil. **Ingen fuzzy-normalisering** — dette er en identifikator, ikke en
matchenøkkel (`etl/transform.py:51-53`).

Frontenden reimplementerer den samme algoritmen i JS (`docs/app/format.js:29-36`) fordi den må
utlede en operatørs slug fra visningsnavnet. **De to må holdes i synk manuelt.**

**Det finnes ingen brønn-entitet.** PPRS rapporterer på felt/rapporteringsenhet, ikke brønn.

### 5.2 `docs/data/meta.json`

Ett objekt. Byggemetadata, ikke produksjonsdata.

| Nøkkel | Type | Eksempel |
|---|---|---|
| `artifact_schema_version` | int | `6` |
| `built_at` | ISO8601 | `"2026-09-10T15:43:08Z"` |
| `earliest_period`, `latest_period` | str YYYYMM | `"197506"`, `"202606"` |
| `field_count`, `field_count_raw` | int | `250`, `250` |
| `history_field_count` | int | `552` |
| `history_record_count` | int | `134294` (rårader) |
| `history_series_point_count` | int | `133608` (skrevne seriepunkter) |
| `record_count` | int | `251` (rårader siste periode) |
| `reporting_unit_count`, `storage_unit_count` | int | `250`, `1` |
| `operator_count`, `operators_split` | int, bool | `50`, `true` |
| `gas_scf_per_boe` | int | `6000` |
| `production_conversion_methodology` | str | `"mboed-v1-6000-scf-per-boe"` |
| `schema_hash` | str | `"sha256:e7889383…"` |
| `sources` | objekt | seks undernøkler, se §3 |
| `notes` | liste[str] | menneskelesbare merknader og resultater fra delta-sjekkene |

Merk `record_count: 251` mot `field_count: 250` — differansen er ROUGH sin lagringsenhet.

### 5.3 `docs/data/fields.geojson`

GeoJSON `FeatureCollection`, 250 features, `Point`-geometri. Siste periode.

| Property | Type | Merknad |
|---|---|---|
| `slug`, `field` | str | lokal / kilde |
| `region` | str | `FIELDAREA`, f.eks. `"CNS"`, `"SNS"` |
| `location` | str | `"Offshore"` / `"Onshore"` |
| `operator` | str | `ORGGRPNM` |
| `period` | str | `"202606"` |
| `unit_count`, `storage_unit_count` | int | antall produksjons-/lagringsenheter |
| `oil_mbd`, `condensate_mbd`, `water_mbd` | float\|null | mb/d, 3 desimaler |
| `assoc_gas_mmscfd`, `dry_gas_mmscfd` | float\|null | MMscf/d, 3 desimaler |
| `liquids_mboed`, `natural_gas_mboed`, `total_mboed` | float\|null | **avledet**, 3 desimaler |
| `notes` | liste[str] | kun til stede ved intern inkonsistens, se §8.3 |

Bygget av `build_fields_geojson`, `etl/transform.py:465-510`.

### 5.4 `docs/data/history/{slug}.json` (552 filer) + `index.json`

```
{ slug, field, operator, region, location,
  units:         [{name, type, first_period, last_period}],
  storage_units: [{name, type, first_period, last_period}],
  series:        [{period, oil_mbd, assoc_gas_mmscfd, dry_gas_mmscfd,
                   condensate_mbd, water_mbd,
                   liquids_mboed, natural_gas_mboed, total_mboed}] }
```

`index.json` er `{slug: {field, operator, region, first_period, last_period}}`.

Bygget av `build_history_artifacts`, `etl/transform.py:439-462`.

### 5.5 `docs/data/operators.json` + `docs/data/operators/{slug}.json` (50 filer)

`operators.json` er `{generated_from: "current operator of record", operators: {slug: {name,
field_count, first_period, last_period, latest: {...}}}}` — kun indeks.

Seriene ligger i separate filer fordi den samlede filen ville passert 2 MB
(`OPERATORS_SPLIT_THRESHOLD_BYTES`, `etl/build.py:164`). Terskelen er nådd
(`operators_split: true`), så oppsplitting er den faktiske tilstanden — men **koden støtter
begge**, og hvilken som gjelder avhenger av datastørrelsen ved byggetid. Frontenden håndterer
begge (`docs/app/state.js:60-85`).

### 5.6 `docs/data/equity/`

| Fil | Antall | Innhold |
|---|---|---|
| `meta.json` | 1 | policy-parametre, kildehash, begrensninger |
| `index.json` | 1 | `{slug: {name, field_count, first/last_published_period, latest_production, latest_coverage_status}}` |
| `companies/{slug}.json` | 292 | per juridisk enhet |
| `fields/{slug}.json` | 491 | eierintervaller per felt |
| `groups/{slug}.json` | 222 | per visningsgruppe |
| `anomalies.json` | 1 | MURLACH, karantene, umatchede felt, osv. |

**`companies/{slug}.json`:**
```
{ slug, name, label: "Legal entity as recorded by NSTA",
  field_count, fields: [feltnavn],
  first_published_period, last_published_period,
  series: [{ period,
             oil_mbd:           {value, status, coverage_pct},
             dry_gas_mmscfd:    {value, status, coverage_pct},
             assoc_gas_mmscfd:  {value, status, coverage_pct},
             condensate_mbd:    {value, status, coverage_pct},
             liquids_mboed:     {value, status, coverage_pct},
             natural_gas_mboed: {value, status, coverage_pct},
             total_mboed:       {value, status, total_coverage_pct} }] }
```

Hver strøm bærer **sin egen** dekningsprosent og status. `status` ∈
`complete` / `warning` / `unavailable`. Ved `unavailable` er `value` **`null`**, aldri `0`
(`etl/equity_artifacts.py:334`). Merk at `total_mboed` bruker nøkkelen `total_coverage_pct`,
ikke `coverage_pct` — en inkonsistens i artefaktformatet.

**`fields/{slug}.json`:**
```
{ slug, field_name, equity_field_name, field_match_method: "exact"|"normalized"|"alias",
  ownership_intervals: [{company_name, interest_pct, start_date, end_date, operator_flag, status}],
  resolution_status_by_period: {"YYYYMM": "resolved"|...},
  excluded_periods: [] }
```

`end_date: null` betyr **åpent intervall**, aldri en sentinel-dato.

### 5.7 `docs/data/overview/` (6 filer, 55 MB)

Forhåndsaggregert for Produksjon-visningen, så nettleseren slipper å laste 552 felthistorikkfiler.

| Fil | Form | Elementer | Rå | Gzip |
|---|---|---|---|---|
| `monthly_totals.json` | liste | 613 perioder | 0,06 MB | 0,01 MB |
| `company_groups.json` | `{gruppenavn: {...}}` | 38 | 1,87 MB | 0,15 MB |
| `legal_entities.json` | `{selskapsnavn: {...}}` | 292 | 10,17 MB | 0,60 MB |
| `fields.json` | `{slug: {...}}` | 552 | 11,11 MB | 1,38 MB |
| `company_groups_field_breakdown.json` | `{gruppe: {felt: {...}}}` | 38 | **31,26 MB** | 1,41 MB |
| `meta.json` | objekt | — | — | — |

`company_groups.json` bærer også `is_singleton` og `member_entities`.

### 5.8 Lisensartefakter

`licence_portfolio.geojson` — 1 803 `Polygon`-features:
`{subarea_name, block_reference, licence_number, licence_reference, licence_status,
licence_start_date, licence_end_date, current_display_group, group_slug, equity_pct,
operator_group, operated}`.

`licence_history.geojson` — 8 886 `Polygon`-features:
`{block_reference, licence_number, licence_reference, licence_status, start_date, end_date,
licensee_names, licensee_group, operator_names, operator_group, admin_org, admin_group,
episode_id, is_current_episode}`.

`episode_id` er **`null` i alle 8 886 features** — en reell feil, ikke et designvalg. Se §11.17.

### 5.9 `docs/data/field_polygons.geojson`

344 features. `{field_no, polygon_field_name, determination_status, matched_pprs_field,
matched_pprs_slug, match_method}`. `matched_pprs_slug` er join-nøkkelen mot
`fields.geojson.properties.slug`. Umatchede polygoner publiseres med `matched_pprs_field: null`
— aldri droppet (`etl/field_polygons.py:150-156`).

---

## 6. Enheter og konverteringer

### 6.1 Enheter i kilden

PPRS publiserer hver strøm i **flere** enheter samtidig. Løsningen henter kun én per strøm:

| Strøm | Feltnavn hentet | Enhet | Andre enheter i kilden (ikke hentet) |
|---|---|---|---|
| Olje | `OILPRODMBD` | **mb/d** (tusen fat/dag) | `OILPRODMAS` (tonn), `OILPRODM3` (m³), `OILPRDDENS` (kg/m³) |
| Assosiert gass | `AGASPROMMS` | **MMscf/d** | `AGASPRODMA` (tonn), `AGASPROKSM` (ksm³), `AGASPRODEN` |
| Tørrgass | `DGASPROMMS` | **MMscf/d** | `DGASPRODMA` (tonn), `DGASPROKSM` (ksm³), `DGASPRODEN` |
| Kondensat | `GCONDMBD` | **mb/d** | `GCONDMASS` (tonn), `GCONDVOL` (m³), `GCONDDEN` |
| Produsert vann | `WATPRODMBD` | **mb/d** | `WATPRODVOL` (m³) |
| Gass til rørledning | `GASPIPVOLM` | MMscf/d | hentes, men **lagres ikke** — se §11.2 |

**NGL finnes ikke som egen strøm i PPRS.** Kondensat (`GCOND*`) er det nærmeste. Det finnes
ingen NGL-felt i de 46 kolonnene.

Kilden har også injisert gass, fakling, venting, injisert vann og reinjisert vann
(`GASINJ*`, `GASFLAR*`, `GASVENT*`, `INJWAT*`, `REINJWATVO`). **Ingen av disse hentes.**

### 6.2 Konverteringen

Én konstant, ett sted:

```python
# etl/production_config.py:29
GAS_SCF_PER_BOE = 6000
```

Formlene (`etl/mboed.py:42-72`):

```
GAS_MMSCF_PER_MBOE = GAS_SCF_PER_BOE / 1000.0          # = 6.0   (etl/mboed.py:39)

liquids_mboed     = oil_mbd + condensate_mbd
natural_gas_mboed = (dry_gas_mmscfd + assoc_gas_mmscfd) / 6.0
total_mboed       = liquids_mboed + natural_gas_mboed
```

`oil_mbd` og `condensate_mbd` er allerede tusen fat/dag og regnes som numerisk ekvivalente med
mboe/d uten konvertering — dette er en **presentasjonsbeslutning**, ikke en fysisk ekvivalens.

Konstanten 6 000 scf/boe er en konvensjonell energiekvivalensfaktor for sammenlignbarhet. Den er
eksplisitt **ikke** en påstand om realisert energiinnhold, salgsspesifikasjon,
entitlement-produksjon, inntektsekvivalens eller målt feltspesifikk brennverdi
(`etl/production_config.py:28-35`).

**Håndhevelse:** `tests/test_no_second_gas_conversion.py` skanner hele repoet — både Python og
JavaScript — etter en annen slik tallkonstant og feiler hvis den finnes. En udokumentert
konverteringskonstant i `docs/app/map.js` ble funnet og fjernet på denne måten
(`docs/app/map.js:26-33`).

### 6.3 Avrunding

| Regel | Verdi | Kilde |
|---|---|---|
| Desimaler, native felt | 3 | `ROUND_DECIMALS`, `etl/transform.py:33` |
| Desimaler, avledede felt | 3 | `MBOED_ROUND_DECIMALS`, `etl/production_config.py:52` |
| `-0.0` kollapses til `0.0` | ja | `etl/transform.py:44-45`, `etl/mboed.py:83-84` |
| Egenkapitalvekting, mellomledd | 6 | `etl/equity_join_historical.py:242-245` |

**Kritisk disiplin:** avledede verdier regnes alltid fra **uavrundede** komponenter og rundes
nøyaktig én gang, ved serialisering — aldri rund komponentstrømmer før `total_mboed` beregnes
(`etl/mboed.py:19-23`, `etl/transform.py:355-370`).

Unntak: operatørgrainet beholder bevisst dobbeltrunding på de *native* feltene
(`etl/validate.py:436-446`). Det er årsaken til at formelsjekkens toleranse er 0,01 og ikke
strammere.

### 6.4 Tidsoppløsning

**Månedlig.** `PERIODYRMN` er en **streng** `"YYYYMM"`, ikke et tall — sortering fungerer
leksikografisk. 613 distinkte perioder fra `197506` til `202606`.

Frontenden kan vise årlig gjennomsnitt, men det beregnes **i nettleseren**
(`docs/app/production.js`), ikke i ETL. Artefaktene er alltid månedlige.

---

## 7. Geodata

### 7.1 Kartlag

| Lag | Kilde | Geometri | Fil |
|---|---|---|---|
| Produksjonsbobler | PPRS punkter | `Point` | `fields.geojson` |
| Feltpolygoner | Feltbestemmelser | `Polygon`/`MultiPolygon` | `field_polygons.geojson` |
| Lisensunderområder | Lisensunderområder | `Polygon` | `licence_portfolio.geojson` |
| Lisenshistorikk | Blokk-historikk | `Polygon` | `licence_history.geojson` |
| Bakgrunnskart | OpenStreetMap | raster | CDN |

### 7.2 Koordinatsystem

Kilden er **WGS84 (EPSG:4326)** i alle datasett — bekreftet live på PPRS-laget
(`extent.spatialReference: {wkid: 4326, latestWkid: 4326}`) og forventet eksplisitt for
feltpolygoner (`EXPECTED_WKID = 4326`, `etl/field_polygons.py:54`).

**Ingen reprojisering skjer noe sted.** `query_all` sender aldri `outSR`
(`etl/arcgis.py:181-188`), så geometri kommer tilbake i lagets native SR, som allerede er 4326.
Det lagres og serveres som 4326.

**Konsekvens for en sammenslått løsning:** hvis en søsterløsning har en kilde i et projisert
system (f.eks. UTM eller nasjonalt rutenett), finnes det ingen reprojiseringskode her å
gjenbruke — den må skrives.

### 7.3 Punktgeometri

PPRS gir ett punkt per rapporteringsenhet. Feltets punkt er **aritmetisk gjennomsnitt** av
produksjonsenhetenes punkter (`etl/transform.py:184-187`) — ikke et ekte sentroid, og ikke
vektet. Lagringsenheter er ekskludert fra sentroidet, slik at ROUGH sin lagringsenhet ikke
trekker markøren (`etl/transform.py:113-120`).

Koordinater rundes til 3 desimaler (`etl/transform.py:503`) ≈ 110 m ved ekvator.

### 7.4 Esri-ringer → GeoJSON

`etl/field_polygons.py:185-194`:

```python
"type": "Polygon" if len(row["geometry"]["rings"]) == 1 else "MultiPolygon",
"coordinates": (row["geometry"]["rings"] if len(...) == 1
                else [[ring] for ring in row["geometry"]["rings"]])
```

Hver ring blir et eget polygon. **Det finnes ingen håndtering av hull.** I Esri-konvensjon er
en med-urviser-ring ytre og en mot-urviser-ring et hull; koden skiller ikke.

Verifisert på faktiske data: av 344 features har **én** flere ringer (`Teal South`, 2 ringer).
Begge ringene er med-urviser, altså to ytre ringer, så konverteringen er **korrekt i dag**. Men
en fremtidig ring med hull ville blitt tegnet som et eget fylt polygon i stedet for et hull.

Ringene beholder Esri sin med-urviser-orientering for ytre ringer, mens GeoJSON (RFC 7946)
foreskriver mot-urviser. MapLibre tolererer dette; strengere konsumenter kanskje ikke.

### 7.5 Servering

Rå GeoJSON over HTTP. **Ingen vektorfliser, ingen flisserver, ingen forenkling.** Frontenden
laster hele filen og gir den til MapLibre som en `geojson`-kilde.

`licence_history.geojson` er 8,89 MB rå / 1,54 MB gzip — én forespørsel når den visningen åpnes.

---

## 8. Forretningslogikk

### 8.1 Rapporteringsenhet → felt

PPRS' grain er (felt, rapporteringsenhet, periode). Løsningens grain er (felt, periode).
Aggregeringen er **ren summering** av produksjonsenheter innen samme `FIELDNAME` og periode
(`etl/transform.py:167-178`, `:346-354`).

**`null` behandles som 0**, ikke som ukjent: `totals` initialiseres til `0.0` og `null`-verdier
hoppes bare over (`etl/transform.py:173-176`). Et felt uten oljeproduksjon får derfor
`oil_mbd: 0.0` i artefaktet, ikke `null`. Se ROUGH-eksempelet i vedlegg A.2.

**Verdt å vite ved reimplementering:** summeringen slår i praksis aldri sammen noe i dag. Målt
mot live data 2026-09-13 har hver (felt, periode) nøyaktig én produksjonsenhet gjennom hele
historikken — 133 608 produksjonsrader fordelt på 133 608 distinkte (felt, periode). Det eneste
feltet med flere enheter i samme måned er ROUGH, og den andre enheten er lagring, som uansett
ekskluderes.

Aggregeringslogikken er altså korrekt, men den er en gjennomgang, ikke en sammenslåing. Ikke
tolk det som at flere enheter per felt-måned er umulig — det er nettopp det mekanismen for
omdøpinger (§8.4) hviler på at *ikke* skjer samtidig. Men ingen test og ingen validering vil
fange det hvis antakelsen brytes.

### 8.2 Lagringsenheter ekskluderes

Kilden har **ingen flagg** som skiller lagring fra produksjon. `UNITTYPDES` for `ROUGH STORAGE`
er `"Dry Gas Field"` — samme som en ekte produksjonsenhet.

Løsningen bruker derfor en **håndvedlikeholdt unntaksliste**,
`etl/mappings/unit_classification.csv`, med tre rader:

| field_name | unit_name | classification |
|---|---|---|
| ROUGH | ROUGH STORAGE | storage |
| HATFIELD | HATFIELD MOOR GAS STORAGE INJECTION | storage |
| HUMBLY GROVE | HUMBLY GROVE GAS STORAGE | storage |

Alt som ikke står der, er `production` som standard (`classify()`, `etl/transform.py:85-91`).
Unntaksbasert, slik at en ny rutineenhet aldri gjør bygget rødt.

**Snubletråd:** `validate_unit_classification_tripwire` (`etl/validate.py:524-570`) skanner alle
enhetsnavn etter tokenene `"STORAGE"` og `"INJECTION"` (`etl/validate.py:75`). Et treff som
**ikke** allerede står i CSV-en bryter bygget for menneskelig vurdering — det blir aldri
auto-klassifisert.

Ekskluderingen gjelder både produksjonstotaler **og** sentroidgeometri, og i **hver** periode,
ikke bare den siste (`etl/transform.py:288-292`).

### 8.3 Inkonsistens innen et felt

`FIELDAREA`, `LOCATION` og `ORGGRPNM` forventes konstante på tvers av et felts
produksjonsenheter i én periode. Ved uenighet tas den første (deterministisk, siden radene er
sortert på `UNITNAME`) og en merknad legges i `properties.notes`
(`etl/transform.py:196-231`) — aldri stille valg.

### 8.4 Feltomdøpinger

`SEAN → NORTH SEAN` og `COLUMBA B → COLUMBA BD` krever **ingen spesialhåndtering**. NSTA bærer
begge enhetsnavnene under samme `FIELDNAME`, og fordi periodene ikke overlapper, gir summering
per (`FIELDNAME`, periode) automatisk én sammenhengende serie uten dobbelttelling
(`etl/transform.py:292-304`). Omdøpingen er likevel synlig: `units[]` lister hvert historiske
enhetsnavn med `first_period`/`last_period`.

### 8.5 Navnematching

To separate mekanismer, begge **deterministiske** — aldri fuzzy:

**Feltnavn (PPRS ↔ egenkapital, PPRS ↔ polygoner):** `normalize_field_name`
(`etl/equity_match.py:73-83`) folder kun store/små bokstaver, whitespace og
bindestrek-/apostrofvarianter. Den fjerner **aldri** klammer, punktum eller skråstrek — fordi
`"VIKING A [pt of VIKING GROUP]"` og `"VIKING B [pt of VIKING GROUP]"` er forskjellige felt.

Matcherekkefølge: eksakt → normalisert → alias fra `etl/mappings/field_aliases.csv`.
**Aliasfilen er tom** (kun header) — mekanismen finnes, men er ikke i bruk.

**Selskapsnavn:** ingen matching i det hele tatt. Juridiske enheter brukes nøyaktig som NSTA
registrerer dem. Ingen morselskapsrollup, ingen sammenslåing av likelydende navn
(`docs/app/equity-ui.js:1-5`).

### 8.6 Selskapsgruppering

Tre begreper holdes fra hverandre (`etl/company_groups.py:1-45`):

1. **Juridisk enhet som registrert av NSTA** — grainet all egenkapitaldata ligger på.
2. **Gjeldende visningsgruppe** — implementert.
3. **Gruppe-på-tidspunktet** — **ikke** implementert. Ingen datert, autoritativ kilde ble funnet,
   så den fabrikkeres ikke.

Kilden er `EQGRPHOLD` på lisensunderområde-tjenesten. Grainet der er (underområde, holder): hver
rad bærer gruppen og *sin egen* prosent (`EQUITY`), men radens **egen juridiske enhet** må
gjenvinnes fra `EQORG` — én streng som lister alle holdere med prosenter:

```
"PERENCO GAS (UK) LIMITED (85%), EVERARD ENERGY LIMITED (15%)"
```

`resolve_row_holder_name` (`etl/company_groups.py:129-142`) matcher radens `EQUITY` mot det ene
`EQORG`-segmentet med samme prosent (toleranse `1e-6`, `:126`). Finnes ingen — eller **flere** —
segmenter på den prosenten, returneres `None`. **Det gjettes aldri.** Oppdagelsesrapporten målte
488 av 1 803 rader som slike uavklarte likheter.

En enhet får kun en ikke-triviell gruppe når NSTAs egen `EQGRPHOLD` utvetydig navngir den i
**hver** rad den opptrer i. Å dele et navneledd er aldri nok.

Alt kilden ikke dekker — 182 av 292 enheter — faller tilbake til å være sin egen
singleton-gruppe med status `unresolved`. Bevaring (`sum(juridisk enhet) == sum(visningsgruppe)`)
holder per konstruksjon uansett.

I frontenden samles alle `unresolved` i én bøtte kalt `"Unresolved legal entities"
(`UNRESOLVED_BUCKET_NAME`, `etl/overview.py:115` og `docs/app/production.js:17` — **de to
strengene må være identiske**, håndhevet kun av en kommentar).

### 8.7 Egenkapitalvekting

Sju vedtatte regler (`etl/equity_join_historical.py:15-28`):

1. **Halvåpen inneslutning:** `start_date <= month_start < end_date`
   (`etl/equity_join.py:129-132`). Måneden ankres til den **første** i måneden.
2. **Rader med null varighet** (`start == end`) er kildehendelser, aldri aktive intervaller.
3. **Nullinteresse-rader beholdes** og bidrar med 0. `Operator Flag = 'Y'` innebærer **aldri**
   positiv andel.
4. **Fremtidsdaterte intervaller beholdes**, inaktive til startdato.
5. `Equity Share Time Period` er kun kildemetadata.
6. **Uavklarte overlapp karantenes, aldri repareres:** ingen normalisering av andeler, ingen
   eierpreferanse, ingen egenkapitalproduksjon beregnet for den feltmåneden.
7. Selskapsnavn er den juridiske enheten nøyaktig som registrert.

Selve vektingen (`etl/equity_join_historical.py:225-254`):

```python
factor = r["interest_pct"] / 100.0
oil_mbd = round(production["oil_mbd"] * factor, 6)
```

Kun rader med `category == "resolved"` og `interest_pct > 0` inngår.

**Feltmåned-kategorier:** `resolved`, `unmatched`, `future_only`, `quarantined`,
`e1_sum_mismatch`, `genuine_interval_gap`, `no_equity_history`, `pre_equity_history`.

### 8.8 Dekning og publiseringsvindu

| Parameter | Verdi | Kilde |
|---|---|---|
| `EQUITY_PUBLICATION_START` | `"201303"` | `etl/equity_config.py:20` |
| `EQUITY_MINIMUM_COVERAGE_PCT` | `95.0` | `etl/equity_config.py:26` |
| `EQUITY_WARNING_COVERAGE_PCT` | `99.5` | `etl/equity_config.py:30` |
| `EQUITY_METHODOLOGY_VERSION` | `"2026.1"` | `etl/equity_config.py:35` |

```python
# etl/equity_publication_window.py:60-64
coverage_pct = round(100.0 * resolved / total, 3)   # None hvis total <= 0
```

Dekning måles **per strøm**, aldri slått sammen til én boe-basert prosent. Under 95 % →
`unavailable`, verdien blir `null`. Mellom 95 og 99,5 % → `warning`. Over → `complete`.

Data før `201303` publiseres ikke i det hele tatt — strukturelt ufullstendig i kilden.

### 8.9 Operatørrollup

Hele et felts historikk tilskrives den operatøren som **sist** holdt det — en 2008-fatprodusjon
telles under dagens operatør (`etl/transform.py:530-545`). Eksplisitt en mellomstasjon.
Et felt splittes aldri mellom operatører, så summering per (operatør, periode) kan ikke
dobbelttelle.

### 8.10 Top-N i frontenden

`TOP_N_DEFAULT = 10` (`docs/app/production.js:47`). Resten samles i «Other», med en fotnote som
navngir alt i bøtta; over 15 navn kollapses fotnoten bak `<details>`
(`OTHER_NOTE_COLLAPSE_THRESHOLD = 15`, `docs/app/production.js:547`).

### 8.11 Dominerende hydrokarbon (kartfarge)

```js
// docs/app/map.js:81-88
if (total_mboed <= 0)                        commodity = "none";
else if (liquids_mboed / total_mboed >= 0.5) commodity = "oil";
else                                          commodity = "gas";
```

Nøyaktig 50 % telles som olje. Boblenes radius skalerer med `sqrt(total_mboed)`
(`docs/app/map.js:187-197`).

---

## 9. Frontend

Tre toppnivåvisninger, valgt via `#top-nav-*`. `showTopView` (`docs/app/main.js:355-380`) veksler
`hidden` på `#view-production`, `#layout` og `#view-licence`.

Produksjonsvisningen initialiseres **først når den vises** (`docs/app/main.js:368-372`) — å åpne
Feltkart direkte betaler aldri oversiktsartefaktenes hentekostnad.

### 9.1 Produksjon (standardvisning)

| Kontroll | Verdier |
|---|---|
| Deling | Væske/naturgass · Etter selskap · Etter felt |
| Frekvens | Månedlig · Årlig gjennomsnitt (standard) |
| Grain (kun selskap) | Gjeldende selskapsgruppe · Juridisk enhet |
| Kategori (kun ett selskap) | Etter felt (standard) · Olje vs gass |
| Top-N (kun felt) | 5 · 10 (standard) · 15 · 20 |
| Filtre | Fra/Til-periode, selskapsgruppe, feltstatus |

**API-kall** (alle er statiske filhentinger):

| Handling | Fil |
|---|---|
| Init | `./data/overview/meta.json`, `./data/overview/monthly_totals.json` |
| Etter selskap, grain=gruppe | `./data/overview/company_groups.json` |
| Etter selskap, grain=enhet | `./data/overview/legal_entities.json` |
| Ett selskap, kategori=felt | `./data/overview/company_groups_field_breakdown.json` (**31 MB rå**) |
| Etter felt | `./data/overview/fields.json` (11 MB rå) |

Kilde: `docs/app/production.js:109-110,407,603-604,765`.

Under diagrammet: en fotnote som forklarer at selskapstilskriving starter mars 2013 mens de to
andre splittene dekker 1975 og framover — drevet av
`equity_attributable_earliest_period` og `monthly_totals_earliest_period` fra metadata
(`docs/app/production.js`, `renderPeriodNote`).

### 9.2 Feltkart

Sidepanel med søk, metrikkvalg (egenkapital / operatør), operatørfilter og laghåndtak
(bobler, feltomriss). Klikk på et felt åpner et panel med faner for Produksjon og Eierskap.

**API-kall:**

| Tidspunkt | Fil |
|---|---|
| Oppstart | `./data/meta.json`, `./data/fields.geojson`, `./data/history/index.json`, `./data/field_polygons.geojson`, `./data/equity/meta.json`, `./data/equity/index.json` |
| Feltvalg | `./data/history/{slug}.json` |
| Eierskapsfane | `./data/equity/fields/{slug}.json` |
| Selskapsvalg | `./data/equity/companies/{slug}.json` |
| Operatørvalg | `./data/operators.json`, evt. `./data/operators/{slug}.json` |

Kilde: `docs/app/main.js:22-25`, `docs/app/equity.js:14-15,57,72`, `docs/app/state.js:46,67,80`.

Per-felt- og per-selskapsdata hentes maks én gang hver og caches i minnet for sidens levetid.
En feil i egenkapitallastingen er isolert — kartet skal fortsatt virke (`docs/app/main.js:8-11`).

### 9.3 Lisensportefølje

To undervisninger: «Current portfolio» og «Historical licence interests and operators».

| Undervisning | Fil |
|---|---|
| Gjeldende | `./data/licence_portfolio_index.json`, `./data/licence_portfolio.geojson`, `./data/licence_portfolio_groups/{slug}.json` |
| Historisk | `./data/licence_history_index.json`, `./data/licence_history.geojson` (8,89 MB) |

Kilde: `docs/app/state.js:122-157`, `docs/app/licence.js:137`.

### 9.4 URL-tilstand

All delbar tilstand ligger i `location.hash`, aldri i stien — kompatibelt med
`/ukcs/`-underbanen (`docs/app/urlstate.js:1-8`). Nøkler er navnerommet per visning:

```
top
view slug metric stream mbubbles mpolygons     (Feltkart)
psplit pfreq pgrain pcat pgroup ptopn pfields pfrom pto pstatus   (Produksjon)
lmode lgroup ldate loperated lstatus llicence  (Lisens)
```

`docs/app/urlstate.js:32-44`. Serialiseringsrekkefølgen er fast og deterministisk. Verdier
valideres mot faste sett (`:17-27`); ugyldige forkastes. Et bytte av toppvisning tømmer alle
andre visningers nøkler. `history.replaceState` brukes, så vanlig interaksjon forurenser ikke
nettleserhistorikken.

---

## 10. Datavolum

### Rader

| Datasett | Rader |
|---|---|
| PPRS full historikk | 134 294 rårader |
| PPRS siste periode | 251 rårader (250 felt + 1 lagringsenhet) |
| Skrevne seriepunkter | 133 608 feltmåneder |
| Egenkapital, normaliserte intervaller | 7 683 |
| Lisensunderområder | 1 803 |
| Lisensblokk-historikk | 8 886 |
| Feltpolygoner | 344 |

Differansen 134 294 − 133 608 = **686, og alle 686 er lagringsrader**. Opptalt mot live data
2026-09-13 med klassifiseringstabellen anvendt:

```
rårader totalt                                   134 294
lagringsrader (ekskludert)                           686
produksjonsrader                                 133 608
distinkte (felt, periode) blant produksjonsrader 133 608
kollapset ved summering                                0
```

**Ingen rader slås sammen ved aggregering.** Gjennom hele 51-årshistorikken har hver
(felt, periode) nøyaktig **én** produksjonsrapporteringsenhet. Se §8.1 for hva det betyr.

### Entiteter

| Entitet | Antall |
|---|---|
| Felt med historikk | 552 |
| Felt som produserte i siste periode | 250 |
| Perioder | 613 (`197506`–`202606`, 51 år) |
| Operatører | 50 |
| Juridiske enheter | 292 |
| Visningsgrupper | 222 filer; 38 i oversiktsartefaktet; 37 «approved» |

### Filstørrelser

Totalt `docs/data/` = **122 MB** i 1 673 filer.

| Sti | Størrelse | Filer |
|---|---|---|
| `overview/` | 55 MB | 6 |
| `history/` | 26 MB | 553 |
| `equity/` | 26 MB | 1 008 |
| `operators/` | 3,4 MB | 50 |
| `licence_history.geojson` | 8,89 MB | 1 |
| `licence_portfolio.geojson` | 2,52 MB | 1 |
| `field_polygons.geojson` | 0,35 MB | 1 |
| `fields.geojson` | 0,10 MB | 1 |

Største enkeltfil: `overview/company_groups_field_breakdown.json`, 31,26 MB rå / 1,41 MB gzip.

### Tidsbruk

Fullt innsamlingsløp målt 2026-09-13 på denne maskinen: **83 sekunder**, exit 0.
Grovt fordelt: ~30 s på å hente 134 294 rader i 68 sider à 2 000, resten på
egenkapitalkjeden, polygoner, lisensdata og validering.

CI-jobben har 20 minutters timeout — rikelig margin.

Frontendtestsuiten (110 Playwright-tester) tar ~140 s. Hele suiten er 390 tester.

---

## 11. Fallgruver og kjente problemer

Dette er avsnittet som betyr mest for en reimplementering.

### 11.1 Kilden kan være ufullstendig uten at noe oppdager det

Den viktigste begrensningen, og den er **ikke løst**. Alle sjekker i prosjektet er interne
konsistenssjekker mot de dataene det faktisk mottok. Ingen av dem kan avgjøre om det NSTA
serverte var fullstendig.

Et stille forkortet datasett som fortsatt pagineres riktig, telles riktig og ikke mangler felt,
ville passert samtlige valideringer. Delta-sjekkene mot forrige bygg (20 % rader, 10 % felt)
fanger et *stort* fall, men ikke et lite eller et som skjer gradvis.

### 11.2 `GASPIPVOLM` hentes, valideres, men lagres aldri

`GASPIPVOLM` (gass til rørledning, MMscf/d) står i `OUT_FIELDS` (`etl/build.py:161`) og i
`PRODUCTION_VALUE_FIELDS` for negativ-sjekken (`etl/validate.py:66`), men **ikke** i
`VALUE_FIELD_MAP` (`etl/transform.py:26-32`). Den hentes over nettet og sjekkes, og forkastes så.

Verifisert: `fields.geojson` inneholder ingen `gas_to_pipeline`-egenskap.

**Dette er riktig oppførsel, ikke en feil** — men begrunnelsen manglet i koden og er nå skrevet
inn (`etl/transform.py`, over `VALUE_FIELD_MAP`). Målt mot live siste periode (202606):

```
tørrgass 875.8 + assosiert 2029.3 = 2905.1 MMscf/d produsert
gass til rørledning               = 2688.5 MMscf/d   (92,5 % av den samme gassen)
```

`GASPIPVOLM` er altså en nedstrøms disponering av gass som allerede er talt, ikke en femte
produksjonsstrøm. Å ta den inn i totalene ville dobbelttalt. Den hentes likevel fordi den står i
`validate.PRODUCTION_VALUE_FIELDS`: en negativ verdi der er en ekte kildefeil verdt å bryte
bygget for, uansett om tallet publiseres.

Ved reimplementering: ikke anta at alt i `OUT_FIELDS` er ment å havne i modellen.

### 11.3 `today_month_start` er en hardkodet dato

```python
# etl/equity_artifacts.py:176
today_month_start: date = date(2026, 9, 1),
```

Samme standard i `etl/equity_join_historical.py:156`. **`build.py` overstyrer den aldri** —
verifisert på `etl/build.py:560-562`.

Verdien avgjør om en feltmåned uten aktivt egenkapitalintervall klassifiseres som `future_only`
eller `pre_equity_history` (`etl/equity_join_historical.py:118-141`). Etter hvert som ekte tid
passerer 2026-09, vil intervaller som faktisk har startet fortsatt regnes som fremtidige.

**RETTET 2026-09-13.** Standardverdien er nå `None`, og den faktiske måneden regnes ut ved
kalltidspunktet (`date.today().replace(day=1)`). Tester som trenger et stabilt svar sender inn en
eksplisitt dato.

Vaktposten er `test_today_month_start_default_is_resolved_at_call_time_not_frozen`
(`tests/test_equity_join_historical.py`), som asserterer på *signaturen* framfor på atferd: et
frossent literal og den ekte klokken er uskillelige så lenge literalet tilfeldigvis navngir
inneværende måned — nøyaktig vinduet der den opprinnelige feilen så riktig ut. En rent
atferdsbasert test ville vært grønn i september 2026 uansett.

### 11.4 MURLACH — et enkeltfelt hardkodet i koden

```python
# etl/equity_artifacts.py:521
def build_anomalies(pipeline_result, murlach_field_name="MURLACH [pt of MARNOCK-SKUA]"):
```

Feltets eneste registrerte egenkapitalrader har startdato **2050-01-04**. Det er åpenbart en
feil i kilden, men koden verken tolker eller retter den: feltet klassifiseres som
`future_only`, faller dermed ut av `resolved_rows`, og utelates fra alle
egenkapitalvektede totaler.

Feltnavnet er en strengkonstant i en funksjonssignatur. Endrer NSTA navnet, forsvinner
anomalirapporteringen stille — selve utelatelsen ville fortsatt fungert (den følger av
`future_only`-kategorien), men forklaringen til brukeren ville forsvunnet.

Frontenden har egen MURLACH-håndtering (`docs/app/equity-ui.js`), som slår opp feltets egne
`ownership_intervals` framfor selskapets aggregerte feltliste — fordi MURLACHs feltmåneder
**aldri** er `resolved` og feltet derfor aldri dukker opp i noen selskaps feltliste.

### 11.5 Lagringsenheter må vedlikeholdes for hånd

Kilden har ingen flagg for lagring. `etl/mappings/unit_classification.csv` har tre rader, ført
inn manuelt etter inspeksjon. Snubletråden fanger nye enheter hvis navn inneholder `STORAGE`
eller `INJECTION` (`etl/validate.py:75`) — men **bare** de to tokenene. En lagringsenhet kalt
noe annet ville blitt talt som produksjon uten at noe varsler.

ROUGH er den eneste som faktisk forurenser tallene i dag: `ROUGH STORAGE` har historisk
rapportert `DGASPROMMS` opp mot ~1 512 MMscf/d, som ville blitt dobbelttalt mot
`ROUGH PRODUCTION` (se notatet i CSV-en). De to andre er ekskludert på prinsipp, ikke fordi de
forurenser noe i dag.

### 11.6 Kommentaren om SRI på MapLibre er feil

`docs/app/map.js:5-6` sier biblioteket lastes «as an ES module from jsDelivr with a verified SRI
hash». Importen på `docs/app/map.js:12-17` er en ren `import`-setning **uten** integritetssjekk
— ES-modulimporter kan ikke bære `integrity`.

SRI finnes faktisk på MapLibre-**CSS** (`docs/index.html:10`) og på ECharts, som injiseres som
`<script>` med `script.integrity` (`docs/app/charts.js:28`). Selve MapLibre-JS-en er upinnet mot
innholdsendring, kun mot versjon.

**RETTET 2026-09-13** — kommentaren sier nå hva som faktisk gjelder. Selve begrensningen består:
en ES-modulimport *kan* ikke bære `integrity`, så versjonspinning er den eneste garantien der.
Å innføre SRI ville krevd å laste biblioteket som et klassisk `<script>` i stedet, eller et
import-map med integritet (ikke bredt støttet) — ikke gjort, siden det er en arkitekturendring,
ikke en rettelse.

### 11.7 Polygonkonvertering håndterer ikke hull

Se §7.4. Korrekt for dagens ene flerringede feature, men uten hull-logikk. Ringene beholder
Esris med-urviser-orientering, som er motsatt av RFC 7946.

### 11.8 `supportsPagination` — kommentaren stemmer ikke lenger

`etl/arcgis.py:11-13` og `:164-166` sier at det live PPRS-laget rapporterer `supportsPagination`
som `null`, og at flagget derfor ignoreres. Målt live 2026-09-13 rapporterer laget
`supportsPagination: true`.

Koden er uansett riktig — den paginerer ubetinget og stoler ikke på flagget. Men kommentarens
begrunnelse er utdatert, og noen som leser den kan feilaktig konkludere at flagget kan brukes.

### 11.9 To «kompakte» oversiktsartefakter er svært store

`overview/company_groups_field_breakdown.json` er **31 MB rå**. Modulens egen docstring
(`etl/overview.py:1-10`) begrunner oversiktsartefaktene med at «nettleseren aldri må laste 552
felthistorikkfiler». Den gzippes til 1,41 MB, så over nettet er det håndterbart — men den
**parses** i sin helhet i nettleseren, og 31 MB JSON er tungt på telefon.

Den lastes så snart man velger ett enkelt selskap i Etter selskap-visningen
(`docs/app/production.js:407`).

`overview/fields.json` (11 MB rå / 1,38 MB gzip) lastes tilsvarende ved Etter felt.

### 11.10 `UNRESOLVED_BUCKET_NAME` er duplisert i to språk

`etl/overview.py:115` og `docs/app/production.js:17` må inneholde nøyaktig samme streng
(`"Unresolved legal entities"`). Det håndheves **kun av en kommentar**
(`docs/app/production.js:13-16`) — ingen test sammenligner dem.

Samme mønster for `slugify()`, som er implementert to ganger: `etl/transform.py:49-57` og
`docs/app/format.js:29-36`. Her sier kommentaren eksplisitt «Must match etl/transform.py's
slugify() exactly», men igjen finnes ingen kryssjekk.

### 11.11 `field_aliases.csv` er tom

Aliasmekanismen er bygget, testet og koblet inn — men filen inneholder bare en header. 52 felt
er umatchede mot egenkapital, og 232 mot polygoner, uten at noen alias er ført inn.

Ved reimplementering: mekanismen finnes, men det finnes ingen faktiske aliaser å arve.

### 11.12 To ulike toleranser for samme slags sjekk

Bevaringssjekkene bruker to helt ulike tilnærminger:

- **Før serialisering:** fast `FLOAT_PRECISION_TOLERANCE_MBOED = 1e-4` (`etl/validate.py:259`).
- **Etter serialisering:** toleransen **regnes ut ved byggetid** fra byggets egne radantall,
  statistisk utledet (`compute_serialization_tolerance`, `etl/validate.py:325-365`):

  ```
  half_ulp = 0.5 * 10**-3
  σ = half_ulp * sqrt((n_field + n_operator) / 3)
  toleranse = 8.0 * σ        # SERIALIZATION_TOLERANCE_SIGMA, etl/validate.py:322
  ```

Begrunnelsen står i docstringen: det naive verste-fall-taket fra trekantulikheten gir ~34 mboe/d
ved dette datasettets skala, altså **løsere** enn den flate 5,0-konstanten den skulle erstatte.

En tidligere flat `CONSERVATION_TOLERANCE_MBOED = 5.0` ble forkastet fordi den kunne skjule et
bortfalt felt som produserte under den grensen (`etl/production_config.py:55-65`).

Formelsjekken (`validate_derived_field_month_formula`, `etl/validate.py:419`) bruker en tredje
toleranse, `0.01`, satt **empirisk**: målt maksimalt avvik i et ekte fullhistorikk-bygg var
~0,004 mboe/d.

Ved reimplementering: dette er ikke overingeniørarbeid, det er nødvendig. Uavhengig avrundede
summer av samme tall divergerer, og en fast toleranse er enten for stram eller for slapp
avhengig av datamengden.

### 11.13 488 av 1 803 selskapsrader er genuint tvetydige

`resolve_row_holder_name` returnerer `None` når to holdere i samme underområde har lik prosent.
Det er ikke en sjeldenhet: oppdagelsesrapporten målte 488 av 1 803 rader. Koden gjetter aldri,
men det betyr at en betydelig del av grunnlaget for selskapsgruppering rett og slett ikke kan
avklares fra denne kilden.

### 11.14 Ingen ekstern avstemming av totaler

`meta.json.notes[0]` sier det rett ut (`etl/build.py:143-150`): totalene er aldri avstemt mot en
NSTA-publisert månedlig aggregatfigur, fordi ingen slik per-periode-figur var lokaliserbar. Kun
årlige og flerårige tall publiseres.

### 11.15 Kildens ustabilitet er konsentrert i Excel-kjeden

PPRS-tjenesten er stabil: samme item-ID, samme skjema, låst med hash. Egenkapitalkjeden er ikke:
den avhenger av lenketekst på en HTML-side, av at en ArcGIS Hub-URL har en `q`-parameter, og av
at et søk returnerer nøyaktig ett treff. Hvert ledd har eksplisitt feilhåndtering med
forklarende melding, men tre ledd som alle kan brytes av en redaksjonell endring hos NSTA er en
reell driftsrisiko.

Positivt: `download_workbook` faller **aldri** tilbake til en hurtigbufret kopi
(`etl/equity_fetch.py:64-66`) — en feil er en feil, ikke stille gamle data.

### 11.16 Hardkodede datoer og navn — samlet liste

| Verdi | Sted | Risiko |
|---|---|---|
| `date(2026, 9, 1)` | `etl/equity_artifacts.py:176`, `etl/equity_join_historical.py:156` | blir foreldet, se §11.3 |
| `"MURLACH [pt of MARNOCK-SKUA]"` | `etl/equity_artifacts.py:521` | navneendring bryter rapportering |
| `"Report 1"` | `etl/equity_parse.py:35` | arknavn i Excel |
| `1960` | `etl/equity_parse.py:64` | sentinel-år-terskel |
| `"OZMfUznmLTnWccBc"` | `etl/equity_fetch.py:51` | ArcGIS org-ID |
| `"Field Partners"` | `etl/equity_artifacts.py:75` | forventet elementtittel |
| `"Unresolved legal entities"` | `etl/overview.py:115` + `docs/app/production.js:17` | må matche |
| lon [−14, 5], lat [48, 63] | `etl/validate.py:77-78` | UKCS bounding box |
| 5 item-ID-er | se §3 | ArcGIS-elementer |

### 11.17 `episode_id` er `null` i hele lisenshistorikken — aktiv feil

`build_history_geojson` setter feltet slik (`etl/licence_history.py:193`):

```python
"properties": {**entry, "episode_id": row["attributes"].get("OBJECTID")},
```

Men modulens `OUT_FIELDS` er `",".join(EXPECTED_FIELDS)` (`etl/licence_history.py:66`), og
`EXPECTED_FIELDS` (`:49-64`) inneholder **ikke** `OBJECTID`. Attributtet blir aldri hentet,
`.get("OBJECTID")` gir `None`, og alle 8 886 features får `episode_id: null`
(verifisert mot `docs/data/licence_history.geojson`).

Docstringen på `:175-177` sier at «Every feature carries a stable `episode_id` (its source
OBJECTID) so the frontend can uniquely address one episode without relying on a (possibly
non-unique) combination of other fields». Den funksjonen virker ikke.

**Konsekvens i frontenden**, som faktisk bruker feltet:

| Sted | Bruk |
|---|---|
| `docs/app/licence.js:350-352` | valg av én episode setter `["==", ["get","episode_id"], <null>]` |
| `docs/app/licence.js:603-604` | filter bygges som `["in", ["get","episode_id"], [...]]` over en liste med bare `null` |

Å velge én historisk episode kan derfor ikke isolere den, siden alle features har samme
`null`-verdi.

**Hvorfor testene ikke fanger det:** enhetstesten
(`tests/test_licence_history.py:102-107`) konstruerer rader via `_row(object_id=1)`, altså med
`OBJECTID` til stede — den tester funksjonen med input som bygget aldri produserer.
Frontend-fixturen (`tests/frontend/fixtures/docs/data/licence_history.geojson`) har
`episode_id: 1, 2, 3` hardkodet og går aldri gjennom ETL-en. Begge sider av grensesnittet er
testet mot data som ikke ligner produksjonsdataene.

**RETTET 2026-09-13.** `"OBJECTID": "esriFieldTypeOID"` er lagt inn i `EXPECTED_FIELDS`, som både
henter feltet (siden `OUT_FIELDS` utledes derfra) og skjemavaliderer det.

To nye vakter i `tests/test_licence_history.py`:

- `test_out_fields_requests_every_attribute_the_builders_read` — parser modulens egne
  `attrs.get("NAVN")`-uttrykk og krever at hvert navn finnes i `OUT_FIELDS`. Dette er den
  generelle invarianten, ikke bare et plaster på `OBJECTID`.
- `test_episode_id_is_populated_from_a_row_shaped_like_the_real_query` — bygger radens
  attributter **kun** fra `OUT_FIELDS`, slik den live spørringen faktisk returnerer, framfor å
  injisere `OBJECTID` uavhengig. Den første versjonen jeg skrev injiserte det likevel og var
  derfor ingen vakt; det er akkurat det blindpunktet som lot feilen gå gjennom.

Begge er verifisert ved å reintrodusere feilen: begge slår ut, og går grønne igjen når den
fjernes.

### 11.18 TODO-er

Verifisert: `grep -rn "TODO\|FIXME\|XXX\|HACK" etl/ docs/app/` gir **null treff**. Det finnes
ingen TODO-er i koden.

---

## 12. Lisens og attribusjon

### Operativ lisens

**NSTA User Agreement, juni 2023**, publisert på
`https://www.nstauthority.co.uk/site-tools/terms-and-conditions/`
(PDF: `nsta-user-agreeement-june-2023.pdf`).

Prosjektets bruk er vurdert som **ikke-kommersiell** under den avtalen. Vurderingen ble gjort
**9. september 2026** mot akkurat det dokumentet (`ATTRIBUTION.md`). Endrer bruken karakter,
må vurderingen gjøres på nytt mot gjeldende avtaleversjon.

### Påkrevd attribusjonstekst

Ordrett, ikke omskrevet:

> Contains information provided by the North Sea Transition Authority and/or other third parties.

Den vises i bunnteksten sammen med lenke til vilkårene (`docs/index.html`, `<footer>`).
**Utelates den, bortfaller de tildelte rettighetene automatisk.**

### Nøkkelvilkår

- Tillatt: kopiere, publisere, distribuere, overføre og bearbeide informasjonen — inkludert å
  bygge og republisere avledede aggregater, som er det denne løsningen gjør.
- Tillatt utnyttelse er **kun ikke-kommersiell**. Juni 2023-dokumentet gir ingen rett til
  kommersiell utnyttelse.
- Dekker **ikke**: persondata, informasjon NSTA ikke har publisert, NSTAs logo eller
  tredjepartslogoer, tredjepartsrettigheter NSTA ikke er bemyndiget til å gi, og andre
  IP-rettigheter (patenter, varemerker, designrettigheter).
- **Ikke-tilslutning:** bruken må ikke antyde offisiell status eller NSTA-tilslutning. Nettstedet
  sier derfor eksplisitt «not an official NSTA product» i toppteksten.
- Ingen garanti; NSTA garanterer ikke fortsatt levering av informasjonen.
- Underlagt engelsk og walisisk rett.

### Kritisk fallgruve for en sammenslått løsning

Et eldre og **vesentlig annerledes** dokument — «OGA Open User Licence» v1.0 — speiles fortsatt
av tredjeparter (f.eks. marine.gov.scot). Den teksten **tillater kommersiell utnyttelse** og
bruker en annen attribusjonsstreng («Contains information provided by the OGA.»).

Den er erstattet på NSTAs eget nettsted og **må ikke legges til grunn**. En sammenslått
applikasjon som henter lisensvilkår fra en speilet kopi vil trekke feil konklusjon om
kommersiell bruk.

### Øvrige lisenser

| Ressurs | Lisens |
|---|---|
| Kartfliser | © OpenStreetMap-bidragsytere, ODbL. Attribusjon rendres av kartets eget attribution-control |
| MapLibre GL JS | BSD-3-Clause |
| ECharts | Apache-2.0 |

---

## Vedlegg A — Ekte rådata og samme rader etter transformasjon

Hentet live fra PPRS 2026-09-13.

### A.1 BUZZARD, periode 202606 — enkel felt-til-felt

**Rå (Esri JSON, ett feature, `.../FeatureServer/0/query?where=FIELDNAME='BUZZARD' AND PERIODYRMN='202606'`):**

```json
{
  "attributes": {
    "OBJECTID": 7329,
    "FIELDNAME": "BUZZARD",
    "FIELDAREA": "CNS",
    "LOCATION": "Offshore",
    "ORGGRPNM": "CNOOC INTERNATIONAL",
    "UNITNAME": "BUZZARD",
    "UNITTYPDES": "Oil Field Exporting to Pipeline",
    "PERIODYRMN": "202606",
    "OILPRODMBD": 39.687384,
    "AGASPROMMS": 12.7663725,
    "DGASPROMMS": 0,
    "GCONDMBD": 0,
    "GASPIPVOLM": 0.1801065,
    "WATPRODMBD": 267.973708666667
  },
  "geometry": { "x": -0.9463369626742059, "y": 57.83311484905897 }
}
```

**Etter transformasjon (`docs/data/fields.geojson`):**

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-0.946, 57.833] },
  "properties": {
    "slug": "buzzard", "field": "BUZZARD",
    "region": "CNS", "location": "Offshore",
    "operator": "CNOOC INTERNATIONAL", "period": "202606",
    "unit_count": 1, "storage_unit_count": 0,
    "oil_mbd": 39.687, "condensate_mbd": 0.0, "water_mbd": 267.974,
    "assoc_gas_mmscfd": 12.766, "dry_gas_mmscfd": 0.0,
    "liquids_mboed": 39.687, "natural_gas_mboed": 2.128, "total_mboed": 41.815
  }
}
```

Hva som skjedde:
- Alle verdier rundet til 3 desimaler, koordinater også.
- `natural_gas_mboed` = (0 + 12.7663725) / 6.0 = 2.12772875 → **2.128**, regnet fra den
  uavrundede råverdien.
- `liquids_mboed` = 39.687384 + 0 → 39.687. `total_mboed` = 41.81511 → 41.815.
- **`GASPIPVOLM` (0.1801065) forsvant** — den er ikke i `VALUE_FIELD_MAP`. Se §11.2.
- `UNITNAME`/`UNITTYPDES` flyttet inn i `units[]` i `history/buzzard.json`, ikke her.

### A.2 ROUGH, periode 202606 — lagringsenhet ekskluderes

**Rå — to features:**

```json
{"OBJECTID": 93200, "FIELDNAME": "ROUGH", "UNITNAME": "ROUGH PRODUCTION",
 "UNITTYPDES": "Dry Gas Field", "PERIODYRMN": "202606",
 "OILPRODMBD": null, "AGASPROMMS": null, "DGASPROMMS": 25.4390778483333,
 "GCONDMBD": 0.00845795333333333, "GASPIPVOLM": 25.4325798883333,
 "WATPRODMBD": 0.0510454466666667}

{"OBJECTID": 93201, "FIELDNAME": "ROUGH", "UNITNAME": "ROUGH STORAGE",
 "UNITTYPDES": "Dry Gas Field", "PERIODYRMN": "202606",
 "OILPRODMBD": null, "AGASPROMMS": null, "DGASPROMMS": 0,
 "GCONDMBD": 0, "GASPIPVOLM": 0, "WATPRODMBD": 0}
```

**Etter transformasjon:**

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [0.462, 53.83] },
  "properties": {
    "slug": "rough", "field": "ROUGH",
    "region": "SNS", "location": "Offshore",
    "operator": "CENTRICA STORAGE HOLDINGS", "period": "202606",
    "unit_count": 1, "storage_unit_count": 1,
    "oil_mbd": 0.0, "condensate_mbd": 0.008, "water_mbd": 0.051,
    "assoc_gas_mmscfd": 0.0, "dry_gas_mmscfd": 25.439,
    "liquids_mboed": 0.008, "natural_gas_mboed": 4.24, "total_mboed": 4.248
  }
}
```

Hva som skjedde:
- `ROUGH STORAGE` ble klassifisert som lagring via
  `etl/mappings/unit_classification.csv` — **ikke** fra noe i kildedataene. Begge radene har
  `UNITTYPDES: "Dry Gas Field"`.
- `unit_count: 1` og `storage_unit_count: 1`: lagringsenheten telles, men bidrar ikke.
- Bare `ROUGH PRODUCTION` sin geometri inngår i sentroidet.
- **`null` ble `0.0`**, ikke `null`: `OILPRODMBD` og `AGASPROMMS` var `null` i begge rader, men
  artefaktet har `oil_mbd: 0.0` og `assoc_gas_mmscfd: 0.0` (se §8.1).
- Dette er også grunnen til at `meta.json` har `record_count: 251` men `field_count: 250`.

### A.3 BUZZARD egenkapital — Excel-rad til artefakt

**Rå (`etl/.cache/equity_workbook.xlsx`, ark `"Report 1"`):**

| Field Name | On Offshore | Median Line Flag | Status | Organisation Name | Percentage Holding | Operator Flag | Start Date | End Date | Equity Share Time Period |
|---|---|---|---|---|---|---|---|---|---|
| BUZZARD | Offshore | *(tom)* | 700 - PRODUCING | BG INTERNATIONAL LIMITED | 19.99 | N | 2001-05-21 | 2003-11-12 | Previous-2001 to 2003 |
| BUZZARD | Offshore | *(tom)* | 700 - PRODUCING | CNOOC PETROLEUM EUROPE LIMITED | 45.01 | Y | 2001-05-21 | 2003-11-12 | Previous-2001 to 2003 |
| BUZZARD | Offshore | *(tom)* | 700 - PRODUCING | ONE-DYAS EOG LIMITED | 5 | N | 2001-05-21 | 2003-11-12 | Previous-2001 to 2003 |

**Etter transformasjon (`docs/data/equity/fields/buzzard.json`, `ownership_intervals[]`):**

```json
{"company_name": "BG INTERNATIONAL LIMITED", "interest_pct": 19.99,
 "start_date": "2001-05-21", "end_date": "2003-11-12",
 "operator_flag": "N", "status": "700 - PRODUCING"}
```

Og et åpent intervall fra samme fil:

```json
{"company_name": "ADURA OPERATIONS LIMITED", "interest_pct": 29.89,
 "start_date": "2026-05-01", "end_date": null,
 "operator_flag": "N", "status": "700 - PRODUCING"}
```

Hva som skjedde:
- `datetime` → ISO-datostreng (`etl/equity_parse.py:73-80`).
- **`end_date: null` betyr åpent intervall** — aldri en sentinel-dato.
- `On Offshore`, `Median Line Flag` og `Equity Share Time Period` bæres **ikke** videre.
- Filen får i tillegg `field_match_method: "exact"` og
  `resolution_status_by_period: {"201303": "resolved", ...}`.
- Radene fra 2001–2003 beholdes selv om de ligger før publiseringsvinduet (`201303`) — de
  brukes til å avgjøre eierskap, men gir ingen publiserte produksjonstall.

Egenkapitalvektingen for en gitt måned skjer så i `etl/equity_join_historical.py:225-254`: for
hver `resolved` feltmåned multipliseres feltets produksjon med `interest_pct / 100`, avrundet til
6 desimaler, og summeres per selskap i `etl/equity_artifacts.py:314-320`.

---

## Vedlegg B — Reimplementeringssjekkliste

Minimum for å reprodusere datainnsamlingen uten å lese kildekoden:

1. **Paginer alltid.** Ikke stol på `supportsPagination`. Bruk `resultOffset`/`resultRecordCount`
   med `orderByFields=OBJECTID`, og sjekk `exceededTransferLimit` på hver side.
2. **Tell uavhengig.** Kjør en `outStatistics`-`count` og sammenlign med antall hentede rader.
3. **Lås skjemaet.** Forvent navngitte felt med eksplisitt type; bryt bygget ved drift.
4. **Hent alt hver gang.** Kilden retter historiske tall bakover — verifisert i praksis.
5. **Aggreger rapporteringsenhet → felt ved summering**, og ekskluder lagringsenheter via en
   eksplisitt unntaksliste med snubletråd for nye kandidater.
6. **Rund én gang, til slutt.** Regn avledede verdier fra uavrundede komponenter.
7. **Én konverteringskonstant, ett sted**, håndhevet av en test som skanner repoet.
8. **Egenkapital: halvåpne intervaller**, `start <= måned_start < end`, ankret til den 1. i
   måneden. Karanteneoverlapp, ikke reparer dem.
9. **Mål dekning per strøm**, aldri sammenslått. Publiser `null` ved utilstrekkelig dekning,
   aldri `0`.
10. **Valider før du skriver.** Skriv atomisk. En feil skal gi null endringer på disk.
