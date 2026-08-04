      ******************************************************************
      * BENFTABL.CPY -- PLAN BENEFIT TABLE
      *
      * CLASSIC INITIALIZED-TABLE PATTERN: FIXED LITERALS REDEFINED
      * AS AN OCCURS TABLE.  EACH ENTRY IS 25 BYTES:
      *   BEN-PLAN-CODE   X(3)      BYTES  1-3
      *   BEN-DEDUCTIBLE  9(5)V99   BYTES  4-10  (ASSUMED DECIMAL)
      *   BEN-COINS-PCT   V99       BYTES 11-12  (20 MEANS .20)
      *   BEN-OOP-MAX     9(5)V99   BYTES 13-19
      *   FILLER          X(1)      BYTE  20
      *   BEN-COPAY       9(3)V99   BYTES 21-25
      ******************************************************************
       01  BENEFIT-TABLE-INIT.
           05  FILLER              PIC X(25)
               VALUE "PPO0050000200600000 02500".
           05  FILLER              PIC X(25)
               VALUE "HMO0000000100450000 01500".
           05  FILLER              PIC X(25)
               VALUE "EPO0075000250700000 03000".
           05  FILLER              PIC X(25)
               VALUE "POS0100000300800000 04000".
       01  BENEFIT-TABLE REDEFINES BENEFIT-TABLE-INIT.
           05  BENEFIT-ENTRY OCCURS 4 TIMES INDEXED BY BEN-IDX.
               10  BEN-PLAN-CODE       PIC X(03).
               10  BEN-DEDUCTIBLE      PIC 9(5)V99.
               10  BEN-COINS-PCT       PIC V99.
               10  BEN-OOP-MAX         PIC 9(5)V99.
               10  FILLER              PIC X(01).
               10  BEN-COPAY           PIC 9(3)V99.
