      *> MAPTIVA stamped extract skeleton - card T404/03
      *> T404 Term - T404/03
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T404-03-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  TERM-DATE-TERMINATION-DATE-CCYYMMDD PIC 9(8)         *> cols 9-16 Req
           05  USAGE-CODE-5-USAGE-CODE-5    PIC X            *> cols 17-17 Opt
           05  WIRE-IND                     PIC X            *> cols 18-18 Opt
           05  FILLER-019-019               PIC X(1)         *> cols 19-19 Not Used
           05  DTL-FUND-ID-FUNDS            PIC X(3)         *> cols 20-22 Opt
           05  CNTRB-FLG-CONTR-EARN         PIC X            *> cols 23-23 Opt
           05  DTL-EXACT-FLG-EXACT          PIC X            *> cols 24-24 Opt
           05  DISB-UNSH-CODE-MEDIUM        PIC X            *> cols 25-25 Opt
           05  REQ-UNSH-CODE-TYPE           PIC X            *> cols 26-26 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-CASH PIC 9(9)V99      *> cols 27-37 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-SHARES-ANNUITY-OR PIC 9(7)V9(4)    *> cols 27-37 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-PERCENT-OR PIC 9(3)V99      *> cols 27-31 Opt
           05  FILLER-032-037               PIC X(6)         *> cols 32-37 Not Used
           05  CHAIN-FLG-LINK-PREV          PIC X            *> cols 38-38 Opt
           05  PDF-INDEX-RESERVED-FOR-FUTURE-USE PIC X(2)         *> cols 39-40 Opt
           05  PDF-CHAIN-FLG-RESERVED-FOR-FUTURE-USE PIC X            *> cols 41-41 Opt
           05  FILLER-042-043               PIC X(2)         *> cols 42-43 Not Used
           05  DTL-FUND-ID-FUNDS-044        PIC X(3)         *> cols 44-46 Opt
           05  CNTRB-FLG-CONTR-EARN-047     PIC X            *> cols 47-47 Opt
           05  DTL-EXACT-FLG-EXACT-048      PIC X            *> cols 48-48 Opt
           05  DISB-UNSH-CODE-MEDIUM-049    PIC X            *> cols 49-49 Opt
           05  REQ-UNSH-CODE-TYPE-050       PIC X            *> cols 50-50 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-CASH-051 PIC 9(9)V99      *> cols 51-61 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-SHARES-ANNUITY-OR-051 PIC 9(7)V9(4)    *> cols 51-61 Opt
           05  DTL-AMT-AMT-SHRS-VARIANT-PERCENT-OR-051 PIC 9(3)V99      *> cols 51-55 Opt
           05  FILLER-056-061               PIC X(6)         *> cols 56-61 Not Used
           05  CHAIN-FLG-LINK-PREV-062      PIC X            *> cols 62-62 Opt
           05  PDF-INDEX-RESERVED-FOR-FUTURE-USE-063 PIC X(2)         *> cols 63-64 Opt
           05  PDF-CHAIN-FLG-RESERVED-FOR-FUTURE-USE-065 PIC X            *> cols 65-65 Opt
           05  FILLER-066-080               PIC X(15)        *> cols 66-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO TERM-DATE-TERMINATION-DATE-CCYYMMDD
           MOVE <source-field> TO USAGE-CODE-5-USAGE-CODE-5
           MOVE <source-field> TO WIRE-IND
           MOVE SPACES TO FILLER-019-019
           MOVE <source-field> TO DTL-FUND-ID-FUNDS
           MOVE <source-field> TO CNTRB-FLG-CONTR-EARN
           MOVE <source-field> TO DTL-EXACT-FLG-EXACT
           MOVE <source-field> TO DISB-UNSH-CODE-MEDIUM
           MOVE <source-field> TO REQ-UNSH-CODE-TYPE
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-CASH
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-SHARES-ANNUITY-OR
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-PERCENT-OR
           MOVE SPACES TO FILLER-032-037
           MOVE <source-field> TO CHAIN-FLG-LINK-PREV
           MOVE <source-field> TO PDF-INDEX-RESERVED-FOR-FUTURE-USE
           MOVE <source-field> TO PDF-CHAIN-FLG-RESERVED-FOR-FUTURE-USE
           MOVE SPACES TO FILLER-042-043
           MOVE <source-field> TO DTL-FUND-ID-FUNDS-044
           MOVE <source-field> TO CNTRB-FLG-CONTR-EARN-047
           MOVE <source-field> TO DTL-EXACT-FLG-EXACT-048
           MOVE <source-field> TO DISB-UNSH-CODE-MEDIUM-049
           MOVE <source-field> TO REQ-UNSH-CODE-TYPE-050
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-CASH-051
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-SHARES-ANNUITY-OR-051
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-VARIANT-PERCENT-OR-051
           MOVE SPACES TO FILLER-056-061
           MOVE <source-field> TO CHAIN-FLG-LINK-PREV-062
           MOVE <source-field> TO PDF-INDEX-RESERVED-FOR-FUTURE-USE-063
           MOVE <source-field> TO PDF-CHAIN-FLG-RESERVED-FOR-FUTURE-USE-065
           MOVE SPACES TO FILLER-066-080
