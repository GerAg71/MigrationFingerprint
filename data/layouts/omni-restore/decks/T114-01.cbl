      *> MAPTIVA stamped extract skeleton - card T114/01
      *> T114 Cont - T114/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T114-01-REC.
           05  TRAN-CODE-TRANSACTION-CODE   PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  FORMAT-FLAG                  PIC X            *> cols 9-9 Opt
           05  DIV-SUB-LOCATION-CODE        PIC X(4)         *> cols 10-13 Opt
           05  FILLER-014-017               PIC X(4)         *> cols 14-17 Not Used
           05  CNTRB-FUND-ID-1-FUND-SOURCE  PIC X(3)         *> cols 18-20 Opt
           05  CATCHUP-OPTION-CNTB-COLS-18-20 PIC X            *> cols 21-21 Opt
           05  AMT-US-1-AMOUNT              PIC 9(9)V99      *> cols 22-32 Opt
           05  CNTRB-FUND-ID-2-FUND-SOURCE  PIC X(3)         *> cols 33-35 Opt
           05  CATCHUP-OPTION-CNTB-COLS-33-35 PIC X            *> cols 36-36 Opt
           05  AMT-US-2-AMOUNT              PIC 9(9)V99      *> cols 37-47 Opt
           05  CNTRB-FUND-ID-3-FUND-SOURCE  PIC X(3)         *> cols 48-50 Opt
           05  CATCHUP-OPTION-CNTB-COLS-48-50 PIC X            *> cols 51-51 Opt
           05  AMT-US-3-AMOUNT              PIC 9(9)V99      *> cols 52-62 Opt
           05  ST-TAXED-401K-STATE-TAX      PIC X            *> cols 63-63 Opt
           05  SUSP-OV-SUSPENSION-OVERRIDE  PIC X            *> cols 64-64 Opt
           05  USAGE-CODE-3                 PIC X(3)         *> cols 65-67 Opt
           05  ALLOC-METHOD-ALLOCATION-METHOD PIC X            *> cols 68-68 Opt
           05  PURCH-UNSHRS-FLG-SHARE-PURCHASE-OPTIONS PIC X            *> cols 69-69 Opt
           05  RECEIVED-IN-FLG-CONTRIBUTION-AMOUNTS-ARE-SHARES-UNIT PIC X            *> cols 70-70 Opt
           05  EE-PRETAX-LMT-OV-PRETAX-LIMIT-OVERRIDE PIC X            *> cols 71-71 Opt
           05  F-415-LMT-OV-415-LIMIT-OVERRIDE PIC X            *> cols 72-72 Opt
           05  OVERRIDE-CALC-IND            PIC X            *> cols 73-73 Opt
           05  IRA-LIMIT-OVERRIDE           PIC X            *> cols 74-74 Opt
           05  FILLER-075-080               PIC X(6)         *> cols 75-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE-TRANSACTION-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO FORMAT-FLAG
           MOVE <source-field> TO DIV-SUB-LOCATION-CODE
           MOVE SPACES TO FILLER-014-017
           MOVE <source-field> TO CNTRB-FUND-ID-1-FUND-SOURCE
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-18-20
           MOVE <source-field> TO AMT-US-1-AMOUNT
           MOVE <source-field> TO CNTRB-FUND-ID-2-FUND-SOURCE
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-33-35
           MOVE <source-field> TO AMT-US-2-AMOUNT
           MOVE <source-field> TO CNTRB-FUND-ID-3-FUND-SOURCE
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-48-50
           MOVE <source-field> TO AMT-US-3-AMOUNT
           MOVE <source-field> TO ST-TAXED-401K-STATE-TAX
           MOVE <source-field> TO SUSP-OV-SUSPENSION-OVERRIDE
           MOVE <source-field> TO USAGE-CODE-3
           MOVE <source-field> TO ALLOC-METHOD-ALLOCATION-METHOD
           MOVE <source-field> TO PURCH-UNSHRS-FLG-SHARE-PURCHASE-OPTIONS
           MOVE <source-field> TO RECEIVED-IN-FLG-CONTRIBUTION-AMOUNTS-ARE-SHARES-UNIT
           MOVE <source-field> TO EE-PRETAX-LMT-OV-PRETAX-LIMIT-OVERRIDE
           MOVE <source-field> TO F-415-LMT-OV-415-LIMIT-OVERRIDE
           MOVE <source-field> TO OVERRIDE-CALC-IND
           MOVE <source-field> TO IRA-LIMIT-OVERRIDE
           MOVE SPACES TO FILLER-075-080
