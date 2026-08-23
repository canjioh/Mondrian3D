# Mondrian 3D

Decostruzione interattiva di un quadro neoplastico (tipo Mondrian) in **livelli
di profondità**. Ogni sezione diventa un **parallelepipedo 3D con spessore**:
frontalmente il quadro si ricompone, ruotando i livelli si separano davvero nello
spazio, con esplosione, spirale e allontanamento regolabili. Esporta un **video**.

Ci sono due versioni. **Usa quella HTML** (qualità 3D vera con luci e ombre).

---

## ▶ Versione HTML/WebGL  (consigliata — alta qualità)

File: `mondrian3d.html`  +  cartella `lib/` (Three.js, già inclusa, funziona offline).

### Avvio
Fai **doppio clic su `Avvia_Mondrian3D.bat`**.
Parte un mini‑server locale e si apre il browser sull'app.
(Serve perché i browser bloccano i moduli JS aperti come `file://`; con il
server locale tutto funziona, anche senza internet.)
Per chiudere: chiudi la finestra nera del server.

> In alternativa, da terminale nella cartella:
> `python -m http.server 8000` e poi apri `http://localhost:8000/mondrian3d.html`

### Vista 3D
- **Trascina** = ruota. **Rotella** = zoom.
- **Esplosione**: quanto si allontanano i livelli in profondità.
- **Spirale**: ogni livello ruota attorno all'asse di profondità (allontanamento a spirale).
- **Allontanamento**: i livelli profondi si dilatano verso l'esterno.
- **Passo profondità** e **Spessore tessere**.
- **Asse di rotazione X / Y / Z**: usato dall'**auto‑rotazione** e dal **video**.
- **Ricompони**: torna alla vista frontale (il quadro originale). **Reset vista**.

### Editor
- **Trascina** = crea un rettangolo con **colore** e **livello** correnti.
- **Click** = seleziona una tessera. Numero al centro = livello di profondità.
- Colori predefiniti o **colore libero**; griglia magnetica; elimina/annulla.

### Esporta video
- Imposta durata, FPS, giri, e avvia **Registra ed esporta**.
- Il video ruota attorno all'asse scelto (aprendo l'esplosione).
- Formato: **MP4** se il browser lo supporta, altrimenti **WebM** (video standard,
  convertibile in MP4 con qualunque strumento; Chrome recente e Safari fanno MP4).

### File
- **Salva/Carica JSON** e **Esempio Mondrian**. I quadri sono liste di tessere
  `x, y, w, h, color, layer` in coordinate 0..1 (origine in basso a sinistra).

---

## Versione Python  (fallback — genera MP4 “veri”)

File: `mondrian3d.py`. Qualità inferiore (render software) ma **export MP4 nativo
garantito**. Richiede: `numpy Pillow imageio imageio-ffmpeg` (già installati).

```
python mondrian3d.py
```
Stesse funzioni (vista 3D, editor, scelta asse, export MP4).
