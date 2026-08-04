      ******************************************************************
      * CLAIMREC.CPY -- HEALTHCARE CLAIM RECORD LAYOUT
      *
      * MONETARY FIELDS ARE PACKED DECIMAL (COMP-3) WITH TWO
      * ASSUMED DECIMAL PLACES (PIC S9(N)V99).
      ******************************************************************
       01  CLAIM-RECORD.
           05  CLM-ID                  PIC X(10).
           05  CLM-MEMBER-ID           PIC X(08).
           05  CLM-PLAN-CODE           PIC X(03).
           05  CLM-TYPE                PIC X(02).
               88  CLM-TYPE-MEDICAL        VALUE "MD".
               88  CLM-TYPE-DENTAL         VALUE "DN".
               88  CLM-TYPE-PHARMACY       VALUE "RX".
           05  CLM-STATUS              PIC 9(01).
               88  CLM-STATUS-OPEN         VALUE 1.
               88  CLM-STATUS-ADJUDICATED  VALUE 2.
               88  CLM-STATUS-DENIED       VALUE 3.
           05  CLM-SERVICE-DATE        PIC 9(08).
           05  CLM-BILLED-AMT          PIC S9(7)V99 COMP-3.
           05  CLM-ALLOWED-AMT         PIC S9(7)V99 COMP-3.
           05  CLM-DEDUCT-APPLIED      PIC S9(5)V99 COMP-3.
           05  CLM-COINS-AMT           PIC S9(7)V99 COMP-3.
           05  CLM-PLAN-PAID-AMT       PIC S9(7)V99 COMP-3.
           05  CLM-MEMBER-RESP-AMT     PIC S9(7)V99 COMP-3.
           05  FILLER                  PIC X(10).
