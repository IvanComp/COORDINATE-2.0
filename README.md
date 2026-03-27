# AgANT of Empire

<p align="center">
  <img src="img/readme/logo.png" width="340" alt="AgANT of Empire logo"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-f2c14e">
  <img src="https://img.shields.io/badge/Flask-backend-cb6d51?logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/React-visualizer-284b63?logo=react&logoColor=61DAFB">
  <img src="https://img.shields.io/badge/Simulation-Anthill%20Life-6a994e">
</p>

## Overview

**AgANT of Empire** e un simulatore di colonia che mette in scena la vita di un formicaio come un piccolo ecosistema sociale.  
Ogni formica nasce, cresce, si muove tra camere specializzate, beve, mangia, dorme, cerca partner, genera nuova prole e prima o poi muore.

L'obiettivo non e solo osservare puntini che si spostano, ma vedere emergere una colonia viva:

- bisogni individuali che cambiano nel tempo
- strategie collettive con priorita diverse
- genealogie complete tra madri, padri e nuove generazioni
- equilibrio fragile tra espansione, sopravvivenza e stress ambientale

In breve: un formicaio simulato come se fosse un piccolo impero biologico.

---

## Il Ciclo Di Vita Di Una Formica

Ogni formica nel simulatore possiede una storia completa, tracciata dal primo minuto di vita fino alla morte.

### 1. Nascita

La colonia parte con una popolazione iniziale configurabile:

- numero totale di formiche
- numero iniziale di maschi
- distribuzione nelle camere del nido

Ogni individuo riceve fin dalla nascita:

- `sex`: maschio o femmina
- `birthTime`: istante di nascita
- `generation`: generazione genealogica
- `motherId` e `fatherId`: quando nasce da un accoppiamento
- `maturityAge`: eta minima per riprodursi
- `maxAge`: longevita massima
- livelli iniziali di `hunger`, `thirst` ed `energy`

Le formiche iniziali sono la generazione zero. Tutte quelle nate durante la simulazione espandono l'albero genealogico della colonia.

### 2. Crescita E Maturita

Durante ogni tick temporale, la formica consuma risorse vitali:

- la fame scende
- la sete scende
- l'energia si riduce

Quando raggiunge la maturita sessuale, puo partecipare alla riproduzione. Prima di quel momento e un membro giovane della colonia: si muove, sopravvive, ma non contribuisce ancora alla genealogia.

### 3. Sopravvivenza Quotidiana

La vita nel formicaio e guidata dai bisogni:

- se la fame e bassa, la formica punta alle camere del cibo
- se la sete cala, raggiunge le camere d'acqua
- se l'energia scende, cerca una camera di riposo per un micro-sonnellino

Questo crea un ritmo organico: non tutte le formiche fanno la stessa cosa nello stesso momento, e la colonia appare irregolare, credibile e viva.

### 4. Riproduzione

Quando una formica adulta incontra un partner compatibile, puo avvenire un evento di accoppiamento.

Il simulatore evita accoppiamenti con legami parentali immediati e applica alcune regole:

- i partner devono essere vivi e maturi
- devono trovarsi nella stessa camera
- devono essere di sesso opposto
- devono rispettare un tempo di recupero dall'ultimo accoppiamento

Quando l'evento va a buon fine:

- viene registrato un `mate`
- nasce una covata di dimensione variabile
- i nuovi figli compaiono nella nursery
- vengono assegnati madre, padre e nuova generazione

Da qui il formicaio non e piu solo una simulazione di movimento: diventa una storia familiare.

### 5. Riposo

Le formiche non dormono a lungo: effettuano **micro-sonnellini**.

Ogni pausa:

- inizia con `nap_start`
- dura un numero configurabile di minuti
- termina con `nap_end`
- ripristina parte dell'energia

Questo dettaglio rende il modello piu interessante, perche introduce pause frequenti, distribuite e importanti per la tenuta dell'intera colonia.

### 6. Morte

La morte puo arrivare in modi diversi:

- `starvation`: fame esaurita
- `dehydration`: sete esaurita
- `natural causes`: eta massima raggiunta
- `colony hazard`: rischio ambientale casuale

La morte non rimuove la storia della formica. Il suo profilo resta nel file genealogico, con:

- tempo di morte
- causa del decesso
- stato finale
- figli avuti
- partner incontrati
- camere visitate

---

## Caratteristiche Di Ogni Formica

Ogni individuo e modellato come una piccola entita autonoma con attributi biologici e comportamentali.

### Identita

- ID univoco
- sesso
- generazione
- madre e padre

### Stato Vitale

- fame
- sete
- energia
- viva o morta
- causa di morte

### Memoria Di Vita

- numero di pasti
- numero di bevute
- numero di movimenti
- numero di micro-sonnellini
- lista dei partner
- lista dei figli
- camere visitate

### Stato Comportamentale

- `active`
- `sleeping`
- `dead`

---

## Azioni Possibili

Nel simulatore una formica puo compiere azioni concrete, tutte registrate nel log eventi.

### Eventi Principali

- `birth`: nascita iniziale o in nursery
- `move`: spostamento verso una camera obiettivo
- `eat`: recupero del livello di fame
- `drink`: recupero del livello di sete
- `nap_start`: inizio del riposo
- `nap_end`: fine del riposo
- `mate`: accoppiamento con un partner
- `death`: termine della vita
- `resource_spawn`: impulso periodico di risorse per la colonia

Questi eventi alimentano sia la parte analitica sia la visualizzazione frontend.

---

## Il Formicaio Simulato

Il formicaio non e un contenitore astratto. E organizzato in **camere specializzate** che definiscono il comportamento della colonia.

### Camere Speciali

- `nest`: cuore del formicaio, punto di origine
- `nursery`: zona dedicata alla nuova prole
- `food`: camere dove si ripristina la fame
- `water`: camere dove si ripristina la sete
- `rest`: camere dove si accumula energia

### Topologie Disponibili

La colonia puo vivere in diverse geometrie:

- `mesh`
- `ring`
- `tree`
- layout piu estesi fino a molte decine di camere

Questo cambia il comportamento emergente:

- in topologie dense la colonia si ridistribuisce rapidamente
- in topologie lineari la distanza pesa di piu
- in topologie ramificate la nursery o le camere vitali possono diventare colli di bottiglia

Il risultato e che la stessa colonia, con gli stessi parametri, puo sembrare prudente, aggressiva o fragile solo cambiando la struttura del formicaio.

---

## Strategie Della Colonia

Il simulatore permette di scegliere una linea comportamentale generale:

- `balanced`
- `brood-focus`
- `forager`
- `hydration-first`
- `rest-guarded`
- `expansion`
- `adaptive-colony`

Ogni strategia modifica i pesi con cui la colonia reagisce ai bisogni:

- piu riproduzione
- piu raccolta e alimentazione
- piu attenzione all'idratazione
- piu difesa dell'energia

### Adaptive Colony

`adaptive-colony` osserva lo stato complessivo dei viventi e adatta la priorita interna della colonia in corso d'opera.  
Per esempio:

- se molte formiche sono scariche, il riposo diventa piu importante
- se la sete diffusa cresce, aumenta il peso dell'idratazione
- se il bilanciamento tra maschi e femmine cambia, cambia anche la pressione riproduttiva

Questa strategia rende il formicaio meno meccanico e piu simile a una societa che reagisce allo stress.

---

## Cosa Si Osserva Nella UI

L'interfaccia mostra la colonia come sistema vivente, non solo come tabella.

Puoi esplorare:

- configurazione della simulazione
- topologia del formicaio
- movimento delle formiche tra camere
- statistiche aggregate
- log eventi in tempo reale
- profilo individuale di una formica

In pratica puoi passare dallo sguardo macro, "come sta andando la colonia?", allo sguardo micro, "che fine ha fatto la formica 17 e quanti figli ha avuto?".

---

## Output Della Simulazione

Ogni esecuzione produce file utili sia per esplorazione visuale sia per analisi.

### Log CSV

Il log cronologico contiene eventi come:

- nascite
- morti
- accoppiamenti
- pasti
- bevute
- sonnellini
- movimenti

### File Genealogico JSON

Il file di lineage conserva:

- struttura della colonia
- camere speciali
- popolazione finale
- numero totale di nascite
- scheda completa di ogni formica

Questo rende il progetto utile anche per storytelling computazionale, analisi emergente e visualizzazioni genealogiche.

---

## Avvio Rapido

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m backend.app
```

### Frontend

```bash
cd ui
npm install
npm run dev
```

Poi apri:

- `http://localhost:5002` per il backend in produzione locale
- `http://localhost:5173` per lo sviluppo frontend

---

## Parametri Più Interessanti

Se vuoi "dare carattere" alla colonia, questi sono i controlli che cambiano di piu il suo stile di vita:

- `N_ANTS`: dimensione iniziale della societa
- `INITIAL_MALES`: equilibrio iniziale tra sessi
- `MATING_PROBABILITY`: intensita riproduttiva
- `BROOD_MIN` e `BROOD_MAX`: dimensione delle covate
- `MICRO_NAPS_PER_DAY`: ritmo del riposo
- `MEAL_RESTORE` e `DRINK_RESTORE`: efficacia delle camere vitali
- `FAIL_PROB`: durezza del mondo esterno
- `RESOURCE_SPAWNING_TIME`: frequenza degli impulsi di risorse
- `TOPOLOGY_NAME` e `N_ROOMS`: geografia dell'impero sotterraneo

---

## Una Lettura Narrativa Del Sistema

Se vuoi immaginare cosa stai osservando, pensa al simulatore cosi:

> Nel sottosuolo non vive un insieme di agenti astratti. Vive una colonia.  
> Alcune formiche sono giovani e irrequiete, altre sopravvivono abbastanza da lasciare discendenti.  
> Alcune muoiono di sete prima di raggiungere la nursery, altre attraversano il formicaio decine di volte e fondano intere linee genealogiche.  
> Ogni run e un piccolo impero che nasce, si organizza, prospera o collassa.

Ed e proprio questa tensione tra bisogno individuale e destino collettivo a rendere **AgANT of Empire** interessante da osservare.
