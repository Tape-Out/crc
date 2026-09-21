# crc

Configurable CRC engine: polynomial, width, reflection and seed.

![maturity](https://img.shields.io/badge/maturity-simulated-yellow) ![license](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0%20OR%20MulanPSL--2.0-blue)

Part of the [Tape-Out](https://github.com/Tape-Out) IP library: Bluespec IP over the
bus-neutral contracts in [`hwcore`](https://github.com/Tape-Out/hwcore), assembled by
[`xirang`](https://github.com/Tape-Out/xirang). Maturity runs `planned` -> `simulated` ->
`fpga-proven` -> `asic-ready` -> `silicon-proven`.

## Status

Simulated. Software sets the six parameters of the Rocksoft model (width, polynomial, seed, input and output reflection, final XOR), writes `start`, feeds bytes and reads the result.

The work is split by what each part is. The algorithm is `Gf2` in `hwcore`, written in Bluespec Haskell: a CRC is a bit step unrolled over the input bits, and the width is a numeric type, so a model given as constants folds into an XOR network while a model held in registers becomes this peripheral. `CrcWide.bs` left-aligns the width chosen at run time inside a `maxWidth`-bit register. `Crc.bsv` decides when to step and when to start again from the seed, which is a scheduling question and stays in BSV.

The testbench programs every model from the [RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/) that fits `maxWidth`, feeds `123456789` and reads back the catalogue check value: CRC-7/MMC, CRC-8/MAXIM-DOW, CRC-15/CAN, CRC-16/XMODEM, CRC-16/IBM-3740, CRC-32/ISO-HDLC and CRC-32/ISCSI. With `reflect` off, the reflection bits cannot be set. `cfg.width` only takes 1 to `maxWidth`; any other write is refused.

| maxWidth | 8 | 20 | 32 |
| :--: | --: | --: | --: |
| Area, um2, `reflect` off | 1260 | 2754 | 4385 |
| Area, um2, `reflect` on | 1349 | 2932 | 4443 |

## Registers

| Offset | Register | Fields |
| :--: | :-- | :-- |
| 0x00 | `ctrl` | `start` (write 1 to begin again from the seed) |
| 0x04 | `cfg` | `width` 5:0, `refin` 8, `refout` 9 |
| 0x08 | `poly` | polynomial without the top term |
| 0x0C | `seed` | register value before the first byte |
| 0x10 | `xorout` | value XORed into the result |
| 0x14 | `data` | write one byte to feed it |
| 0x18 | `result` | CRC of the bytes fed since `start` |

Reset leaves the engine set up for CRC-8/MAXIM-DOW, the 1-Wire CRC.

## License

任选其一：

- [MIT](LICENSE-MIT)
- [Apache 2.0](LICENSE-APACHE)
- [木兰宽松许可证 第2版](LICENSE-MULAN)

`SPDX-License-Identifier: MIT OR Apache-2.0 OR MulanPSL-2.0`

除非另行说明，你提交的贡献按上述三者同时授权，不附加其他条件。
