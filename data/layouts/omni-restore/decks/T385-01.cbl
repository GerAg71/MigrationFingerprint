      *> MAPTIVA stamped extract skeleton - card T385/01
      *> T385 Ln Pay - T385/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T385-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  PMT-DATE-OV-ACCEPT-PAYMENT-EVEN-IF-DATE-DOES-NOT-AGREE-WITH-NEXT-PAYMENT-DATE PIC X            *> cols 9-9 Opt
           05  LOAN-NUM-LOAN-NUMBER         PIC X(3)         *> cols 10-12 Opt
           05  PMT-FREQ-PAYMENT-FREQUENCY   PIC X            *> cols 13-13 Opt
           05  PMT-AMT-PAYMENT-AMOUNT       PIC 9(7)V99      *> cols 14-22 Opt
           05  PRINC-AMT-OV-APPLY-ENTIRE-PAYMENT-TO-PRINCIPAL PIC X            *> cols 23-23 Opt
           05  INT-AMT-ADDITIONAL-INTEREST  PIC 9(7)V99      *> cols 24-32 Opt
           05  PMT-OV-PAYMENT-MATCH-OPTIONS PIC X            *> cols 33-33 Opt
           05  ASOF-PCT-OPT-AS-OF-ALLOCATION-FLAG PIC X            *> cols 34-34 Opt
           05  REQUIRE-LOAN-NUM-LOAN-NUMBER-REQUIRED PIC X            *> cols 35-35 Opt
           05  USAGE-CODE-5                 PIC X            *> cols 36-36 Opt
           05  FILLER-037-040               PIC X(4)         *> cols 37-40 Not Used
           05  PAYMENT-IND-DISCHARGE-THE-LOAN PIC X            *> cols 41-41 Opt
           05  PAY-ER-FIRST-IND-APPLY-PAYMENT-TO-EMPLOYER-FUNDS-FIRST PIC X            *> cols 42-42 Opt
           05  SHR-PURCH-IND-AUTO-PURCHASE-OPTIONS PIC X            *> cols 43-43 Opt
           05  FUND-LIST-FUND-SEQUENCE-LIST PIC X(2)         *> cols 44-45 Opt
           05  PMT-TYPE-CODES-TYPE          PIC X(2)         *> cols 46-47 Opt
           05  FILLER-048-049               PIC X(2)         *> cols 48-49 Not Used
           05  MSG-ARREARS-LOAN-IN-ARREARS  PIC X            *> cols 50-50 Opt
           05  MSG-BACK-PMTS-BACK-PAYMENTS-MADE PIC X            *> cols 51-51 Opt
           05  MSG-ADV-PMTS-ADVANCE-PAYMENTS-MADE PIC X            *> cols 52-52 Opt
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO PMT-DATE-OV-ACCEPT-PAYMENT-EVEN-IF-DATE-DOES-NOT-AGREE-WITH-NEXT-PAYMENT-DATE
           MOVE <source-field> TO LOAN-NUM-LOAN-NUMBER
           MOVE <source-field> TO PMT-FREQ-PAYMENT-FREQUENCY
           MOVE <source-field> TO PMT-AMT-PAYMENT-AMOUNT
           MOVE <source-field> TO PRINC-AMT-OV-APPLY-ENTIRE-PAYMENT-TO-PRINCIPAL
           MOVE <source-field> TO INT-AMT-ADDITIONAL-INTEREST
           MOVE <source-field> TO PMT-OV-PAYMENT-MATCH-OPTIONS
           MOVE <source-field> TO ASOF-PCT-OPT-AS-OF-ALLOCATION-FLAG
           MOVE <source-field> TO REQUIRE-LOAN-NUM-LOAN-NUMBER-REQUIRED
           MOVE <source-field> TO USAGE-CODE-5
           MOVE SPACES TO FILLER-037-040
           MOVE <source-field> TO PAYMENT-IND-DISCHARGE-THE-LOAN
           MOVE <source-field> TO PAY-ER-FIRST-IND-APPLY-PAYMENT-TO-EMPLOYER-FUNDS-FIRST
           MOVE <source-field> TO SHR-PURCH-IND-AUTO-PURCHASE-OPTIONS
           MOVE <source-field> TO FUND-LIST-FUND-SEQUENCE-LIST
           MOVE <source-field> TO PMT-TYPE-CODES-TYPE
           MOVE SPACES TO FILLER-048-049
           MOVE <source-field> TO MSG-ARREARS-LOAN-IN-ARREARS
           MOVE <source-field> TO MSG-BACK-PMTS-BACK-PAYMENTS-MADE
           MOVE <source-field> TO MSG-ADV-PMTS-ADVANCE-PAYMENTS-MADE
