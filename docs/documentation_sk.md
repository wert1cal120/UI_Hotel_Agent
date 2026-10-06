# Inteligentný agent pre správu hotela

Zadanie č. 1 - návrh, implementácia a experimentálne vyhodnotenie agenta

Experimenty: 120 behov, 60 párov scenárov. Reprodukčná sada bola vytvorená 2026-10-06.

## 1. Téma a cieľ

Agent prideľuje izby skupinám podľa počtu osôb, preferovaného typu a termínu pobytu. Hlavným cieľom je maximalizovať počet skupín, ktoré dostanú celé plánované ubytovanie. Prijatá rezervácia ešte nie je úspešne dokončený pobyt. Každý objekt Client reprezentuje jednu žiadosť skupiny; počet hostí je samostatný údaj.

## 2. PEAS

- P: počet úplne ubytovaných skupín a ich podiel medzi nezrušenými žiadosťami; doplnkovo počet hostí, dodané hosťonoci, zhoda typu, obsadenosť, odmietnutia a prerušenia.
- E: hotel s obmedzeným počtom izieb typu single, double, triple a quad, kalendár rezervácií, denné dávky žiadostí, začiatočný a konečný termín pobytu, voliteľné náhodné zrušenia a poruchy s opravou.
- A: zvoliť poradie spracovania dennej dávky; rezervovať izbu, odmietnuť žiadosť, presunúť zvyšok pobytu do inej izby alebo odmietnuť náhradné ubytovanie. Príchod a odchod vykonáva prostredie automaticky.
- S: aktuálny deň, všetky nové žiadosti dnešnej dávky alebo úloha presťahovania, kapacita a typ izieb, uskutočniteľnosť celej alokácie, kalendár známych rezervácií a oznámený termín opravy už pokazenej izby.

Agent vidí celú dnešnú dávku, nie žiadosti, ktoré prídu v ďalších dňoch, ani budúce zrušenia a poruchy. Rezervácia zároveň určuje izbu na pobyt.

## 3. Klasifikácia prostredia

- Pozorovateľné: aktuálny prevádzkový stav relevantný pre pridelenie izby je plne pozorovateľný cez senzor. Neznalosť budúcich náhodných udalostí sama osebe nie je dôvodom označiť aktuálny hotel za čiastočne pozorovateľný.
- Stochastické: príchody, preferencie, termíny, zrušenia a poruchy sú náhodne generované. Pre fixný scenár je vykonanie platnej akcie deterministické.
- Sekvenčné: obsadenie izby ovplyvňuje neskoršie prijatie žiadostí aj presťahovanie.
- Čas: stav sa mení medzi diskrétnymi dennými krokmi. Počas výpočtu jednej akcie je statický; simulácia nemá asynchrónne udalosti počas rozhodovania.
- Diskrétne: dni, izby, typy, žiadosti a akcie sú diskrétne.
- Jednoagentové: v každom svete rozhoduje jeden agent. Porovnanie dvoch agentov znamená dva nezávislé svety, nie súťaž o spoločné izby.

Prostredie spĺňa požadovanú sekvenčnosť a obmedzené zdroje. Náhodné externé udalosti poskytujú ďalšiu náročnosť bez nepresných tvrdení o pozorovateľnosti.

## 4. Reprezentácia a architektúra

models.py zachováva bežné triedy Room, Client, Booking a Hotel, zoznam room.bookings a metódu Hotel.book_room. environment.py rozširuje pôvodnú kostru o životný cyklus pobytov. Jeho generate_rooms, generate_client, generate_clients a step sa používajú aj pri predgenerovaní scenára v scenario.py. Každý beh kopíruje klientov, aby jeden svet nemohol zmeniť druhý.

sensors.py vytvára nemenné dátové snímky s tuple kalendármi. Agent dostáva iba Percept a dnešnú dávku, nie HotelEnvironment, Hotel, Booking ani celý Scenario. actuators.py vykonáva overené akcie. performance.py hodnotí výsledky. simulation.py riadi denný cyklus; experiments.py, cli.py, settings.py a report.py obsahujú pomocnú logiku experimentov, nastavení a výstupov.

Interval pobytu je polootvorený [arrival, departure). Dve rezervácie sa prekrývajú práve vtedy, keď startA < endB a startB < endA. Odchod a nový príchod v rovnaký deň sú povolené. Počet osôb je tvrdá podmienka; preferovaný typ je mäkká požiadavka, takže väčšia izba môže byť prijateľná.

Stavy rezervácie sú reserved, active, completed, cancelled a disrupted. Dokončenie vyžaduje dodanie všetkých plánovaných nocí. Presťahovanie zachová ID aj už dodané noci; vytvorí novú alokáciu iba od max(dnes, príchod). Cieľová izba sa overí pred uvoľnením pôvodnej alokácie.

Poradie dňa: odchody; zrušenia; opravy a nové poruchy; náhradné alokácie (ubytovaní hostia prví, potom skorší príchod a ID); pozorovanie dennej dávky; výber poradia a postupné akcie; príchody; zaznamenanie noci. Každá jednotlivá akcia dostane čerstvý vnem a znovu sa overí. Interval poruchy je [porucha, oprava), preto je izba použiteľná v deň opravy.

## 5. Miera úspešnosti

- completed_groups: nezrušené skupiny so stavom completed a všetkými dodanými nocami. Toto je hlavný výsledok.
- fulfillment_rate = 100 * completed_groups / eligible_requests. eligible_requests zahŕňa všetky žiadosti okrem externých zrušení, aj keď agent zrušenú žiadosť pôvodne odmietol.
- guest_night_fulfillment_rate = 100 * dodané nezrušené hosťonoci / požadované nezrušené hosťonoci. Zachytí aj čiastočnú službu pri prerušení pobytu.
- exact_type_match_rate = 100 * dodané izbonoci v preferovanom type / všetky dodané izbonoci nezrušených pobytov.
- occupancy = 100 * obsadené izbonoci / prevádzkyschopné izbonoci. bed_utilization používa hosťonoci a dostupné lôžkonoci.
- accepted, rejected a failed rozlišujú prijatie, rozhodnutie odmietnuť a neplatnú akciu. failed_actions zahŕňa aj chyby presťahovania; disrupted_groups je neúspešné pokračovanie už prijatého pobytu.

Pri nulovom menovateli vracia program pre danú mieru 0, nie 100; surové počty umožňujú rozlíšiť prázdny súbor od neúspešnej služby. Nie je použitý spoločný vážený bodový výsledok. Skóre výberu izby je odhad pre rozhodovanie, nie objektívna miera úspešnosti.

## 6. Základný agent

BaselineAgent zachová prichádzajúce poradie celej dennej dávky. Pre každú žiadosť používa first-fit: zvolí prvú vhodnú izbu, inak odmietne. Pri poruche rovnako vyberá náhradnú izbu. Je deterministický a dostáva rovnakú dávku, senzory a akčné možnosti ako intelligent; nemá menej informácií.

## 7. Inteligentný agent

IntelligentAgent skúsi najviac päť jednoduchých poradí dnešnej dávky: pôvodné poradie, kratšie pobyty prvé, menej vhodných izieb prvé, väčšie skupiny prvé a skorší odchod prvý. Rovnaké poradia neskúša opakovane. Každé simuluje v dočasnom kalendári bez zmeny hotela.

V simulovanom poradí vyberá vhodnú izbu podľa štvorice: voľné lôžka navyše, nezhoda typu, zvyšná dĺžka voľného kalendárového okna a číslo izby. Menšia hodnota má prednosť; neskoršia položka rozhoduje iba pri zhode skorších. Kalendárové okno je medzi najbližšími známymi rezerváciami; bez ďalšej rezervácie sa použije hranica 30 dní po odchode. Nejde o predikciu.

Plány porovnáva podľa počtu prijateľných skupín, potom počtu presných typov a nakoniec menšieho počtu nevyužitých lôžkonocí. Pri úplnej zhode zachová prvý plán. Vráti iba poradie ID; simulation.py vykonáva bežné decide a akcie po jednej. Reálne kalendáre sa medzi akciami aktualizujú.

Kontrolná ukážka: jedna izba, žiadosť na šesť nocí a dve žiadosti na po sebe idúce tri noci, všetky prijaté v ten istý deň. Baseline prijme prvú a dokončí jednu skupinu; intelligent spracuje krátke pobyty prvé a dokončí dve. Obsadenosť a zhoda typu sú pritom u oboch 100 %. Príkaz main.py demo ukazuje rozdiel v plánovaní, nie iba vo výbere typu. Ukážka je oddelená od náhodných experimentov.

## 8. Pamäť a autonómnosť

Vnútorným stavom je posledný vybraný plán last_plan: pravidlo poradia, porovnávacia trojica a dočasné pridelenia. Pri ďalšej dávke sa nahradí. Diagnostické počítadlá zaznamenávajú počet skúšaných plánov a porovnaní izieb.

Agent sa neučí rozdelenie budúceho dopytu a nepoužíva náhodnú predikciu. Pracuje so známou dávkou a kalendárom. Plán vyberá autonómne, bez pokynov používateľa. Každý experiment vytvára novú inštanciu; vnútorný stav sa neprenáša medzi behmi.

## 9. Racionalita a obmedzenia

Správne rozhodnutie umožní dokončiť čo najviac skupín pri zachovaní kapacity a termínov. Agent maximalizuje prijateľnosť dnešnej dávky medzi skúšanými plánmi, nie počet budúcich skupín so znalosťou neviditeľných udalostí.

Ohraničenie je jednoduché: najviac päť poradí a chamtivý výber izby v každom. Neskúša všetky permutácie, kombinácie izieb ani strategické odmietnutia. Nezaručuje optimum ani pre dnešnú dávku. Počet porovnaní izieb v jednom volaní bol najviac 240; celkom sa v sade skúšalo 4550 plánov. Nejde o tvrdý časový limit, práca závisí aj od veľkosti dávky a kalendárov.

Dobré rozhodnutie môže zlyhať pre budúcu poruchu, neskorší neznámy dopyt alebo kombináciu termínov, ktorú päť poradí nenájde. Počet presťahovaní ani konkrétna akcia nie sú samy osebe odmenou.

## 10. Experimenty a reprodukovateľnosť

| Konfigurácia | Izby | Žiadosti/deň | Porucha/izba/deň |
| --- | --- | --- | --- |
| relaxed | 16 | 1-3 | 0.005 |
| standard | 12 | 1-4 | 0.01 |
| stressed | 8 | 2-5 | 0.02 |

Spoločné nastavenie: príjem 30 dní od 2026-09-01; predstih 0-7 dní; pobyt 1-7 nocí; váhy typov izieb [30, 40, 20, 10] a dopytu [30, 40, 20, 10]; oprava 1-3 dni; pravdepodobnosť zrušenia 0.10. Zrušenie je možné iba pre žiadosti s aspoň jedným celým dňom medzi prijatím a príchodom (predstih >=2). Nastane striktne po prijatí a pred príchodom; nastavená pravdepodobnosť sa preto nevzťahuje na všetky bezprostredné príchody.

Každá konfigurácia používa 20 seedov 1111-1130. Jeden scenár sa predgeneruje a použije v dvoch oddelených prostrediach. Poruchy majú samostatný RNG a stabilné ID izieb; zrušenia stabilné ID žiadostí. Rozhodnutia agenta nemenia generovanie externých udalostí.

Po príjmovej fáze simulácia pokračuje po posledný plánovaný odchod všetkých žiadostí scenára, vrátane odmietnutých a zrušených. Horizont aj dostupné kapacity sú preto rovnaké pre oba svety; nedokončené budúce rezervácie nie sú mylne vyhodnotené ako úspechy.

Tabuľky uvádzajú priemer a výberovú smerodajnú odchýlku (ddof=1), nie interval spoľahlivosti. Párové rozdiely používajú intelligent - baseline. Časy sú merané cez perf_counter vrátane in-memory simulácie, bez ukladania výsledkov a kreslenia grafov; závisia od počítača a nie sú deterministické. Verzie Pythonu/knižníc, konfigurácie, SHA-256 zdrojov a scenárov sú uložené v manifest.json. Reprodukcia presných scenárov vyžaduje aj rovnakú verziu Pythonu: publikovaný Python bol 3.13.2.

## 11. Výsledky

| Konfigurácia | Agent | Dokončené skupiny | Úspešnosť (%) |
| --- | --- | --- | --- |
| relaxed | baseline | 51.55 ± 4.93 | 92.37 ± 6.53 |
| relaxed | intelligent | 52.15 ± 4.70 | 93.47 ± 6.30 |
| standard | baseline | 54.00 ± 6.60 | 78.75 ± 7.56 |
| standard | intelligent | 56.15 ± 7.58 | 81.76 ± 7.81 |
| stressed | baseline | 50.35 ± 4.31 | 50.98 ± 4.25 |
| stressed | intelligent | 51.95 ± 4.51 | 52.61 ± 4.68 |

![Úspešnosť skupín: priemer a smerodajná odchýlka](figures/fulfillment.png)

| Konfigurácia | Agent | Zhoda typu (%) | Obsadenosť (%) |
| --- | --- | --- | --- |
| relaxed | baseline | 71.26 ± 15.75 | 32.76 ± 3.27 |
| relaxed | intelligent | 94.37 ± 4.64 | 33.20 ± 3.25 |
| standard | baseline | 70.80 ± 14.67 | 45.74 ± 5.01 |
| standard | intelligent | 86.89 ± 9.03 | 47.63 ± 6.01 |
| stressed | baseline | 70.08 ± 15.96 | 64.27 ± 4.01 |
| stressed | intelligent | 78.27 ± 12.74 | 65.74 ± 3.98 |

![Zhoda preferovaného typu: priemer a smerodajná odchýlka](figures/room_match.png)

| Konfigurácia | Výhry I | Výhry B | Remízy | Rozdiel skupín |
| --- | --- | --- | --- | --- |
| relaxed | 6 | 1 | 13 | 0.60 ± 1.43 |
| standard | 14 | 0 | 6 | 2.15 ± 2.21 |
| stressed | 13 | 1 | 6 | 1.60 ± 2.06 |

![Párové rozdiely dokončených skupín; čierna čiara je priemer](figures/paired_deltas.png)

| Konfigurácia | Agent | Čas behu (ms) | Prerušené skupiny |
| --- | --- | --- | --- |
| relaxed | baseline | 9.20 ± 0.96 | 0.15 ± 0.37 |
| relaxed | intelligent | 10.51 ± 1.15 | 0.20 ± 0.52 |
| standard | baseline | 9.41 ± 1.33 | 0.35 ± 0.75 |
| standard | intelligent | 10.89 ± 1.73 | 0.60 ± 0.75 |
| stressed | baseline | 9.77 ± 1.00 | 3.15 ± 1.63 |
| stressed | intelligent | 10.90 ± 0.98 | 3.15 ± 1.39 |

Vo všetkých publikovaných behoch bolo spolu 0 neplatných akcií. To overuje integráciu agentov a aktuátorov v tejto sade, nie neprítomnosť každej možnej chyby.

## 12. Porovnanie a interpretácia

V konfigurácii relaxed bol priemerný párový rozdiel 0.60 dokončených skupín. Intelligent vyhral v 6 pároch, baseline v 1; 13 párov skončilo remízou. Zhoda typu izby sa v priemere zmenila o 23.10 percentuálneho bodu. V konfigurácii standard bol priemerný párový rozdiel 2.15 dokončených skupín. Intelligent vyhral v 14 pároch, baseline v 0; 6 párov skončilo remízou. Zhoda typu izby sa v priemere zmenila o 16.09 percentuálneho bodu. V konfigurácii stressed bol priemerný párový rozdiel 1.60 dokončených skupín. Intelligent vyhral v 13 pároch, baseline v 1; 6 párov skončilo remízou. Zhoda typu izby sa v priemere zmenila o 8.19 percentuálneho bodu.

Agenti sa líšia poradím dennej dávky aj výberom izby. Baseline môže obsadiť izbu dlhou žiadosťou pred dvoma nadväzujúcimi krátkymi alebo prideliť malú skupinu do veľkej izby. Intelligent porovná niekoľko poradí, zachováva menšie vhodné izby a tesnejšie voľné okná. Vyššia obsadenosť sama osebe neznamená viac dokončených skupín, pretože dlhé pobyty zapĺňajú viac nocí ako krátke.

Konkrétny neúspech: stressed, seed 1128. Baseline dokončil 46 skupín, intelligent 44. Priebeh je uložený v runs/<konfigurácia>/<seed>/<agent>/actions.csv a events.csv. Príčinu jednotlivých odmietnutí možno overiť podľa ID žiadosti, dátumov a predchádzajúcich alokácií. Samotné agregáty nedokazujú, ktorý krok plánovania spôsobil prehru.

Kontrolná ukážka izoluje prínos poradia pri jednej izbe. Náhodné výsledky však spájajú účinok poradia, kapacity a kalendára; bez ablačného experimentu nemožno samostatne vyčísliť každý prínos. Sada je opisné porovnanie, nie dôkaz optimálnosti ani všeobecnej štatistickej významnosti.

## 13. Testy, nedostatky a ďalší rozvoj

Dodaná verzia obsahuje sedem základných unittest testov v tests/test_hotel.py: prijatie rezervácie, prekrytie termínov a príchod v deň odchodu, kapacitu izby, zrušenie, presťahovanie pri poruche, rovnaký seed a dennú dávku. Používajú malé príklady bez mockov. Nejde o úplné pokrytie všetkých okrajových prípadov, neplatných akcií, CLI ani generovania dokumentácie.

Model neobsahuje ceny, upratovanie, viacizbové skupiny, čakaciu listinu, alternatívne termíny ani dobrovoľný presun platných rezervácií. Pri neúspešnom presťahovaní sa zvyšok pobytu preruší. Dopyt je syntetický; skupiny majú rovnakú hodnotu bez ohľadu na veľkosť a dĺžku. Päť poradí nie je úplný plánovač. Ďalší krok môže byť ablačné porovnanie alebo úplný malý prehľad plánov, nie pridávanie náhodných udalostí bez rozhodovacieho zmyslu.

## 14. Používateľská príručka

Použite Python 3.10 alebo novší; publikovaná sada bola overená na Python 3.13.2. V koreňovom priečinku projektu:

- `python3 -m venv .venv`
- `.venv/bin/python -m pip install -r requirements.txt`
- `.venv/bin/python main.py compare --config standard --seed 1111`
- `.venv/bin/python main.py demo`
- `.venv/bin/python main.py compare --config-file configs/no_events.json`
- `.venv/bin/python main.py simulate --agent intelligent --rooms 8 --days 10`
- `.venv/bin/python main.py experiments --repetitions 20 --seed 1111`
- `.venv/bin/python -m unittest discover -s tests -v`
- `.venv/bin/python main.py report`

Na Windows použite .venv\Scripts\python.exe namiesto .venv/bin/python. Závislosti možno pripnúť cez requirements-lock.txt. CLI umožňuje zmeniť preset, seed, izby a dni. Počet žiadostí, pobyty a pravdepodobnosti patria do JSON cez --config-file; --rooms a --days majú prednosť. Experiments vždy použije tri presety a --seed je prvý seed série. --output mení cieľ a --no-plots vypína grafy. Súbory configs/*.json sú príklady.

Bez argumentov sa spustí porovnanie. Compare a simulate zapisujú do results/compare a results/simulation; demo do results/demo. Každý beh obsahuje actions.csv, events.csv, daily.csv, metrics.csv a batches.csv s pôvodným a vybraným poradím. Celá sada je v results/experiments vrátane manifestu a párových tabuliek. Opakovaný príkaz používa rovnaký adresár; na zachovanie predošlých výsledkov zadajte iný --output. Report vyžaduje aktuálne zdrojové hashe. Ukážková zmena na obhajobe: main.py compare --rooms 6 --seed 1111 --output results/defense.

## 15. Zdroje, knižnice a nástroje

Rozhodovací mechanizmus je explicitný Python kód bez hotového agentného frameworku alebo predtrénovaného rozhodovacieho modelu. Základné doménové triedy a pôvodnú kostru pripravil autor projektu. Pri dokončení bol použitý OpenAI Codex na návrh, implementáciu, testovanie a prípravu dokumentácie. O prípustnosti takejto pomoci rozhodujú pravidlá vyučujúceho.

- Python štandardná knižnica: random, dataclasses, enum, datetime, unittest, argparse, csv, json a hashlib. Dokumentácia generátora: https://docs.python.org/3/library/random.html
- pandas: spracovanie CSV a agregácia experimentov. https://pandas.pydata.org/docs/
- Matplotlib: grafy, bez grafického používateľského rozhrania. https://matplotlib.org/stable/users/index.html
- ReportLab: vytvorenie PDF a vloženie Unicode fontu DejaVu Sans dodávaného s Matplotlib. https://docs.reportlab.com/

Presné verzie knižníc pre experimenty sú v manifest.json a requirements-lock.txt. Knižnice nevykonávajú výber izby za agenta.
