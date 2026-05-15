# BotFather setup — do this BEFORE running the gateway

Open @BotFather on Telegram. For each row below:
1. `/newbot` → name → username (suffix `_bot`)
2. Copy the token into `.env` as `TELEGRAM_TOKEN_<KEY>`
3. `/setprivacy` → Disable (so bots can read all group messages, not just mentions)
4. `/setuserpic` → upload avatar
5. `/setdescription` → set about text
6. `/setname` → set display name

| KEY            | Username            | Display name           | Emoji | About text |
|----------------|---------------------|------------------------|-------|------------|
| ORCHESTRATOR   | @lacakin_bot        | Lacakin                | 🛵    | Asisten investigasi motor hilang. Saya yang koordinasi tim. |
| CCTV           | @mata_bandung_bot   | Mata Bandung           | 👁️    | Saya mengawasi CCTV pelindung. Tick tiap 30 detik. |
| MARKETPLACE    | @pasar_bot          | Pemantau Pasar         | 🛒    | Saya cek Tokopedia + OLX. Listing motor curiga? Saya laporkan. |
| PARTS          | @cadang_bot         | Pemburu Suku Cadang    | 🔧    | Motor dijual potong? Saya cari spare part-nya. |
| SOSMED         | @sosmed_bot         | Pengintai Sosmed       | 📱    | Marketplace Facebook + Instagram. Saya stalker yang baik. |
| POLISI         | @polisi_ai_bot      | Polisi-AI              | 👮    | Saya bantu draft laporan polisi. Bukan polisi sungguhan. |
| REPORT         | @laporan_bot        | Pencatat Laporan       | 📋    | Saya rangkum semua temuan. Tiap 90 detik / on-demand. |

(Usernames must be globally unique on Telegram. If `@lacakin_bot` is taken,
pick `@lacakin_demo_bot` etc. and update bindings to match.)

## After all 7 are created

1. Create a new Telegram **group** "Lacakin · Demo".
2. Add all 7 bots. Promote each one to **admin** (settings → Administrators).
   Admin permissions needed: send messages, edit messages (for pinned summary).
3. Send any message in the group, then run:
   ```bash
   curl "https://api.telegram.org/bot$TELEGRAM_TOKEN_ORCHESTRATOR/getUpdates"
   ```
   Find `"chat":{"id":-100xxxxxxx, ...}` and put that into `.env` as
   `LACAKIN_GROUP_ID`.
4. Confirm: each bot's `getMe` returns its own username:
   ```bash
   for k in ORCHESTRATOR CCTV MARKETPLACE PARTS SOSMED POLISI REPORT; do
     tok=$(printenv "TELEGRAM_TOKEN_$k")
     echo "$k: $(curl -s https://api.telegram.org/bot$tok/getMe | jq -r .result.username)"
   done
   ```
