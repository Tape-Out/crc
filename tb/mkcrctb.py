"""crc 的行为测试台：按 RevEng 目录的模型编程，喂 "123456789"，读回的必须是目录里的校验值。

认矩阵：`maxWidth` 装不下的模型跳过。`reflect` 关着时只测不反射的模型，另加一条：
照 CRC-8/MAXIM-DOW 编程（refin、refout 都写 1），两位写不进去，结果按不反射算。
那一条的期望值来自本脚本里的逐位参考实现，而这份实现生成之前先对着目录的七个
校验值自证一遍，不对就不生成。

一个字节写进来的下一拍才步进，所以连着喂的九个字节是背靠背写的——哪一拍丢了一个，
校验值就对不上。
"""
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out.mkdir(parents=True, exist_ok=True)
cfg = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
label = cfg.get("label", "")
knobs = cfg.get("knobs", {})
maxw = int(knobs.get("maxWidth", 32))
reflect = bool(knobs.get("reflect", True))

# (名字, 宽度, 多项式, 初值, refin, refout, xorout, 校验值)——RevEng 目录原文
MODELS = [
    ("CRC-7/MMC", 7, 0x09, 0x00, False, False, 0x00, 0x75),
    ("CRC-8/MAXIM-DOW", 8, 0x31, 0x00, True, True, 0x00, 0xA1),
    ("CRC-15/CAN", 15, 0x4599, 0x0000, False, False, 0x0000, 0x059E),
    ("CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000, 0x31C3),
    ("CRC-16/IBM-3740", 16, 0x1021, 0xFFFF, False, False, 0x0000, 0x29B1),
    ("CRC-32/ISO-HDLC", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xCBF43926),
    ("CRC-32/ISCSI", 32, 0x1EDC6F41, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xE3069283),
]
MSG = b"123456789"
CTRL, CFG, POLY, SEED, XOROUT, DATA, RESULT = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18


def ref(w, poly, seed, rin, rout, xo, data):
    mask = (1 << w) - 1
    c = seed
    for byte in data:
        for i in range(8):
            bit = (byte >> i) & 1 if rin else (byte >> (7 - i)) & 1
            top = (c >> (w - 1)) & 1
            c = ((c << 1) & mask) ^ (poly if top ^ bit else 0)
    if rout:
        c = int(f"{c:0{w}b}"[::-1], 2)
    return c ^ xo


for m in MODELS:
    if ref(*m[1:7], MSG) != m[7]:
        raise SystemExit(f"参考实现算 {m[0]} 不对，不生成测试台")

cases = [m for m in MODELS if m[1] <= maxw and (reflect or not (m[4] or m[5]))]
if not reflect:
    n, w, p, s, ri, ro, x, _ = MODELS[1]
    cases.append((f"{n} with reflect off", w, p, s, ri, ro, x, ref(w, p, s, False, False, x, MSG)))

ops = []            # (类别, 地址, 数据, 第几个模型)：0 写、1 空一拍、2 读并比较
for i, (n, w, p, s, ri, ro, x, want) in enumerate(cases):
    ops += [(0, CFG, w | (int(ri) << 8) | (int(ro) << 9), i),
            (0, POLY, p, i), (0, SEED, s, i), (0, XOROUT, x, i), (0, CTRL, 1, i)]
    # 喂到第四个字节时往 ctrl 写 0：start 是写 1 才重来，写 0 若也重来，结果就成了 "56789" 的 CRC
    ops += [(0, DATA, b, i) for b in MSG[:4]] + [(0, CTRL, 0, i)] + [(0, DATA, b, i) for b in MSG[4:]]
    ops += [(1, 0, 0, i), (1, 0, 0, i), (2, RESULT, want, i)]

body = "\n".join(f"    16'd{j}: return Op {{ kind: {k}, addr: 8'h{a:02X}, data: 32'h{d:08X}, idx: {i} }};"
                 for j, (k, a, d, i) in enumerate(ops))
names = "\n".join(f'    {i}: return "{c[0]}";' for i, c in enumerate(cases))
verdict = (f"{len(cases)} catalogue models give their check values at maxWidth {maxw} with a 0 written to ctrl mid-message"
           + ("" if reflect else ", and refin and refout cannot be set with reflect off"))

txt = f'''package Crc{label}Tb;

// 由 tb/mkcrctb.py 生成，勿手改。这一点：maxWidth={maxw} reflect={reflect}

import RegIf::*;
import Crc::*;

typedef struct {{
  Bit#(2)  kind;
  Bit#(8)  addr;
  Bit#(32) data;
  Bit#(8)  idx;
}} Op deriving (Bits);

function Op op(Bit#(16) i);
  case (i)
{body}
    default: return Op {{ kind: 1, addr: 0, data: 0, idx: 0 }};
  endcase
endfunction

function String name(Bit#(8) i);
  case (i)
{names}
    default: return "?";
  endcase
endfunction

(* synthesize *)
module mkCrc{label}Tb(Empty);
  CrcIfc#(8, 32, {maxw}) d <- mkCrc(CrcCfg {{ reflect: {"True" if reflect else "False"} }});

  Reg#(Bit#(16)) pc  <- mkReg(0);
  Reg#(Bool)     bad <- mkReg(False);

  rule run;
    if (pc == {len(ops)}) begin
      if (bad) $display("FAILED");
      else $display("PASS crc: {verdict}");
      $finish(bad ? 1 : 0);
    end else begin
      Op o = op(pc);
      case (o.kind)
        0: begin
          let _ <- d.regs.access(RegReq {{ addr: o.addr, write: True, wdata: o.data, wstrb: '1 }});
        end
        2: begin
          let x <- d.regs.access(RegReq {{ addr: o.addr, write: False, wdata: 0, wstrb: '1 }});
          if (x.rdata != o.data) begin
            $display("FAIL %s reads %08h, want %08h", name(o.idx), x.rdata, o.data);
            bad <= True;
          end
        end
        default: noAction;
      endcase
      pc <= pc + 1;
    end
  endrule
endmodule

endpackage
'''

(out / f"Crc{label}Tb.bsv").write_text(txt, encoding="utf-8")
print(f"  crc 行为测试台就位：maxWidth={maxw} reflect={reflect}，{len(cases)} 个模型")
