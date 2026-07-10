      *> MAPTIVA stamped extract skeleton - card T384/01
      *> T384 LN - T384/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T384-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  F-1STPYMT-DATE-DATES-1ST-PAYMENT-CCYYMMDD PIC 9(8)         *> cols 9-16 Req
           05  LOAN-AMT-LOAN-AMOUNT         PIC 9(7)V99      *> cols 17-25 Opt
           05  INT-RATE-PCT-INTEREST-RATE   PIC 9(3)V9(4)    *> cols 26-32 Req
           05  PMT-AMT-PAYMENT-AMOUNT       PIC 9(7)V99      *> cols 33-41 Req
           05  EXACT-TARGET-FLG-LOAN-AMOUNT-IS-A-TARGET-AMOUNT PIC X            *> cols 42-42 Opt
           05  NUM-PMTS-NUMBER-OF-PAYMENTS  PIC 9(4)         *> cols 43-46 Req
           05  PMT-FREQ-REPAYMENT-FREQUENCY PIC X            *> cols 47-47 Req
           05  AMT-OV-AMOUNT-OVERRIDE       PIC X            *> cols 48-48 Opt
           05  REPAY-OPT-REPAY-OPTIONS      PIC X            *> cols 49-49 Opt
           05  CONSTANT-DAY-INDICATOR       PIC X            *> cols 50-50 Opt
           05  LOAN-USE-IND-THIS-IS-A-PRINCIPAL-RESIDENCE-LOAN PIC X            *> cols 51-51 Opt
           05  INT-BAL-IND-DO-NOT-CALCULATE-UP-FRONT-INTEREST PIC X            *> cols 52-52 Opt
           05  SPEC-HAND-CODE               PIC X            *> cols 53-53 Opt
           05  CHECK-DEL-METHOD             PIC X            *> cols 54-54 Opt
           05  FILLER-055-056               PIC X(2)         *> cols 55-56 Not Used
           05  AMORT-TYPE-AMORT-TYPE        PIC X            *> cols 57-57 Opt
           05  MAX-OMNI-SCRIPT-LOANMAX-OMNI-SCRIPT-SUFFIX PIC X(2)         *> cols 58-59 Opt
           05  GADJ-OMNISCRIPT-FLAG-ADJGROSSPMT-OMNI-SCRIPT-OPTIONS PIC X            *> cols 60-60 Opt
           05  CHECK-STATUS-CHECK-STATUS    PIC 9            *> cols 61-61 Opt
           05  TOTAL-EXP-INT-TOTAL-EXPECTED-INTEREST PIC 9(6)V99      *> cols 62-69 Opt
           05  TOT-EXP-INT-OVR-OVERRIDE-CALCULATED-EXPECTED-INTEREST PIC X            *> cols 70-70 Opt
           05  PAYROLL-CODE-PAYROLL-CODE    PIC X(8)         *> cols 71-78 Opt
           05  FILLER-079-080               PIC X(2)         *> cols 79-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO F-1STPYMT-DATE-DATES-1ST-PAYMENT-CCYYMMDD
           MOVE <source-field> TO LOAN-AMT-LOAN-AMOUNT
           MOVE <source-field> TO INT-RATE-PCT-INTEREST-RATE
           MOVE <source-field> TO PMT-AMT-PAYMENT-AMOUNT
           MOVE <source-field> TO EXACT-TARGET-FLG-LOAN-AMOUNT-IS-A-TARGET-AMOUNT
           MOVE <source-field> TO NUM-PMTS-NUMBER-OF-PAYMENTS
           MOVE <source-field> TO PMT-FREQ-REPAYMENT-FREQUENCY
           MOVE <source-field> TO AMT-OV-AMOUNT-OVERRIDE
           MOVE <source-field> TO REPAY-OPT-REPAY-OPTIONS
           MOVE <source-field> TO CONSTANT-DAY-INDICATOR
           MOVE <source-field> TO LOAN-USE-IND-THIS-IS-A-PRINCIPAL-RESIDENCE-LOAN
           MOVE <source-field> TO INT-BAL-IND-DO-NOT-CALCULATE-UP-FRONT-INTEREST
           MOVE <source-field> TO SPEC-HAND-CODE
           MOVE <source-field> TO CHECK-DEL-METHOD
           MOVE SPACES TO FILLER-055-056
           MOVE <source-field> TO AMORT-TYPE-AMORT-TYPE
           MOVE <source-field> TO MAX-OMNI-SCRIPT-LOANMAX-OMNI-SCRIPT-SUFFIX
           MOVE <source-field> TO GADJ-OMNISCRIPT-FLAG-ADJGROSSPMT-OMNI-SCRIPT-OPTIONS
           MOVE <source-field> TO CHECK-STATUS-CHECK-STATUS
           MOVE <source-field> TO TOTAL-EXP-INT-TOTAL-EXPECTED-INTEREST
           MOVE <source-field> TO TOT-EXP-INT-OVR-OVERRIDE-CALCULATED-EXPECTED-INTEREST
           MOVE <source-field> TO PAYROLL-CODE-PAYROLL-CODE
           MOVE SPACES TO FILLER-079-080
