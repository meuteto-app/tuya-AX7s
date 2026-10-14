# Firmware dumps (stock, generic)

Read over the UART root shell from the flash (`cat /dev/mtdblockN`). These are the **generic,
per-model** partitions — the same image on every unit of this doorbell. Per-device partitions
(overlay/env/id/private/UDISK — Wi-Fi credentials, device identity/keys) are **not** included.

| file | mtd | size | content |
|---|---|---|---|
| `mtd0_uboot.bin` | mtd0 | 1 MB | U-Boot |
| `mtd1_boot.bin` | mtd1 | 3 MB | kernel — u-boot legacy uImage, ARM OpenWrt Linux-4.9.118 |
| `mtd2_rootfs.bin` | mtd2 | 10.5 MB | root filesystem — Squashfs 4.0 (zlib). Includes `/usr/bin/ipphone` |

Verify: `sha256sum -c SHA256SUMS`

Extract the rootfs with `unsquashfs mtd2_rootfs.bin`.

## Notes

- `mtd1_boot.bin` is a standard u-boot uImage; extract the kernel with `dumpimage -T kernel -p 0`.
- The rootfs is OpenWrt-style (overlay at runtime). `/usr/bin/ipphone` is the Tuya application.
  It embeds some hex constants near `auth_key` strings whose exact role is unconfirmed — treat
  them as unknown, do not assume they are usable credentials.
- `stock-config/` has the two factory config files from the rootfs, handy for reference:
  - `config.cfg` — system/door/network defaults. Useful knobs: `talk_volume` (intercom volume),
    `ring_vol`, `ring_time`, `door_lock_delay`, `pairing_mode` (0 = EZ, 1 = AP).
  - `net_cfg.cfg` — default network settings.
