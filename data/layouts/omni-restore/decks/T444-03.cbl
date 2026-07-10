      *> MAPTIVA stamped extract skeleton - card T444/03
      *> T444 With - T444/03
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T444-03-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-019               PIC X(14)        *> cols 6-19 Not Used
           05  DTL-FUND-ID-FUNDS            PIC X(3)         *> cols 20-22 Opt
           05  CNTRB-FLG-CONTR-EARN         PIC X            *> cols 23-23 Opt
           05  DTL-EXACT-FLG-EXACT          PIC X            *> cols 24-24 Opt
           05  DISB-UNSH-CODE-MEDIUM        PIC X            *> cols 25-25 Opt
           05  REQ-UNSH-CODE-TYPE           PIC X            *> cols 26-26 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-CASH PIC 9(9)V99      *> cols 27-37 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-SHARES-ANNUITY-OR PIC 9(7)V9(4)    *> cols 27-37 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-PERCENT-OR PIC 9(3)V99      *> cols 27-31 Opt
           05  FILLER-032-037               PIC X(6)         *> cols 32-37 Not Used
           05  CHAIN-FLG-LINK-PREV          PIC X            *> cols 38-38 Opt
           05  FILLER-039-049               PIC X(11)        *> cols 39-49 Not Used
           05  DTL-FUND-ID-FUNDS-050        PIC X(3)         *> cols 50-52 Opt
           05  CNTRB-FLG-CONTR-EARN-053     PIC X            *> cols 53-53 Opt
           05  DTL-EXACT-FLG-EXACT-054      PIC X            *> cols 54-54 Opt
           05  DISB-UNSH-CODE-MEDIUM-055    PIC X            *> cols 55-55 Opt
           05  REQ-UNSH-CODE-TYPE-056       PIC X            *> cols 56-56 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-CASH-057 PIC 9(9)V99      *> cols 57-67 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-SHARES-ANNUITY-OR-057 PIC 9(7)V9(4)    *> cols 57-67 Opt
           05  DTL-AMT-AMT-SHRS-ANNU-VARIANT-PERCENT-OR-057 PIC 9(3)V99      *> cols 57-61 Opt
           05  FILLER-062-067               PIC X(6)         *> cols 62-67 Not Used
           05  CHAIN-FLG-LINK-PREV-068      PIC X            *> cols 68-68 Opt
           05  FILLER-069-079               PIC X(11)        *> cols 69-79 Not Used
           05  FILLER-080-080               PIC X(1)         *> cols 80-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-019
           MOVE <source-field> TO DTL-FUND-ID-FUNDS
           MOVE <source-field> TO CNTRB-FLG-CONTR-EARN
           MOVE <source-field> TO DTL-EXACT-FLG-EXACT
           MOVE <source-field> TO DISB-UNSH-CODE-MEDIUM
           MOVE <source-field> TO REQ-UNSH-CODE-TYPE
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-CASH
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-SHARES-ANNUITY-OR
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-PERCENT-OR
           MOVE SPACES TO FILLER-032-037
           MOVE <source-field> TO CHAIN-FLG-LINK-PREV
           MOVE SPACES TO FILLER-039-049
           MOVE <source-field> TO DTL-FUND-ID-FUNDS-050
           MOVE <source-field> TO CNTRB-FLG-CONTR-EARN-053
           MOVE <source-field> TO DTL-EXACT-FLG-EXACT-054
           MOVE <source-field> TO DISB-UNSH-CODE-MEDIUM-055
           MOVE <source-field> TO REQ-UNSH-CODE-TYPE-056
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-CASH-057
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-SHARES-ANNUITY-OR-057
           MOVE <source-field> TO DTL-AMT-AMT-SHRS-ANNU-VARIANT-PERCENT-OR-057
           MOVE SPACES TO FILLER-062-067
           MOVE <source-field> TO CHAIN-FLG-LINK-PREV-068
           MOVE SPACES TO FILLER-069-079
           MOVE SPACES TO FILLER-080-080
