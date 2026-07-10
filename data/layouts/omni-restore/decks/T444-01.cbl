      *> MAPTIVA stamped extract skeleton - card T444/01
      *> T444 With - T444/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T444-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-009               PIC X(4)         *> cols 6-9 Not Used
           05  LUMP-SUM-FLG-LUMP-SUM-PAYMENT PIC X            *> cols 10-10 Opt
           05  FILLER-011-011               PIC X(1)         *> cols 11-11 Not Used
           05  EXACT-TOT-FLG-WITHDRAW-EXACT-AMOUNT-GIVEN PIC X            *> cols 12-12 Opt
           05  TOT-AMT-AMOUNT               PIC 9(7)V99      *> cols 13-21 Opt
           05  MAX-OMNISCRIPT-WDRLMAX-OMNISCRIPT-SUFFIX PIC X(2)         *> cols 22-23 Opt
           05  SUSP-OMNISCRIPT-WDRLSUSP-OMNISCRIPT-SUFFIX PIC X(2)         *> cols 24-25 Opt
           05  FORF-OMNISCRIPT-WDRLFORF-OMNISCRIPT-SUFFIX PIC X(2)         *> cols 26-27 Opt
           05  TYPE-TRANSACTION-TYPE        PIC X(2)         *> cols 28-29 Opt
           05  DIV-SUB-LOCATION             PIC X(4)         *> cols 30-33 Opt
           05  SPECIAL-DIST-OPT-SPECIAL-CATEGORY PIC X            *> cols 34-34 Opt
           05  REASON-CD-WITHDRAWAL-REASON  PIC X            *> cols 35-35 Opt
           05  QVEC-REASON-CD-QVEC-REASON   PIC X            *> cols 36-36 Opt
           05  TRANSACTION-OVERRIDE         PIC X            *> cols 37-37 Opt
           05  USAGE-CODE-1-USAGE-CODE-1    PIC X            *> cols 38-38 Opt
           05  TAX-YEAR-FLAG-TAX-YEAR       PIC X            *> cols 39-39 Opt
           05  F-401K-WDR-FLG-OVERRIDE-401K-WITHDRAWAL-LIMIT PIC X            *> cols 40-40 Opt
           05  CHECK-STATUS-CHECK-STATUS    PIC X            *> cols 41-41 Opt
           05  FILLER-042-042               PIC X(1)         *> cols 42-42 Not Used
           05  GADJ-OMNISCRIPT-FLG-ADJGROSSPMT-OMNISCRIPT-OPTIONS PIC X            *> cols 43-43 Opt
           05  FILLER-044-044               PIC X(1)         *> cols 44-44 Not Used
           05  ROLLOVER-USAGE-ROLLOVER-USAGE-CODE PIC X            *> cols 45-45 Opt
           05  MAND-WHOLD-ROLL-MANDATORY-WITHHOLDING-DOES-NOT-APPLY PIC X            *> cols 46-46 Opt
           05  FILLER-047-049               PIC X(3)         *> cols 47-49 Not Used
           05  USAGE-CODE-4-USAGE-CODE-4    PIC X(4)         *> cols 50-53 Opt
           05  DISB-REASON-SPECIAL-DISB-REASON-SPECIAL PIC X(2)         *> cols 54-55 Opt
           05  APAY-KEY-SEQ                 PIC 9(3)         *> cols 56-58 Opt
           05  OLD-INST-SEQ                 PIC 9(1)         *> cols 59-59 Opt
           05  INST-NEXT-PAY-DATE           PIC 9(8)         *> cols 60-67 Opt
           05  FILLER-068-068               PIC X(1)         *> cols 68-68 Not Used
           05  QUAL-EXPENSE-DIST-FLAG       PIC X            *> cols 69-69 Opt
           05  INST-GLOBAL-PAYMENT          PIC X            *> cols 70-70 Opt
           05  INST-SETUP-TRANSACTION-SEQ   PIC 9(7)         *> cols 71-77 Opt
           05  INST-SEQ                     PIC 9(2)         *> cols 78-79 Opt
           05  FILLER-080-080               PIC X(1)         *> cols 80-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-009
           MOVE <source-field> TO LUMP-SUM-FLG-LUMP-SUM-PAYMENT
           MOVE SPACES TO FILLER-011-011
           MOVE <source-field> TO EXACT-TOT-FLG-WITHDRAW-EXACT-AMOUNT-GIVEN
           MOVE <source-field> TO TOT-AMT-AMOUNT
           MOVE <source-field> TO MAX-OMNISCRIPT-WDRLMAX-OMNISCRIPT-SUFFIX
           MOVE <source-field> TO SUSP-OMNISCRIPT-WDRLSUSP-OMNISCRIPT-SUFFIX
           MOVE <source-field> TO FORF-OMNISCRIPT-WDRLFORF-OMNISCRIPT-SUFFIX
           MOVE <source-field> TO TYPE-TRANSACTION-TYPE
           MOVE <source-field> TO DIV-SUB-LOCATION
           MOVE <source-field> TO SPECIAL-DIST-OPT-SPECIAL-CATEGORY
           MOVE <source-field> TO REASON-CD-WITHDRAWAL-REASON
           MOVE <source-field> TO QVEC-REASON-CD-QVEC-REASON
           MOVE <source-field> TO TRANSACTION-OVERRIDE
           MOVE <source-field> TO USAGE-CODE-1-USAGE-CODE-1
           MOVE <source-field> TO TAX-YEAR-FLAG-TAX-YEAR
           MOVE <source-field> TO F-401K-WDR-FLG-OVERRIDE-401K-WITHDRAWAL-LIMIT
           MOVE <source-field> TO CHECK-STATUS-CHECK-STATUS
           MOVE SPACES TO FILLER-042-042
           MOVE <source-field> TO GADJ-OMNISCRIPT-FLG-ADJGROSSPMT-OMNISCRIPT-OPTIONS
           MOVE SPACES TO FILLER-044-044
           MOVE <source-field> TO ROLLOVER-USAGE-ROLLOVER-USAGE-CODE
           MOVE <source-field> TO MAND-WHOLD-ROLL-MANDATORY-WITHHOLDING-DOES-NOT-APPLY
           MOVE SPACES TO FILLER-047-049
           MOVE <source-field> TO USAGE-CODE-4-USAGE-CODE-4
           MOVE <source-field> TO DISB-REASON-SPECIAL-DISB-REASON-SPECIAL
           MOVE <source-field> TO APAY-KEY-SEQ
           MOVE <source-field> TO OLD-INST-SEQ
           MOVE <source-field> TO INST-NEXT-PAY-DATE
           MOVE SPACES TO FILLER-068-068
           MOVE <source-field> TO QUAL-EXPENSE-DIST-FLAG
           MOVE <source-field> TO INST-GLOBAL-PAYMENT
           MOVE <source-field> TO INST-SETUP-TRANSACTION-SEQ
           MOVE <source-field> TO INST-SEQ
           MOVE SPACES TO FILLER-080-080
