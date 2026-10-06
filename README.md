# UI Hotel Agent

Simulovaný hotel s dvoma agentmi: baseline first-fit a jednoduchý plánovač
dennej dávky zohľadňujúci kapacitu a kalendár. Bez GUI, neurónovej siete
alebo hotového agentného frameworku. Jedna žiadosť reprezentuje skupinu hostí.

## Spustenie

Python 3.10+; publikované výsledky boli overené na Python 3.13.2.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py compare --config standard --seed 1111
```

Na Windows použite `.venv\Scripts\python.exe` namiesto `.venv/bin/python`.
Ak už máte virtuálne prostredie, netreba ho znovu vytvárať.
Pre presné publikované verzie závislostí použite `requirements-lock.txt`;
pre iné podporované verzie Pythonu je určený rozsah v `requirements.txt`.

```bash
# Jeden agent a zmena hlavných parametrov
.venv/bin/python main.py simulate --agent intelligent --rooms 8 --days 10

# Dva samostatné svety s identickým scenárom
.venv/bin/python main.py compare --config stressed --seed 1112

# Zrozumiteľná ukážka: jedna izba, baseline 1 skupina, intelligent 2
.venv/bin/python main.py demo

# Porovnanie bez zrušení a porúch
.venv/bin/python main.py compare --config-file configs/no_events.json

# 3 konfigurácie × 20 seedov × 2 agenti = 120 behov
.venv/bin/python main.py experiments --repetitions 20 --seed 1111

# Sedem základných testov (stdlib unittest, nepotrebujú pandas)
.venv/bin/python -m unittest discover -s tests -v

# Dokumentácia z výsledkov aktuálneho zdrojového kódu
.venv/bin/python main.py report
```

`tests/test_hotel.py` obsahuje iba základné kontroly: rezerváciu, prekrytie
termínov a deň odchodu, kapacitu, zrušenie, presťahovanie, rovnaký seed
a dennú dávku. Nejde o úplné pokrytie všetkých chýb a okrajových prípadov.

Bez argumentov sa spustí `compare`. Všetky možnosti: `main.py --help`,
`main.py compare --help`. Príklad JSON: `--config-file configs/standard.json`.
CLI parametre majú prednosť pred JSON; napríklad `--rooms 6`.
Grafy možno vypnúť pomocou `--no-plots`.

CLI má iba hlavné voľby: preset, seed, počet izieb a dní. Počet žiadostí,
dĺžku pobytov a pravdepodobnosti nastavte v JSON, napríklad:

```json
{
  "max_requests": 5,
  "max_stay": 10,
  "cancellation_probability": 0
}
```

Uložte ako `configs/custom.json` a použite `--config-file configs/custom.json`.
`experiments` vždy porovná všetky tri presety; `--seed` je prvý seed série.

## Výstupy

- `results/experiments/runs.csv`: každý jednotlivý beh a všetky metriky.
- `summary.csv`: priemery a výberové smerodajné odchýlky (ddof=1).
- `paired.csv`, `paired_summary.csv`: rozdiely intelligent - baseline, výhry a prehry.
- `manifest.json`: konfigurácie, seedy, verzie Pythonu/knižníc a SHA-256 zdrojov/scenárov.
- `scenarios/`: skutočný agentom skrytý scenár každej dvojice.
- `runs/<konfigurácia>/<seed>/<agent>/`: `result.json`, denné dáta, akcie, udalosti a metriky.
- `batches.csv` v každom behu: pôvodné/vybrané poradie dnešnej dávky a pravidlo výberu.
- `comparison.png`, `paired_deltas.png`: grafy celého porovnania.
- `output/pdf/documentation.pdf`: dokumentácia.
- `docs/documentation_sk.md`: jej textový zdroj.

Príkazy zapisujú do uvedeného výstupného adresára. Ak chcete zachovať staré
výsledky, použite nový `--output results/moj_experiment`. Po zmene programu
treba experimenty zopakovať; report overuje hash zdrojov a odmietne staré dáta.
Zámerne sa zachovávajú aj behy, v ktorých intelligent prehral.

## Čo sa hodnotí

Hlavný výsledok je počet úplne dokončených pobytov skupín, nie počet
prijatých rezervácií. Zrušenia sa vylučujú z menovateľa úspešnosti oboch agentov,
aj keď jeden pôvodne zrušenú žiadosť odmietol. Doplnkové metriky zahŕňajú
zhodu preferovaného typu, obsadenosť prevádzkyschopných izbonocí, hosťonoci,
prerušenia, presťahovania, počet kontrol a čas.

Simulácia po skončení príjmu žiadostí pokračuje po posledný plánovaný odchod.
Poruchy a zrušenia sa generujú vopred nezávisle od rozhodnutí; agent ich
vopred nepozná. Rezervácie používajú interval `[príchod, odchod)`.

## Architektúra

`scenario → environment → sensors → agent → actions → actuators → environment`

`performance` vyhodnotí výsledok; `simulation` riadi denný cyklus;
`experiments` vytvára nezávislé párové behy. Nemenné vnemy neobsahujú mutable
hotelové objekty. Algoritmus agenta je v `agents/intelligent.py`, nie v senzore.

## Denná dávka a jednoduché plánovanie

Obaja agenti vidia všetky žiadosti prijaté dnes a tie isté známe kalendáre.
Baseline zachová ich poradie a vezme prvú vhodnú izbu. Intelligent skúsi
najviac päť poradí: pôvodné, krátke pobyty, málo vhodných izieb, veľké skupiny
a skoré odchody. Každé preverí v dočasnom kalendári. Vyberá viac prijateľných
skupín, potom viac presných typov, potom menej nevyužitých lôžkonocí.
Izbu volí podľa kapacity, typu a tesnejšieho voľného okna.

Je to heuristika, nie úplný prehľad všetkých plánov. Nepozná žiadosti ďalších
dní a nepredikuje ich. `demo` je kontrolný príklad, nie náhrada 120 náhodných
behov. V oboch svetoch ukážky sú zhoda typu aj obsadenosť 100 %, ale počet
dokončených skupín je rozdielny.

## Pôvodná kostra

`models.py` používa pôvodné bežné triedy a metódy `Hotel.book_room`,
`Booking.check_availability`, `room.bookings`, `Hotel.print_bookings`.
`HotelEnvironment(hotel, start_date, seed)` zachováva `generate_rooms`,
`generate_client`, `generate_clients` a `step`; scenár používa tieto generátory.
`main(agent)` zostáva jednoduchým programovým vstupom. Denný cyklus s
`sensors.observe → agent.decide → actuators.execute` je v `simulation.py`.

`config.py` obsahuje známe konštanty SEED, WORKING_DAYS, NUMBER_OF_ROOMS
a CLIENT_NAMES. WORKING_DAYS mení dĺžku príjmu všetkých CLI presetov;
NUMBER_OF_ROOMS mení štandardný preset. Explicitné CLI/JSON hodnoty majú
prednosť. Rozsahy a kontrola nastavení sú v `settings.py`, argumenty v `cli.py`.
Výsledky a grafy sú pomocná vrstva, nie súčasť rozhodovania agenta.

Použité nástroje vrátane implementačnej pomoci Codex sú popísané v dokumentácii.
Téma/PEAS vyžadujú schválenie vyučujúcim; program netvrdí, že schválenie už nastalo.
