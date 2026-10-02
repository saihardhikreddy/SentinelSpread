# SentinelSpread — Manual Testing Guide

Three layers you can test by hand, from "just the crypto" up to "the full
RF chain, and hear it." All commands run from `C:\Users\csaih\sentinelspread`.

## 1. Crypto round-trip (any text or file, no GNU Radio needed)

```powershell
python cli.py encrypt -i "Hello, this is a secret" --type text -o bundle.bin --save-keys
python cli.py decrypt -i bundle.bin -k keys\private_key.pem -o recovered.txt
type recovered.txt
```

Works with a real file too — text or audio:

```powershell
python cli.py encrypt -i path\to\notes.txt --type text -o bundle.bin -k keys\public_key.pem
python cli.py encrypt -i path\to\clip.wav --type audio -o bundle.bin -k keys\public_key.pem
```

This only exercises Stage 1 (AES-256-GCM + RSA-OAEP). No modem, no DSSS, no
GNU Radio — fastest way to sanity-check the crypto layer with your own data.

## 2. Full GNU Radio software SDR loopback (text/message)

```powershell
python cli.py sdr-loopback --message "Hello from the real flowgraph" --sf 16 --noise 0.02 --freq-offset 0.0005
```

This runs your actual text through: encrypt → BPSK map → DSSS spread → RRC
shape → AWGN+frequency-offset channel → RRC matched filter → symbol sync →
Costas loop → despread → decrypt, all inside a real GNU Radio flowgraph.
Exit code 0 + `[PASS - EXACT MATCH]` means it worked.

**You can already feed it a real file**, not just a literal string — pass a
file path as the message and it'll pick it up automatically:

```powershell
python cli.py sdr-loopback --message "C:\path\to\notes.txt" --sf 16 --noise 0.02
```

(`InputHandler.prepare_text_payload` checks `Path(...).is_file()` first and
reads the file's bytes if it exists, falling back to treating the string as
literal text otherwise — this already works today, no code change needed.)

Turn up `--noise` or `--freq-offset` to see where it breaks (that's exactly
what the propagation-verification script already does deliberately with
Costas removed).

## 3. Listen to the signal (new — `listen_to_signal.py`)

This is the one that lets you actually **hear** what's happening, using your
real crypto + modem + DSSS modules (not a toy reimplementation) — no GNU
Radio required, runs under your normal project Python (radioconda's works
fine too, since it has numpy/scipy):

```powershell
python sentinelspread\listen_to_signal.py --text "Your secret message here"
```

or with a real file:

```powershell
python sentinelspread\listen_to_signal.py --file path\to\notes.txt
```

It writes three WAV files to `listen_out\` and prints the pipeline as it
goes (encrypted bundle size, bit count, bit errors, decrypted text). Play
them in order — any media player or Audacity handles this fine:

1. **`1_narrowband.wav`** — your encrypted bits, BPSK, pulse-shaped, but
   **not spread**. A clean, rhythmic buzz — unmistakably "a signal."
2. **`2_spread_sf16.wav`** — the *exact same bits*, DSSS-spread at SF=16
   before shaping. Same duration, same message — but it sounds like
   broadband hiss/static. This is the whole point of DSSS made audible:
   spreading the same energy over 16× the bandwidth pushes it toward the
   noise floor, including to your ear.
3. **`3_spread_noisy.wav`** — the spread signal plus heavy AWGN (−8 dB
   SNR, deliberately harsh). Sounds like pure static. The script then
   despreads, demodulates, and decrypts *this exact noisy signal* and
   prints the recovered plaintext — proving the message survives even
   though it's audibly and spectrally indistinguishable from noise.

If you want it noisier or cleaner, edit `NOISY_SNR_DB` near the top of the
script (currently `-8.0`; verified to decode with 0 bit errors at that
level, and will start occasionally failing to decrypt below about −10 dB —
that failure is AES-GCM's all-or-nothing authenticated-encryption behavior
working as designed, not a bug, since a single flipped bit anywhere in the
331-byte crypto bundle invalidates the whole message rather than silently
corrupting it).

### Why the file sizes/sample rates differ

File 1 is written at 8000 Hz (comfortably audible). File 2/3 carry 16×
more chips in the same time span, so they're written at 128000 Hz to
preserve real-time duration — most players handle that transparently. If
yours doesn't, Audacity (File → Import → Raw Data, or just opening the
.wav directly) will.
