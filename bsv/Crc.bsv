package Crc;

// 可编程 CRC：寄存器组加一个按字节步进的引擎。算法在 hwcore 的 Gf2，运行时宽度的
// 对齐在 CrcWide，两份都是 BH；这里只管什么时候步进、什么时候从初值重来。

import RegIf::*;
import CrcRegs::*;
import Gf2::*;
import CrcWide::*;

typedef struct {
  Bool reflect;
} CrcCfg;

interface CrcIfc#(numeric type aw, numeric type dw, numeric type maxWidth);
  interface RegIf#(aw, dw) regs;
endinterface

typedef union tagged {
  void    Idle;
  void    Start;
  Bit#(8) Feed;
} Pend deriving (Bits, Eq);

module mkCrc#(CrcCfg cfg)(CrcIfc#(aw, dw, maxWidth))
    provisos (Mul#(TDiv#(dw, 8), 8, dw), Add#(_a, 8, aw), Add#(_b, 1, dw),
              Add#(_c, 6, dw), Add#(_d, 8, dw), Add#(_e, maxWidth, dw),
              Add#(1, _f, maxWidth));

  CrcRegsIfc#(aw, dw, maxWidth) r <- mkCrcRegs(CrcRegsCfg { reflect: cfg.reflect });

  Reg#(Bit#(maxWidth)) crc <- mkReg(0);
  // 写脉冲在总线方法之后才有，配置寄存器却要在它之前读：拆成两条规则、隔一拍，
  // 由这个 CReg 递过去（端口 0 给步进，端口 1 给记脉冲）
  Reg#(Pend) pend[2] <- mkCReg(2, tagged Idle);

  UInt#(6) width = unpack(r.cfg_width);

  rule mark;
    if (r.ctrl_start_wr && r.ctrl_start_wr_val == 1) pend[1] <= tagged Start;
    else if (r.data_wr) pend[1] <= tagged Feed r.data_wr_val;
  endrule

  // 特性关掉时字段读回零，但硬件那一侧的方法仍是存储里的复位值，所以要与开关相与
  rule step;
    Bool rin = cfg.reflect && r.cfg_refin == 1;
    CrcModel#(maxWidth) m = wideModel(width, rin, r.poly, r.seed);
    case (pend[0]) matches
      tagged Start:   crc <= m.seed;
      tagged Feed .b: crc <= crcByte(m, crc, b);
    endcase
    pend[0] <= tagged Idle;
  endrule

  rule show;
    Bool rout = cfg.reflect && r.cfg_refout == 1;
    r.result_in(narrow(width, rout, r.xorout, crc));
  endrule

  interface regs = r.regs;
endmodule

endpackage
