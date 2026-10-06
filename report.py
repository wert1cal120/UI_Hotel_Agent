"""Build Slovak Markdown/PDF documentation directly from verified experiment CSVs."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def _load_results(directory: Path):
    import pandas as pd
    from experiments import paired_comparisons, summarize_runs

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    runs = pd.read_csv(directory / "runs.csv")
    summary = pd.read_csv(directory / "summary.csv")
    paired = pd.read_csv(directory / "paired.csv")
    paired_summary = pd.read_csv(directory / "paired_summary.csv")
    if not manifest.get("assignment_minimum_met"):
        raise ValueError("Documentation needs >=3 configurations and >=20 seed pairs per configuration")
    if len(runs) != manifest["run_count"] or len(paired) != manifest["pair_count"]:
        raise ValueError("CSV counts disagree with the manifest")
    for name, group in runs.groupby("config"):
        counts = group.groupby("agent").size().to_dict()
        if set(counts) != {"baseline", "intelligent"} or min(counts.values()) < 20:
            raise ValueError(f"Incomplete experiment cohort: {name}")
        if group.groupby("seed").scenario_hash.nunique().max() != 1:
            raise ValueError("Paired agents did not receive the same scenario")
    # Do not build an apparently authoritative report from stale/edited
    # aggregate tables: independently recompute them from all raw observations.
    _, expected_summary = summarize_runs(runs.to_dict("records"))
    expected_paired, expected_paired_summary = paired_comparisons(runs)
    for actual, expected, keys in (
        (summary, expected_summary, ["config", "agent"]),
        (paired, expected_paired, ["config", "seed"]),
        (paired_summary, expected_paired_summary, ["config"]),
    ):
        try:
            pd.testing.assert_frame_equal(
                actual.sort_values(keys).reset_index(drop=True),
                expected.sort_values(keys).reset_index(drop=True),
                check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-9)
        except AssertionError as error:
            raise ValueError("Saved aggregate statistics disagree with raw runs; rerun experiments") from error
    sources = list(ROOT.glob("*.py")) + list((ROOT / "agents").glob("*.py"))
    current = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sources}
    if current != manifest["source_sha256"]:
        raise ValueError("Source changed after the experiments; rerun main.py experiments before report")
    return manifest, runs, summary, paired, paired_summary


def _markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(str(value) for value in row) + " |" for row in rows])


def _figures(summary, paired, directory: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory.mkdir(parents=True, exist_ok=True)
    names = list(dict.fromkeys(summary.config))
    colors = {"baseline": "#64748b", "intelligent": "#0f766e"}
    for metric, filename, label in (
        ("fulfillment_rate", "fulfillment.png", "Úplne ubytované skupiny (%)"),
        ("exact_type_match_rate", "room_match.png", "Zhoda s preferovaným typom (%)"),
    ):
        fig, ax = plt.subplots(figsize=(7.2, 3.4), constrained_layout=True)
        for offset, agent in ((-0.19, "baseline"), (0.19, "intelligent")):
            data = summary[summary.agent == agent].set_index("config")
            ax.bar([index + offset for index in range(len(names))],
                   [data.loc[name, f"{metric}_mean"] for name in names],
                   yerr=[data.loc[name, f"{metric}_std"] for name in names],
                   width=0.36, capsize=4, label=agent, color=colors[agent])
        ax.set_xticks(range(len(names)), names)
        ax.set_ylabel(label)
        ax.set_ylim(0, 110)
        ax.grid(axis="y", alpha=0.15)
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False)
        fig.savefig(directory / filename, dpi=180)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.2, 3.4), constrained_layout=True)
    for index, name in enumerate(names):
        values = paired[paired.config == name].completed_groups_delta.to_list()
        ax.scatter([index + (position % 5 - 2) * 0.035 for position in range(len(values))],
                   values, alpha=0.65, s=32, color="#0f766e")
        ax.plot([index - .22, index + .22], [sum(values) / len(values)] * 2,
                color="#111827", linewidth=2)
    ax.axhline(0, linestyle="--", color="#64748b", linewidth=1)
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("Dokončené skupiny: intelligent - baseline")
    ax.grid(axis="y", alpha=.15)
    fig.savefig(directory / "paired_deltas.png", dpi=180)
    plt.close(fig)


def _documentation(manifest, runs, summary, paired, paired_summary):
    def mean_sd(row, metric):
        return f"{row[f'{metric}_mean']:.2f} ± {row[f'{metric}_std']:.2f}"

    configs = _markdown_table(
        ["Konfigurácia", "Izby", "Žiadosti/deň", "Porucha/izba/deň"],
        [(config["name"], config["number_of_rooms"],
          f"{config['min_requests']}-{config['max_requests']}", config["outage_probability"])
         for config in manifest["configs"]])
    outcomes = _markdown_table(
        ["Konfigurácia", "Agent", "Dokončené skupiny", "Úspešnosť (%)"],
        [(row.config, row.agent, mean_sd(row, "completed_groups"), mean_sd(row, "fulfillment_rate"))
         for _, row in summary.iterrows()])
    secondary = _markdown_table(
        ["Konfigurácia", "Agent", "Zhoda typu (%)", "Obsadenosť (%)"],
        [(row.config, row.agent, mean_sd(row, "exact_type_match_rate"), mean_sd(row, "occupancy"))
         for _, row in summary.iterrows()])
    winners = _markdown_table(
        ["Konfigurácia", "Výhry I", "Výhry B", "Remízy", "Rozdiel skupín"],
        [(row.config, int(row.intelligent_wins), int(row.baseline_wins), int(row.ties),
          f"{row.completed_groups_delta_mean:.2f} ± {row.completed_groups_delta_std:.2f}")
         for _, row in paired_summary.iterrows()])
    computation = _markdown_table(
        ["Konfigurácia", "Agent", "Čas behu (ms)", "Prerušené skupiny"],
        [(row.config, row.agent,
          f"{row.runtime_s_mean * 1000:.2f} ± {row.runtime_s_std * 1000:.2f}",
          mean_sd(row, "disrupted_groups")) for _, row in summary.iterrows()])
    discussion = []
    for _, row in paired_summary.iterrows():
        group = summary[summary.config == row.config].set_index("agent")
        match = group.loc["intelligent", "exact_type_match_rate_mean"] - group.loc["baseline", "exact_type_match_rate_mean"]
        discussion.append(
            f"V konfigurácii {row.config} bol priemerný párový rozdiel "
            f"{row.completed_groups_delta_mean:.2f} dokončených skupín. "
            f"Intelligent vyhral v {int(row.intelligent_wins)} pároch, baseline v "
            f"{int(row.baseline_wins)}; {int(row.ties)} párov skončilo remízou. "
            f"Zhoda typu izby sa v priemere zmenila o {match:.2f} percentuálneho bodu.")
    losses = paired[paired.completed_groups_delta < 0].sort_values("completed_groups_delta")
    failure = "V tomto súbore nebola zaznamenaná párová prehra; nejde však o dôkaz všeobecnej dominancie."
    if not losses.empty:
        loss = losses.iloc[0]
        pair = runs[(runs.config == loss.config) & (runs.seed == loss.seed)].set_index("agent")
        failure = (f"Konkrétny neúspech: {loss.config}, seed {int(loss.seed)}. "
                   f"Baseline dokončil {int(pair.loc['baseline', 'completed_groups'])} skupín, "
                   f"intelligent {int(pair.loc['intelligent', 'completed_groups'])}. "
                   "Priebeh je uložený v runs/<konfigurácia>/<seed>/<agent>/actions.csv a events.csv. "
                   "Príčinu jednotlivých odmietnutí možno overiť podľa ID žiadosti, dátumov a predchádzajúcich "
                   "alokácií. Samotné agregáty nedokazujú, ktorý krok plánovania spôsobil prehru.")
    seed_end = manifest["base_seed"] + manifest["repetitions"] - 1
    detail_keys = ("start_date", "intake_days", "max_lead_days", "min_stay", "max_stay",
                   "room_weights", "demand_weights", "min_repair_days", "max_repair_days",
                   "cancellation_probability")
    configurations = manifest["configs"]
    shared = all(all(config[key] == configurations[0][key] for key in detail_keys)
                 for config in configurations)
    details = []
    for config in configurations[:1] if shared else configurations:
        prefix = "Spoločné nastavenie" if shared else f"Nastavenie {config['name']}"
        details.append(
            f"{prefix}: príjem {config['intake_days']} dní od {config['start_date']}; "
            f"predstih 0-{config['max_lead_days']} dní; pobyt {config['min_stay']}-{config['max_stay']} nocí; "
            f"váhy typov izieb {config['room_weights']} a dopytu {config['demand_weights']}; "
            f"oprava {config['min_repair_days']}-{config['max_repair_days']} dni; "
            f"pravdepodobnosť zrušenia {config['cancellation_probability']:.2f}.")
    configuration_details = " ".join(details)
    return f"""# Inteligentný agent pre správu hotela

Zadanie č. 1 - návrh, implementácia a experimentálne vyhodnotenie agenta

Experimenty: {manifest['run_count']} behov, {manifest['pair_count']} párov scenárov. Reprodukčná sada bola vytvorená {manifest['created_at_utc'][:10]}.

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

Ohraničenie je jednoduché: najviac päť poradí a chamtivý výber izby v každom. Neskúša všetky permutácie, kombinácie izieb ani strategické odmietnutia. Nezaručuje optimum ani pre dnešnú dávku. Počet porovnaní izieb v jednom volaní bol najviac {int(runs.max_decision_checks.max())}; celkom sa v sade skúšalo {int(runs.plans_checked.sum())} plánov. Nejde o tvrdý časový limit, práca závisí aj od veľkosti dávky a kalendárov.

Dobré rozhodnutie môže zlyhať pre budúcu poruchu, neskorší neznámy dopyt alebo kombináciu termínov, ktorú päť poradí nenájde. Počet presťahovaní ani konkrétna akcia nie sú samy osebe odmenou.

## 10. Experimenty a reprodukovateľnosť

{configs}

{configuration_details} Zrušenie je možné iba pre žiadosti s aspoň jedným celým dňom medzi prijatím a príchodom (predstih >=2). Nastane striktne po prijatí a pred príchodom; nastavená pravdepodobnosť sa preto nevzťahuje na všetky bezprostredné príchody.

Každá konfigurácia používa {manifest['repetitions']} seedov {manifest['base_seed']}-{seed_end}. Jeden scenár sa predgeneruje a použije v dvoch oddelených prostrediach. Poruchy majú samostatný RNG a stabilné ID izieb; zrušenia stabilné ID žiadostí. Rozhodnutia agenta nemenia generovanie externých udalostí.

Po príjmovej fáze simulácia pokračuje po posledný plánovaný odchod všetkých žiadostí scenára, vrátane odmietnutých a zrušených. Horizont aj dostupné kapacity sú preto rovnaké pre oba svety; nedokončené budúce rezervácie nie sú mylne vyhodnotené ako úspechy.

Tabuľky uvádzajú priemer a výberovú smerodajnú odchýlku (ddof=1), nie interval spoľahlivosti. Párové rozdiely používajú intelligent - baseline. Časy sú merané cez perf_counter vrátane in-memory simulácie, bez ukladania výsledkov a kreslenia grafov; závisia od počítača a nie sú deterministické. Verzie Pythonu/knižníc, konfigurácie, SHA-256 zdrojov a scenárov sú uložené v manifest.json. Reprodukcia presných scenárov vyžaduje aj rovnakú verziu Pythonu: publikovaný Python bol {manifest['python']}.

## 11. Výsledky

{outcomes}

![Úspešnosť skupín: priemer a smerodajná odchýlka](figures/fulfillment.png)

{secondary}

![Zhoda preferovaného typu: priemer a smerodajná odchýlka](figures/room_match.png)

{winners}

![Párové rozdiely dokončených skupín; čierna čiara je priemer](figures/paired_deltas.png)

{computation}

Vo všetkých publikovaných behoch bolo spolu {int(runs.failed_actions.sum())} neplatných akcií. To overuje integráciu agentov a aktuátorov v tejto sade, nie neprítomnosť každej možnej chyby.

## 12. Porovnanie a interpretácia

{' '.join(discussion)}

Agenti sa líšia poradím dennej dávky aj výberom izby. Baseline môže obsadiť izbu dlhou žiadosťou pred dvoma nadväzujúcimi krátkymi alebo prideliť malú skupinu do veľkej izby. Intelligent porovná niekoľko poradí, zachováva menšie vhodné izby a tesnejšie voľné okná. Vyššia obsadenosť sama osebe neznamená viac dokončených skupín, pretože dlhé pobyty zapĺňajú viac nocí ako krátke.

{failure}

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

Na Windows použite .venv\\Scripts\\python.exe namiesto .venv/bin/python. Závislosti možno pripnúť cez requirements-lock.txt. CLI umožňuje zmeniť preset, seed, izby a dni. Počet žiadostí, pobyty a pravdepodobnosti patria do JSON cez --config-file; --rooms a --days majú prednosť. Experiments vždy použije tri presety a --seed je prvý seed série. --output mení cieľ a --no-plots vypína grafy. Súbory configs/*.json sú príklady.

Bez argumentov sa spustí porovnanie. Compare a simulate zapisujú do results/compare a results/simulation; demo do results/demo. Každý beh obsahuje actions.csv, events.csv, daily.csv, metrics.csv a batches.csv s pôvodným a vybraným poradím. Celá sada je v results/experiments vrátane manifestu a párových tabuliek. Opakovaný príkaz používa rovnaký adresár; na zachovanie predošlých výsledkov zadajte iný --output. Report vyžaduje aktuálne zdrojové hashe. Ukážková zmena na obhajobe: main.py compare --rooms 6 --seed 1111 --output results/defense.

## 15. Zdroje, knižnice a nástroje

Rozhodovací mechanizmus je explicitný Python kód bez hotového agentného frameworku alebo predtrénovaného rozhodovacieho modelu. Základné doménové triedy a pôvodnú kostru pripravil autor projektu. Pri dokončení bol použitý OpenAI Codex na návrh, implementáciu, testovanie a prípravu dokumentácie. O prípustnosti takejto pomoci rozhodujú pravidlá vyučujúceho.

- Python štandardná knižnica: random, dataclasses, enum, datetime, unittest, argparse, csv, json a hashlib. Dokumentácia generátora: https://docs.python.org/3/library/random.html
- pandas: spracovanie CSV a agregácia experimentov. https://pandas.pydata.org/docs/
- Matplotlib: grafy, bez grafického používateľského rozhrania. https://matplotlib.org/stable/users/index.html
- ReportLab: vytvorenie PDF a vloženie Unicode fontu DejaVu Sans dodávaného s Matplotlib. https://docs.reportlab.com/

Presné verzie knižníc pre experimenty sú v manifest.json a requirements-lock.txt. Knižnice nevykonávajú výber izby za agenta.
"""


def _inline(text):
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r'<font name="DejaVuMono">\1</font>', escaped)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)


def _render_pdf(markdown: str, output: Path, source_dir: Path):
    import matplotlib
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    fonts = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, filename in (("DejaVu", "DejaVuSans.ttf"), ("DejaVuBold", "DejaVuSans-Bold.ttf"),
                           ("DejaVuMono", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVuBold", italic="DejaVu", boldItalic="DejaVuBold")
    body = ParagraphStyle("body", fontName="DejaVu", fontSize=9.5, leading=14,
                          spaceAfter=7, textColor=colors.HexColor("#172033"))
    h1 = ParagraphStyle("title", parent=body, fontName="DejaVuBold", fontSize=20,
                        leading=26, spaceAfter=14, keepWithNext=True)
    h2 = ParagraphStyle("section", parent=body, fontName="DejaVuBold", fontSize=13,
                        leading=18, spaceBefore=13, spaceAfter=8, keepWithNext=True)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.3, leading=11, spaceAfter=0)
    caption = ParagraphStyle("caption", parent=body, fontSize=8.3, leading=11,
                             textColor=colors.HexColor("#475569"), spaceAfter=10)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, bulletIndent=0,
                            bulletFontName="DejaVu", bulletFontSize=9.5)
    width = A4[0] - 90
    flow, paragraph, table_lines = [], [], []

    def flush_paragraph():
        if paragraph:
            flow.append(Paragraph(_inline(" ".join(paragraph)), body))
            paragraph.clear()

    def flush_table():
        if not table_lines:
            return
        rows = [[part.strip() for part in line.strip("|").split("|")] for line in table_lines]
        rows = [row for row in rows if not all(re.fullmatch(r"[-: ]+", value) for value in row)]
        cells = [[Paragraph(_inline(value), cell) for value in row] for row in rows]
        table = Table(cells, colWidths=[width / len(rows[0])] * len(rows[0]), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#94a3b8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ]))
        flow.extend([table, Spacer(1, 10)])
        table_lines.clear()

    for line in markdown.splitlines() + [""]:
        if line.startswith("|"):
            flush_paragraph()
            table_lines.append(line)
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
        elif line.startswith("# "):
            flush_paragraph()
            flow.append(Paragraph(_inline(line[2:]), h1))
        elif line.startswith("## "):
            flush_paragraph()
            flow.append(Paragraph(_inline(line[3:]), h2))
        elif line.startswith("!["):
            flush_paragraph()
            match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
            if match is None:
                raise ValueError("Invalid figure reference")
            image = Image(str(source_dir / match.group(2)))
            image.drawHeight = width * image.imageHeight / image.imageWidth
            image.drawWidth = width
            flow.extend([image, Paragraph(_inline(match.group(1)), caption)])
        elif line.startswith("- "):
            flush_paragraph()
            flow.append(Paragraph(_inline(line[2:]), bullet, bulletText="-"))
        else:
            paragraph.append(line)

    def footer(canvas, document):
        canvas.setFont("DejaVu", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(45, 25, "UI Hotel Agent - dokumentácia")
        canvas.drawRightString(A4[0] - 45, 25, str(document.page))

    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=45, rightMargin=45,
                                 topMargin=40, bottomMargin=42, title="Inteligentný agent pre správu hotela")
    document.build(flow, onFirstPage=footer, onLaterPages=footer)


def generate_report(results_dir="results/experiments", output="output/pdf/documentation.pdf"):
    directory, output = Path(results_dir), Path(output)
    manifest, runs, summary, paired, paired_summary = _load_results(directory)
    source_dir = ROOT / "docs"
    source_dir.mkdir(exist_ok=True)
    _figures(summary, paired, source_dir / "figures")
    markdown = _documentation(manifest, runs, summary, paired, paired_summary)
    (source_dir / "documentation_sk.md").write_text(markdown, encoding="utf-8")
    _render_pdf(markdown, output, source_dir)
    return output.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results/experiments")
    parser.add_argument("--output", default="output/pdf/documentation.pdf")
    args = parser.parse_args()
    print(generate_report(args.results, args.output))
