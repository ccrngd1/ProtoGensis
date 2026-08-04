      ******************************************************************
      * CLAIMCALC -- HEALTHCARE CLAIM ADJUDICATION (DEMO PROGRAM)
      *
      * ADJUDICATES A BATCH OF HARD-CODED CLAIMS AGAINST THE PLAN
      * BENEFIT TABLE (BENFTABL COPYBOOK), WRITING A DETERMINISTIC
      * REPORT TO SYSOUT VIA DISPLAY.
      *
      * DEMONSTRATES: COMP-3 PACKED-DECIMAL MONEY ARITHMETIC WITH
      * COBOL TRUNCATION SEMANTICS (NO ROUNDED PHRASE), OCCURS /
      * REDEFINES TABLE LOOKUP, 88-LEVEL CONDITION NAMES, AND A
      * MULTI-PARAGRAPH PERFORM STRUCTURE.
      *
      * BUSINESS RULES:
      *   - ALLOWED AMOUNT = 80 PCT OF BILLED (TRUNCATED TO CENTS)
      *   - ANNUAL DEDUCTIBLE APPLIES FIRST (PER-MEMBER ACCUMULATOR)
      *   - MEDICAL/DENTAL: MEMBER PAYS COINSURANCE PCT OF THE
      *     POST-DEDUCTIBLE ALLOWED AMOUNT (TRUNCATED)
      *   - PHARMACY: MEMBER PAYS THE FLAT COPAY INSTEAD
      *   - UNKNOWN PLAN CODE: CLAIM DENIED, MEMBER OWES BILLED AMT
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLAIMCALC.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

       COPY CLAIMREC.

       COPY BENFTABL.

       01  INPUT-CLAIMS.
           05  FILLER              PIC X(40) VALUE
               "CLM0000001MBR00001PPOMD20260115000450000".
           05  FILLER              PIC X(40) VALUE
               "CLM0000002MBR00001PPOMD20260120000123456".
           05  FILLER              PIC X(40) VALUE
               "CLM0000003MBR00001PPODN20260201000030000".
           05  FILLER              PIC X(40) VALUE
               "CLM0000004MBR00001XXXMD20260210000050000".
           05  FILLER              PIC X(40) VALUE
               "CLM0000005MBR00001PPORX20260215000007599".
       01  INPUT-CLAIM-TABLE REDEFINES INPUT-CLAIMS.
           05  INPUT-CLAIM OCCURS 5 TIMES INDEXED BY CLM-IDX.
               10  IN-CLM-ID           PIC X(10).
               10  IN-MEMBER-ID        PIC X(08).
               10  IN-PLAN-CODE        PIC X(03).
               10  IN-CLM-TYPE         PIC X(02).
               10  IN-SERVICE-DATE     PIC 9(08).
               10  IN-BILLED-AMT       PIC 9(7)V99.

       01  WS-WORK-FIELDS.
           05  WS-CLAIM-COUNT          PIC 9(02)     VALUE 5.
           05  WS-PLAN-FOUND           PIC X(01)     VALUE "N".
               88  PLAN-FOUND              VALUE "Y".
               88  PLAN-NOT-FOUND          VALUE "N".
           05  WS-DEDUCT-MET           PIC S9(5)V99  COMP-3 VALUE 0.
           05  WS-DEDUCT-REMAIN        PIC S9(5)V99  COMP-3 VALUE 0.
           05  WS-POST-DEDUCT          PIC S9(7)V99  COMP-3 VALUE 0.
           05  WS-COINS-PCT            PIC SV99      COMP-3 VALUE 0.
           05  WS-DEDUCT-LIMIT         PIC S9(5)V99  COMP-3 VALUE 0.
           05  WS-COPAY                PIC S9(3)V99  COMP-3 VALUE 0.
           05  WS-TOT-BILLED           PIC S9(9)V99  COMP-3 VALUE 0.
           05  WS-TOT-PLAN-PAID        PIC S9(9)V99  COMP-3 VALUE 0.
           05  WS-TOT-MEMBER-RESP      PIC S9(9)V99  COMP-3 VALUE 0.

       01  WS-DISPLAY-FIELDS.
           05  WS-EDIT-AMT             PIC Z(6)9.99-.
           05  WS-EDIT-TOT             PIC Z(8)9.99-.
           05  WS-STATUS-TEXT          PIC X(11).

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-INIT
           PERFORM 2000-PROCESS-ONE-CLAIM
               VARYING CLM-IDX FROM 1 BY 1
               UNTIL CLM-IDX > WS-CLAIM-COUNT
           PERFORM 8000-PRINT-TOTALS
           PERFORM 9000-TERM
           .

       1000-INIT.
           DISPLAY "CLAIMCALC ADJUDICATION REPORT"
           DISPLAY "============================="
           MOVE ZERO TO WS-DEDUCT-MET
                        WS-TOT-BILLED
                        WS-TOT-PLAN-PAID
                        WS-TOT-MEMBER-RESP
           .

       2000-PROCESS-ONE-CLAIM.
           PERFORM 2100-LOAD-CLAIM
           PERFORM 2200-FIND-PLAN
           IF PLAN-NOT-FOUND
               PERFORM 2600-DENY-CLAIM
           ELSE
               PERFORM 2300-CALC-ALLOWED
               PERFORM 2400-APPLY-DEDUCTIBLE
               PERFORM 2500-APPLY-COST-SHARE
               SET CLM-STATUS-ADJUDICATED TO TRUE
           END-IF
           PERFORM 7000-PRINT-CLAIM
           PERFORM 7500-ACCUMULATE-TOTALS
           .

       2100-LOAD-CLAIM.
           INITIALIZE CLAIM-RECORD
           MOVE IN-CLM-ID (CLM-IDX)       TO CLM-ID
           MOVE IN-MEMBER-ID (CLM-IDX)    TO CLM-MEMBER-ID
           MOVE IN-PLAN-CODE (CLM-IDX)    TO CLM-PLAN-CODE
           MOVE IN-CLM-TYPE (CLM-IDX)     TO CLM-TYPE
           MOVE IN-SERVICE-DATE (CLM-IDX) TO CLM-SERVICE-DATE
           MOVE IN-BILLED-AMT (CLM-IDX)   TO CLM-BILLED-AMT
           SET CLM-STATUS-OPEN TO TRUE
           .

       2200-FIND-PLAN.
           SET PLAN-NOT-FOUND TO TRUE
           SET BEN-IDX TO 1
           SEARCH BENEFIT-ENTRY
               AT END
                   CONTINUE
               WHEN BEN-PLAN-CODE (BEN-IDX) = CLM-PLAN-CODE
                   SET PLAN-FOUND TO TRUE
                   MOVE BEN-DEDUCTIBLE (BEN-IDX) TO WS-DEDUCT-LIMIT
                   MOVE BEN-COINS-PCT (BEN-IDX)  TO WS-COINS-PCT
                   MOVE BEN-COPAY (BEN-IDX)      TO WS-COPAY
           END-SEARCH
           .

       2300-CALC-ALLOWED.
      *    COBOL DEFAULT: RESULT TRUNCATED TO THE RECEIVING FIELD'S
      *    SCALE (NO ROUNDED PHRASE) -- E.G. 1234.56 * .80 = 987.648
      *    STORES 987.64, NOT 987.65.
           COMPUTE CLM-ALLOWED-AMT = CLM-BILLED-AMT * 0.80
           .

       2400-APPLY-DEDUCTIBLE.
           COMPUTE WS-DEDUCT-REMAIN = WS-DEDUCT-LIMIT - WS-DEDUCT-MET
           IF WS-DEDUCT-REMAIN < ZERO
               MOVE ZERO TO WS-DEDUCT-REMAIN
           END-IF
           IF CLM-ALLOWED-AMT < WS-DEDUCT-REMAIN
               MOVE CLM-ALLOWED-AMT TO CLM-DEDUCT-APPLIED
           ELSE
               MOVE WS-DEDUCT-REMAIN TO CLM-DEDUCT-APPLIED
           END-IF
           ADD CLM-DEDUCT-APPLIED TO WS-DEDUCT-MET
           COMPUTE WS-POST-DEDUCT =
               CLM-ALLOWED-AMT - CLM-DEDUCT-APPLIED
           .

       2500-APPLY-COST-SHARE.
           IF CLM-TYPE-PHARMACY
               MOVE ZERO TO CLM-COINS-AMT
               IF WS-POST-DEDUCT < WS-COPAY
                   MOVE WS-POST-DEDUCT TO CLM-MEMBER-RESP-AMT
                   MOVE ZERO           TO CLM-PLAN-PAID-AMT
               ELSE
                   COMPUTE CLM-PLAN-PAID-AMT =
                       WS-POST-DEDUCT - WS-COPAY
               END-IF
           ELSE
      *        COINSURANCE TRUNCATES: 987.64 * .20 = 197.528 -> 197.52
               COMPUTE CLM-COINS-AMT =
                   WS-POST-DEDUCT * WS-COINS-PCT
               COMPUTE CLM-PLAN-PAID-AMT =
                   WS-POST-DEDUCT - CLM-COINS-AMT
           END-IF
      *    MEMBER OWES EVERYTHING THE PLAN DID NOT PAY, INCLUDING
      *    THE DISALLOWED PORTION OF THE BILLED CHARGE.
           COMPUTE CLM-MEMBER-RESP-AMT =
               CLM-BILLED-AMT - CLM-PLAN-PAID-AMT
           .

       2600-DENY-CLAIM.
           SET CLM-STATUS-DENIED TO TRUE
           MOVE ZERO           TO CLM-ALLOWED-AMT
                                  CLM-DEDUCT-APPLIED
                                  CLM-COINS-AMT
                                  CLM-PLAN-PAID-AMT
           MOVE CLM-BILLED-AMT TO CLM-MEMBER-RESP-AMT
           .

       7000-PRINT-CLAIM.
           EVALUATE TRUE
               WHEN CLM-STATUS-ADJUDICATED
                   MOVE "ADJUDICATED" TO WS-STATUS-TEXT
               WHEN CLM-STATUS-DENIED
                   MOVE "DENIED     " TO WS-STATUS-TEXT
               WHEN OTHER
                   MOVE "OPEN       " TO WS-STATUS-TEXT
           END-EVALUATE
           DISPLAY " "
           DISPLAY "CLAIM: " CLM-ID
               "  PLAN: " CLM-PLAN-CODE
               "  TYPE: " CLM-TYPE
               "  STATUS: " WS-STATUS-TEXT
           MOVE CLM-BILLED-AMT TO WS-EDIT-AMT
           DISPLAY "  BILLED:      " WS-EDIT-AMT
           MOVE CLM-ALLOWED-AMT TO WS-EDIT-AMT
           DISPLAY "  ALLOWED:     " WS-EDIT-AMT
           MOVE CLM-DEDUCT-APPLIED TO WS-EDIT-AMT
           DISPLAY "  DEDUCTIBLE:  " WS-EDIT-AMT
           MOVE CLM-COINS-AMT TO WS-EDIT-AMT
           DISPLAY "  COINSURANCE: " WS-EDIT-AMT
           MOVE CLM-PLAN-PAID-AMT TO WS-EDIT-AMT
           DISPLAY "  PLAN PAID:   " WS-EDIT-AMT
           MOVE CLM-MEMBER-RESP-AMT TO WS-EDIT-AMT
           DISPLAY "  MEMBER RESP: " WS-EDIT-AMT
           .

       7500-ACCUMULATE-TOTALS.
           ADD CLM-BILLED-AMT      TO WS-TOT-BILLED
           ADD CLM-PLAN-PAID-AMT   TO WS-TOT-PLAN-PAID
           ADD CLM-MEMBER-RESP-AMT TO WS-TOT-MEMBER-RESP
           .

       8000-PRINT-TOTALS.
           DISPLAY " "
           DISPLAY "============================="
           MOVE WS-TOT-BILLED TO WS-EDIT-TOT
           DISPLAY "TOTAL BILLED:      " WS-EDIT-TOT
           MOVE WS-TOT-PLAN-PAID TO WS-EDIT-TOT
           DISPLAY "TOTAL PLAN PAID:   " WS-EDIT-TOT
           MOVE WS-TOT-MEMBER-RESP TO WS-EDIT-TOT
           DISPLAY "TOTAL MEMBER RESP: " WS-EDIT-TOT
           MOVE WS-DEDUCT-MET TO WS-EDIT-TOT
           DISPLAY "DEDUCTIBLE MET:    " WS-EDIT-TOT
           .

       9000-TERM.
           DISPLAY " "
           DISPLAY "CLAIMCALC COMPLETE"
           STOP RUN
           .
