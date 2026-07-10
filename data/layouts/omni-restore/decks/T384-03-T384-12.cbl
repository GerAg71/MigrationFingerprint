      *> MAPTIVA stamped extract skeleton - card T384/03-T384/12
      *> T384 LN - T384/03 through T384/12
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T384-03-T384-12-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  FUND-ID2-FUND-IDS            PIC X(3)         *> cols 9-11 Req
           05  BORROW-FLAG-AMOUNT-FLAG      PIC X            *> cols 12-12 Opt
           05  DTL-EXACT-FLAG               PIC X            *> cols 13-13 Opt
           05  BORROW-AMT-AMOUNT-PERCENT-IF-CASH-VARIANT-1 PIC 9(6)V99      *> cols 14-21 Req
           05  BORROW-PCT-AMOUNT-PERCENT-IF-PERCENT-VARIANT-2-OR PIC 9(4)V9(4)    *> cols 14-21 Req
           05  FILLER-022-022               PIC X(1)         *> cols 22-22 Not Used
           05  FUND-ID2-FUND-IDS-023        PIC X(3)         *> cols 23-25 Req
           05  BORROW-FLAG-AMOUNT-FLAG-026  PIC X            *> cols 26-26 Opt
           05  DTL-EXACT-FLAG-027           PIC X            *> cols 27-27 Opt
           05  BORROW-AMT-AMOUNT-PERCENT-IF-CASH-VARIANT-1-028 PIC 9(6)V99      *> cols 28-35 Req
           05  BORROW-PCT-AMOUNT-PERCENT-IF-PERCENT-VARIANT-2-OR-028 PIC 9(4)V9(4)    *> cols 28-35 Req
           05  FILLER-036-080               PIC X(45)        *> cols 36-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO FUND-ID2-FUND-IDS
           MOVE <source-field> TO BORROW-FLAG-AMOUNT-FLAG
           MOVE <source-field> TO DTL-EXACT-FLAG
           MOVE <source-field> TO BORROW-AMT-AMOUNT-PERCENT-IF-CASH-VARIANT-1
           MOVE <source-field> TO BORROW-PCT-AMOUNT-PERCENT-IF-PERCENT-VARIANT-2-OR
           MOVE SPACES TO FILLER-022-022
           MOVE <source-field> TO FUND-ID2-FUND-IDS-023
           MOVE <source-field> TO BORROW-FLAG-AMOUNT-FLAG-026
           MOVE <source-field> TO DTL-EXACT-FLAG-027
           MOVE <source-field> TO BORROW-AMT-AMOUNT-PERCENT-IF-CASH-VARIANT-1-028
           MOVE <source-field> TO BORROW-PCT-AMOUNT-PERCENT-IF-PERCENT-VARIANT-2-OR-028
           MOVE SPACES TO FILLER-036-080
