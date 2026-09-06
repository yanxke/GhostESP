# ESP32-C5 N32R8: LittleFS capture profile

The profile `configs/sdkconfig.capture.esp32c5_n32r8` targets 32 MB flash
and 8 MB quad PSRAM using ESP-IDF 6.0.2. It enables LittleFS for capture
storage and does not automatically start a capture.

## Build and flash

From the repository root in PowerShell:

```powershell
. C:\Espressif\frameworks\esp-idf-v6.0.2\export.ps1
$env:PYTHONUTF8 = "1"
idf.py -B build_capture -D SDKCONFIG=sdkconfig.capture -D SDKCONFIG_DEFAULTS=configs/sdkconfig.capture.esp32c5_n32r8 build
idf.py -B build_capture -D SDKCONFIG=sdkconfig.capture -p COM5 flash monitor
```

Replace COM5 with your device's port. These commands use a separate generated
configuration and build directory. An existing `sdkconfig.capture` takes
precedence over defaults; use the following to change its options:

```powershell
idf.py -B build_capture -D SDKCONFIG=sdkconfig.capture menuconfig
```

The partition table keeps NVS at 0x9000 and the factory application at 0x10000.
The application has 0x7D0000 bytes, followed by a 128 KiB coredump slot.
The `captures` partition occupies 0x800000 through 0x1FFFFFF: 24 MiB before
filesystem overhead. This profile has no OTA application slots.
Back up existing flash files before switching partition layouts. Flash the
bootloader and partition table as well as the application using `idf.py flash`.

## First boot and storage

An empty LittleFS partition initially fails to mount. Wait for startup to
finish, then explicitly provision it through the serial CLI:

```text
sd format-littlefs ERASE
sd status
```

The provisioning command erases the entire `captures` partition and mounts it.
It refuses to format mounted storage or an active capture. It is only needed
once; subsequent boots mount existing files. Automatic formatting on mount
failure is **off** in this profile so a mount error cannot erase captures.
The advanced `CAPTURE_LITTLEFS_FORMAT_IF_FAILED` option is deliberately left off.

Under **Ghost ESP Options → Capture storage**, enable
`CAPTURE_STORAGE_LITTLEFS` to select flash storage instead of physical SD.
Disable it to restore the existing SD/board-specific storage behavior and use
an appropriate SD board configuration. This is a build-time selection, not a
runtime hot swap. LittleFS bypasses physical SD initialization and shared-SPI
mounting, regardless of saved SD pin settings.

Files retain their existing paths, including `/mnt/ghostesp/pcaps`.
Existing `sd list`, `sd read`, `sd rm`, capture listing, and WebUI downloads
operate on LittleFS. The historical `sd` command name and WebUI SD labels
remain. `sd status` reports flash as virtual storage, with LittleFS capacity.
All files under `/mnt`, including logs and exports, share this partition.

## Capture and retrieve

For a passive capture on a known channel (replace 6 as appropriate):

```text
mem heaps
capture -eapol -c 6
capture -stop
sd list pcaps
```

`capture -raw -c 6` is also available when you want all received frame types,
including management frames, for offline analysis; it fills storage faster.
An ESP32 captures one channel at a time. Reception does not guarantee that a
complete handshake or usable hash was observed.

Always stop the capture before downloading, removing files, or rebooting.
Writes sync LittleFS at buffer flushes and close; a power loss can still lose
the current RAM buffer. Flash latency can cause dropped packets, especially
with raw capture. Check `mem heaps` during capture and after stopping.
A full partition or I/O error is reported as an incomplete capture; retrieve
the partial file and free space before starting another capture.

With the serial terminal logging to `download.log`, run (substitute the actual
filename shown by `sd list pcaps`):

```text
sd read pcaps/eapolscan_0.pcap --base64
```

Wait for `SD:READ:END` and `SD:OK`, then decode that single transfer on your PC:

```powershell
python scripts/decode_capture_log.py download.log capture.pcap
```

The decoder verifies base64 and the full-file byte counts. It refuses to
overwrite an existing output and leaves failed decodes with a `.part` suffix.
Do not treat a plain-text serial log as a PCAP file.
The existing WebUI file browser can also access the mounted files after the
capture is stopped.

Keep the original PCAP for later analysis. On a PC with
[hcxtools](https://github.com/ZerBea/hcxtools), convert it with:

```text
hcxpcapngtool -o capture.22000 capture.pcap
```

This produces Hashcat mode 22000 material when sufficient WPA/WPA2 data is
present. The existing firmware `capture -export` command has a smaller,
bounded parser (including a 128-byte EAPOL limit); PC-side conversion avoids
depending on that parser for your only saved artifact.

The storage integration uses
[joltwallet LittleFS 1.22.3](https://components.espressif.com/components/joltwallet/littlefs/versions/1.22.3/readme),
which provides the ESP-IDF VFS and IDF 6 support.
