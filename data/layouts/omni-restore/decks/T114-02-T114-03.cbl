      *> MAPTIVA stamped extract skeleton - card T114/02-T114/03
      *> T114 Cont - T114/02 and T114/03
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T114-02-T114-03-REC.
           05  TRAN-CODE-TRANSACTION-CODE   PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  CNTRB-FUND-ID-FUND-SOURCE    PIC X(3)         *> cols 9-11 Opt
           05  CATCHUP-OPTION-CNTB-COLS-9-11 PIC X            *> cols 12-12 Opt
           05  AMT-US-AMOUNT                PIC 9(9)V99      *> cols 13-23 Opt
           05  CNTRB-FUND-ID-FUND-SOURCE-024 PIC X(3)         *> cols 24-26 Opt
           05  CATCHUP-OPTION-CNTB-COLS-24-26 PIC X            *> cols 27-27 Opt
           05  AMT-US-AMOUNT-028            PIC 9(9)V99      *> cols 28-38 Opt
           05  CNTRB-FUND-ID-FUND-SOURCE-039 PIC X(3)         *> cols 39-41 Opt
           05  CATCHUP-OPTION-CNTB-COLS-39-41 PIC X            *> cols 42-42 Opt
           05  AMT-US-AMOUNT-043            PIC 9(9)V99      *> cols 43-53 Opt
           05  CNTRB-FUND-ID-FUND-SOURCE-054 PIC X(3)         *> cols 54-56 Opt
           05  CATCHUP-OPTION-CNTB-COLS-54-56 PIC X            *> cols 57-57 Opt
           05  AMT-US-AMOUNT-058            PIC 9(9)V99      *> cols 58-68 Opt
           05  ST-TAXED-401K                PIC X            *> cols 69-69 Opt
           05  AS-OF-PERCENT-OPT-AS-OF-PERCENT-FLAG PIC X            *> cols 70-70 Opt
           05  FILLER-071-080               PIC X(10)        *> cols 71-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE-TRANSACTION-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO CNTRB-FUND-ID-FUND-SOURCE
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-9-11
           MOVE <source-field> TO AMT-US-AMOUNT
           MOVE <source-field> TO CNTRB-FUND-ID-FUND-SOURCE-024
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-24-26
           MOVE <source-field> TO AMT-US-AMOUNT-028
           MOVE <source-field> TO CNTRB-FUND-ID-FUND-SOURCE-039
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-39-41
           MOVE <source-field> TO AMT-US-AMOUNT-043
           MOVE <source-field> TO CNTRB-FUND-ID-FUND-SOURCE-054
           MOVE <source-field> TO CATCHUP-OPTION-CNTB-COLS-54-56
           MOVE <source-field> TO AMT-US-AMOUNT-058
           MOVE <source-field> TO ST-TAXED-401K
           MOVE <source-field> TO AS-OF-PERCENT-OPT-AS-OF-PERCENT-FLAG
           MOVE SPACES TO FILLER-071-080
