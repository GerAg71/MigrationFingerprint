      *> MAPTIVA stamped extract skeleton - card T384/02
      *> T384 LN - T384/02
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T384-02-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  OLD-FUND-ID                  PIC X(3)         *> cols 9-11 Opt
           05  PRODUCT-ID                   PIC X(6)         *> cols 12-17 Opt
           05  FILLER-018-036               PIC X(19)        *> cols 18-36 Not Used
           05  USAGE-CODE-5                 PIC X            *> cols 37-37 Opt
           05  ISSUE-DATE-ISSUE-CCYYMMDD    PIC 9(8)         *> cols 38-45 Req
           05  FILLER-046-047               PIC X(2)         *> cols 46-47 Not Used
           05  ASOF-PCT-FLAG                PIC X            *> cols 48-48 Opt
           05  TYPE                         PIC X(4)         *> cols 49-52 Opt
           05  REFINANCE-FLAG-THIS-IS-A-REFINANCING-LOAN PIC X            *> cols 53-53 Opt
           05  FILLER-054-061               PIC X(8)         *> cols 54-61 Not Used
           05  ORIGINATOR-LOAN-IS-A-PLAN-LOAN PIC X            *> cols 62-62 Opt
           05  FILLER-063-063               PIC X(1)         *> cols 63-63 Not Used
           05  ADDL-LIEN-VALUE-ADDITIONAL-LIEN-VALUE PIC 9(9)V99      *> cols 64-74 Opt
           05  REFINANCE-LOAN-NUM-REFINANCE-NUM PIC X(3)         *> cols 75-77 Opt
           05  ENFORCE-NEW-REGS-ENFORCE-DEEMED-DISTRIBUTION-REGS PIC X            *> cols 78-78 Opt
           05  FILLER-079-080               PIC X(2)         *> cols 79-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO OLD-FUND-ID
           MOVE <source-field> TO PRODUCT-ID
           MOVE SPACES TO FILLER-018-036
           MOVE <source-field> TO USAGE-CODE-5
           MOVE <source-field> TO ISSUE-DATE-ISSUE-CCYYMMDD
           MOVE SPACES TO FILLER-046-047
           MOVE <source-field> TO ASOF-PCT-FLAG
           MOVE <source-field> TO TYPE
           MOVE <source-field> TO REFINANCE-FLAG-THIS-IS-A-REFINANCING-LOAN
           MOVE SPACES TO FILLER-054-061
           MOVE <source-field> TO ORIGINATOR-LOAN-IS-A-PLAN-LOAN
           MOVE SPACES TO FILLER-063-063
           MOVE <source-field> TO ADDL-LIEN-VALUE-ADDITIONAL-LIEN-VALUE
           MOVE <source-field> TO REFINANCE-LOAN-NUM-REFINANCE-NUM
           MOVE <source-field> TO ENFORCE-NEW-REGS-ENFORCE-DEEMED-DISTRIBUTION-REGS
           MOVE SPACES TO FILLER-079-080
