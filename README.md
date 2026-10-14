# tuya-AX7s — AGL Wi-Fi doorbell (Allwinner V316 / "AX7s") teardown & root

Reverse-engineering notes for a **Tuya-based Wi-Fi audio doorbell** whose main SoC is marked
**`AX7s` / `AYz Tech`** — which turns out to be an **Allwinner V316** (`sun8iw19`) running Linux.

Unit documented here: **AGL "Interfone Wi-Fi Hello+"** (product code `1106211`,
[aglfechaduras.com.br](https://www.aglfechaduras.com.br/)), sold in Brazil. It is an **audio-only**
intercom (no camera), two modules (outdoor "porteiro" + indoor "interfone"), works with the
**AGL Home / Tuya Smart / Smart Life** apps. The indoor board is silkscreened **`WF009-V1.0`**
(dated 2021-12-10). The same board/SoC is likely used by other rebadged Tuya audio doorbells.

> Everything here was found on the author's own device. No device-specific secrets
> (local keys, device IDs, Wi-Fi credentials, cloud API keys) are published — get your own with
> the steps below.

## TL;DR

- The SoC marked **`AX7s`** is an **Allwinner V316** (`Hardware: sun8iw19`), ARMv7, **Linux 4.9.118**,
  **musl** libc, OpenWrt-style (squashfs + jffs2 overlay).
- There is a **UART debug console** on header **`J1`**, next to the SoC. **115200 8N1.**
- Pressing Enter on the console drops into an **unauthenticated root shell** (`root@(none):/#`).
  No password.
- The Tuya application is **`/usr/bin/ipphone`**. Audio is standard **ALSA** (mic + speaker),
  so the hardware can be driven by your own code once you stop `ipphone`.
- The Tuya cloud link (MQTT over TLS to `m2.tuyaus.com:8883`) is **certificate-pinned** to Tuya's
  own self-signed CA, so a network MITM is not possible — but with root on the box that no longer
  matters.

## Hardware

| Part | Detail |
|---|---|
| Main SoC | **Allwinner V316** (`sun8iw19`), marked `AX7s` / `AYz Tech`, QFN. ARMv7 (Cortex-A7) |
| Indoor board | `WF009-V1.0` (2021-12-10) |
| Speakerphone codec | `HPS MC34118` (voice-switched speakerphone IC — the half-duplex audio) |
| Audio amp | 8-pin amp driving the speaker (connector `CN4`, `SPK+/SPK-`) |
| Wi-Fi | **SSV6xxx** SDIO module (driver `ssv6xxx`), with an IPEX/u.FL antenna (`RF1`) |
| SPI-NAND flash | ~16 MB (see partition table) |
| microSD | slot present (`J2`); empty by default (kernel logs `sunxi-mmc sdc0 ... RTO` when empty) |
| Mic | electret on `CN3` (`M+ M-`) |

### Modules & external wiring (enclosure terminals)

- **Outdoor module (porteiro):** mains powered (`~ ~`, AC 110-240 V), bell button, mic/speaker,
  and the **`FF`** 12 V lock output (driven by two Darlington transistors, MJD127 + MJD122).
- **Indoor module (interfone):** `1 2` two-wire bus to the outdoor unit, `+12V -` DC input
  (included 12 V 1 A supply). The Wi-Fi/brain lives here.
- Units talk over the **2-wire bus** (`1`-`1`, `2`-`2`). The key/app lock command sends a pulse to
  the outdoor `FF` output.

## UART root console (J1)

`J1` is a **3-pin header** next to the SoC, with series resistors `R33/R34/R35` beside it
(typical UART). Pinout on the documented unit:

```
J1 (3 holes, in a column):
  - MIDDLE  = SoC TX   (board -> you; this is the console output)
  - one END = SoC RX   (you -> board; for typing)
  - GND: not on J1 on this unit — take it from the microSD metal cage, a GND test pad,
         or the Wi-Fi shield.  (Confirm with a meter; see note.)
```

- **115200 baud, 8N1, 3.3 V logic.**
- Connect only a 3.3 V USB-UART: `RX(adapter) <- TX(J1 middle)`, `TX(adapter) -> RX(J1 end)`,
  `GND <-> GND`. Do **not** feed Vcc.
- Press **Enter** → `root@(none):/#`. Open root shell, no login.
- The empty-microSD kernel spam is noisy; quiet it with `echo 1 > /proc/sys/kernel/printk`.

> Note: identify TX empirically — connect only adapter-RX + GND first and power up; the hole that
> streams the boot log at 115200 is TX. The other two J1 holes are RX and (sometimes) GND; try the
> remaining holes for RX. Series resistors protect against touching the wrong one.

See [`hardware/`](hardware/) for board photos and [`tools/`](tools/) for helper scripts.

## System

```
# uname -a
Linux (none) 4.9.118 #... PREEMPT ... armv7l GNU/Linux
# Hardware (from /proc/cpuinfo): sun8iw19   (Allwinner V316)
# libc: /lib/ld-musl-armhf.so.1  (musl, ARM hard-float)
```

Rootfs is OpenWrt-style overlay:

```
/dev/root           /rom     squashfs  ro
/dev/by-name/rootfs_data /overlay jffs2 rw
overlayfs:/overlay  /        overlay   rw   (lowerdir=/, upperdir=/overlay/upper)
```

The overlay (`rootfs_data`) is **small** (512 KB on this unit, nearly full), so persistent changes
must be tiny. `/tmp` and `/run` are **tmpfs** (RAM) and writable — run your own binaries from there.

### Flash partitions (`/proc/mtd`)

| mtd | size | name | notes |
|---|---|---|---|
| mtd0 | 0x100000 (1 MB) | uboot | |
| mtd1 | 0x300000 (3 MB) | boot | kernel |
| mtd2 | 0xa80000 (10.5 MB) | rootfs | squashfs (ro) |
| mtd3 | 0x80000 (512 KB) | rootfs_data | jffs2 overlay (rw) |
| mtd4 | 0x20000 (128 KB) | env | boot env |
| mtd5 | 0x10000 (64 KB) | misc | |
| mtd6 | 0x8000 (32 KB) | id | |
| mtd7 | 0x10000 (64 KB) | private | per-device data |
| mtd8 | 0xb8000 (736 KB) | UDISK | |

Block devices are under `/dev/by-name/` and `/dev/mtdblockN`.

### What runs

- **`/usr/bin/ipphone`** (~2.6 MB) — the Tuya client: cloud MQTT, the P2P audio session, and the
  doorbell logic. It logs key presses to the console as `[D/digbell][Digbell_key_proc:470]
  message=0x10/0x12 ...`.
- `wpa_supplicant -Dnl80211 -iwlan0`, `udhcpc -i wlan0` (station), `udhcpd` (for the setup
  hotspot / AP mode).
- busybox userland. **Minimal applets** on this build — no `wget`, `nc`, `tftp`, `base64`, `od`,
  `dd`, `wc`, `command`. Plan transfers around that (UART raw, microSD, or rebuild busybox).

### Audio (ALSA)

Full ALSA (`libasound.so.2`). Devices:

```
/dev/snd/controlC0  controlC1
/dev/snd/pcmC0D0c   (capture)   pcmC0D0p (playback)   pcmC1D0c (2nd capture)
```

So the mic and speaker are reachable from your own ALSA program once `ipphone` is stopped
(it holds the audio devices).

## Tuya / cloud notes (generic)

- Local LAN control works with the standard **Tuya 3.3** protocol on **TCP 6668** using the
  per-device **local key**. Get your own key by pairing once (Smart Life app) and running the
  [tinytuya](https://github.com/jasonacox/tinytuya) cloud wizard. Example DP map for this product
  (IDs are product-generic, not secret):

  | DP | code | meaning |
  |---|---|---|
  | 101 | basic_indicator | status LED on/off (bool, rw) |
  | 109 | sd_storge | SD capacity string |
  | 110 | sd_status | SD status (1-5) |
  | 111 | sd_format | format SD (bool) |
  | 136 | doorbell_active | ring event (string) |
  | 148 | — | **lock / `FF` pulse** (bool, rw, auto-resets ~2 s) |
  | 154 | doorbell_pic | ring snapshot URL (placeholder; no camera) |
  | 162 | device_restart | reboot (bool, rw) |
  | 185 | alarm_message | ring/alarm payload (`{"cmd":"ipc_doorbell",...}`) |
  | 231 | — | lock channel list (`{"chs":[{"id":0,"n":"DOOR"}]}`) |

- Ring is detectable locally by watching DP `185`/`136`; the lock/`FF` can be fired locally with
  DP `148`. No camera, so `154` is a placeholder.
- **Cloud signaling is cert-pinned.** `m2.tuyaus.com:8883` (MQTT/TLS) presents a **self-signed
  "Tuya Global Inc." certificate** (CN `*.tuyaus.com` + all regions, valid 2018-2118), and the
  device trusts only that CA. TLS 1.2 only, `ECDHE-RSA-AES128-GCM-SHA256`. A self-signed MITM cert
  is rejected with `TLSV1_ALERT_UNKNOWN_CA`. The device also ignores the DHCP-provided DNS and uses
  hardcoded resolvers (`8.8.8.8`, `114.114.114.114`). Net result: you cannot impersonate the Tuya
  cloud from the network — but with the UART root shell you don't need to.
- The exploit/conversion toolkits do **not** apply here: tuya-convert (ESP82xx only),
  tuya-cloudcutter (Beken/Realtek Wi-Fi MCUs only), thingino/OpenIPC (Ingenic/SigmaStar *camera*
  SoCs). This is an Allwinner audio SoC — rooted via the open UART console instead.

## Status / TODO

- [x] Identify SoC (Allwinner V316 / sun8iw19), get UART root shell, map system.
- [ ] Firmware dump (partitions) — pending a transfer method (busybox has no `dd`/`base64`/`nc`;
      options: UART raw with `stty`, a microSD card, or rebuilt tools).
- [ ] Local two-way audio bridge: a small static ARMv7 (`GOARCH=arm GOARM=7 CGO_ENABLED=0`, or
      zig `arm-linux-musleabihf`) ALSA↔network daemon; stop `ipphone`, run it, talk over the LAN —
      fully local, no cloud.

Contributions welcome if you have the same or a similar `AX7s` / Allwinner V316 Tuya doorbell.
