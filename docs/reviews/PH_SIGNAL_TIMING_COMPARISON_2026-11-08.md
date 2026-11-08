# Philippine traffic signal practice vs SmartFlow's fixed-time plan

Date: 2026-11-08. Purpose: check whether SmartFlow's "traditional" fixed-time signal (inherited from the SUMO stack) matches how signals are timed in the Philippines.

## Short answer

No online Philippine document states official yellow, all-red or cycle values. What is published indicates:

- the **yellow and all-red times are reasonable**;
- the **phase layout (five separate phases) probably does not match local practice**, and likely makes the traditional signal look worse than a real local signal would.

## SmartFlow's current default fixed-time plan

Defaults are in `simulation/scenario_config.py`; the Webster tool is in `simulation/signal_design.py`.

| Setting | Current default |
|---|---|
| Phases | **5, served one at a time**: north → east → south → west → pedestrians only |
| Green per phase | 14 s (allowed range 5–180 s; minimum green 10 s, maximum green 60 s) |
| Yellow | 3 s (allowed 2–6 s) |
| All-red | 1 s (allowed 1–10 s) |
| Cycle | 90 s (5 × 18 s) |
| Each approach | 14 s green, then **72 s red** every cycle |
| Webster tool | Available, saturation flow 1,800 pcu/h per 3.3 m lane; not used for the default plan |

## What was found about Philippine practice

| Topic | Evidence | Compared with SmartFlow |
|---|---|---|
| **Official standard** | DPWH Highway Safety Design Standards. Part 1 (Road Safety Design Manual, May 2012) has a section on signal-controlled intersections and cites the US Highway Capacity Manual and AASHTO. Part 2 covers signs and pavement markings. Only scanned copies are online, so the timing values could not be read. | Not confirmed |
| **How timing is designed** | Philippine teaching (UP Diliman; Sigua, *Fundamentals of Traffic Engineering*, UP Press) uses Webster's method from measured flows. A UP lecture on the MMDA Commonwealth Avenue U-turn scheme uses saturation flows of 1,800 pcu/h per lane straight through and 1,600 pcu/h per lane for left turns. | SmartFlow has a Webster tool with 1,800 pcu/h, but the default plan is not built with it |
| **A real plan in Mindanao** | El Salvador City (Misamis Oriental), a mid-sized city like Tagum, ran a **125 s, three-phase fixed-time plan** at three intersections. Amber and all-red were held at "local standards", but the values are not given. | SmartFlow uses 5 phases; this plan uses 3 |
| **Metro Manila** | A PIDS study evaluates phase length, cycle time and phase pattern at Metro Manila intersections. Only the abstract was available. | No values to compare |
| **Cycle length** | General guidance keeps cycles under about 120 s; very long cycles cause excessive delay. | 90 s is within range |
| **Yellow and all-red** | International references commonly use about 3 s yellow for approach speeds up to 60 km/h, 4 s above that, plus a short all-red. This comes from an Indian code, not a Philippine standard. | 3 s / 1 s fits 30–40 km/h roads |
| **Pedestrians** | Nothing found describing a separate pedestrian-only phase as normal Philippine practice; the El Salvador City plan is three-phase. | The separate pedestrian phase is likely unusual locally |

## What this means for the study

1. **Keep yellow 3 s and all-red 1 s**, but cite a source for the panel: Sigua's textbook or the DPWH Part 1 manual (print copies).
2. **The five single-approach phases are the weakest part.** Each approach gets 14 s of green per 90 s cycle. That makes the traditional signal look worse than a realistic local one, and would inflate how much better the RL signal looks. The engine already supports grouped phases, for example north and south together, then east and west, then turns.
3. **A fairer baseline:** a plan designed with the Webster tool from the field counts, with grouped phases and a cycle under about 125 s, labelled as designed rather than observed (neither study site has a signal today).

## Not verified

- The DPWH manuals and Sigua's textbook are not readable online. The actual Philippine yellow and all-red values remain unconfirmed; ask the adviser or the DPWH regional office.
- The UP Diliman lecture slides (PDF) were downloaded but could not be opened: no PDF text reader is installed and nothing was downloaded to read them. The figures quoted from them come from search-result summaries.
- The El Salvador City paper (MDPI) refused automated access; its details come from its abstract and a secondary summary.

## Sources

**Philippine sources**
- [DPWH Highway Safety Design Standards, Part 1: Road Safety Design Manual (Scribd)](https://www.scribd.com/document/358568221/Dpwh-Book-1-Final)
- [DPWH Highway Safety Design Standards, Part 2: Road Signs and Pavement Markings Manual (Scribd)](https://www.scribd.com/document/358574525/Dpwh-Book-2-Final)
- [Sigua, *Fundamentals of Traffic Engineering*, UP Press (Scribd, table of contents)](https://es.scribd.com/document/387070618/11-Fundamentals-of-Traffic-Engineering-Ricardo-G-Sigua-pdf)
- [UP Diliman traffic signal timing slides, Commonwealth Avenue / MMDA example (PDF)](https://d0ctrine.com/wp-content/uploads/2012/08/traffic-signal-timing-knvergel-10aug2012.pdf)
- [PIDS study of Metro Manila intersection signal parameters](https://serp-p.pids.gov.ph/publication_detail?id=3022)
- [A Lightweight Edge AI Framework for Adaptive Traffic Signal Control in Mid-Sized Philippine Cities, MDPI *Sustainability* 18(3) 1147 (El Salvador City)](https://www.mdpi.com/2071-1050/18/3/1147)
- [Secondary summary of the El Salvador City study (synapsesocial)](https://synapsesocial.com/papers/6975b36bfeba4585c2d6ed91)

**General signal-timing references (not Philippine)**
- [Traffic Signals, Engineering LibreTexts (cycle length guidance)](https://eng.libretexts.org/Bookshelves/Civil_Engineering/Fundamentals_of_Transportation/06:_Traffice_Control/6.02:_Traffic_Signals)
- [NCHRP Report 731: Guidelines for Timing Yellow and All-Red Intervals at Signalized Intersections](https://nap.nationalacademies.org/read/22700/chapter/2)
- [IRC 93: Guidelines on Design and Installation of Road Traffic Signals (India)](https://infralens.in/code/IRC-93)
- [Comparison of fixed-time and Webster's optimal signal timing (Mahidol University)](https://repository.li.mahidol.ac.th/handle/123456789/114016)
