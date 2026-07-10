      *> MAPTIVA stamped extract skeleton - card T404/01
      *> T404 Term - T404/01
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T404-01-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  REASON-CD-DISTRIBUTION-REASON PIC X            *> cols 9-9 Opt
           05  DIV-SUB-DIV-SUB              PIC X(4)         *> cols 10-13 Opt
           05  QUAL-FLG-IMMEDIATE-PAYMENT-IS-NOT-A-QUALIFIED-TOTAL-DISTRIBUTION PIC X            *> cols 14-14 Opt
           05  LUMP-SUM-FLG-DISTRIBUTION-IS-A-NON-LUMP-SUM-INSTALLMENT-PAYMENT PIC X            *> cols 15-15 Opt
           05  FILLER-016-016               PIC X(1)         *> cols 16-16 Not Used
           05  MAX-OMNI-SCRIPT-WDRLMAX-OMNI-SCRIPT-SUFFIX PIC X(2)         *> cols 17-18 Opt
           05  FORF-OMNI-SCRIPT-WDRLFORF-OMNI-SCRIPT-SUFFIX PIC X(2)         *> cols 19-20 Opt
           05  GADJ-OMNISCRIPT-FLG-ADJGROSSPMT-OMNI-SCRIPT-OPTIONS PIC X            *> cols 21-21 Opt
           05  LOAN-DEFAULT-OVR-LOAN-DISCHARGE-OPTIONS PIC X            *> cols 22-22 Opt
           05  ALT-ADDRESS-IND              PIC 9(3)         *> cols 23-25 Opt
           05  FILLER-026-028               PIC X(3)         *> cols 26-28 Not Used
           05  TRANSACTION-OVERRIDE         PIC X            *> cols 29-29 Opt
           05  FILLER-030-031               PIC X            *> cols 30-31 Not Used
           05  DEFER-DATE-DEFERRED-PAYMENTS-DATE-CCYYMMDD PIC 9(8)         *> cols 32-39 Opt
           05  DEFER-AGE-DEFERRED-PAYMENTS-AGE PIC 9(2)         *> cols 40-41 Opt
           05  FILLER-042-054               PIC X(13)        *> cols 42-54 Not Used
           05  QUAL-DEFER-PAY-FLAG-DEFERRED-PAYMENT-OR-INSTALLMENT-IS-A-QUALIFIED-TOTAL-DISTRIBUTION PIC X            *> cols 55-55 Opt
           05  QVEC-REASON-CD-QVEC-DISTRIBUTION-REASON PIC X            *> cols 56-56 Opt
           05  QVEC-QUAL-FLG-PAYMENT-IS-NOT-A-QVEC-DIST PIC X            *> cols 57-57 Opt
           05  TAXYEAR-FLAG-TAX-YEAR        PIC X            *> cols 58-58 Opt
           05  PREMATURE-DIST-EXCEP-PREMATURE-DISTRIBUTION-EXCEPTION PIC X            *> cols 59-59 Opt
           05  USAGE-CODE-1-USAGE-CODE      PIC X            *> cols 60-60 Opt
           05  CHECK-STATUS-CHECK-STATUS    PIC X            *> cols 61-61 Opt
           05  QUAL-EXPENSE-DIST-FLAG       PIC X            *> cols 62-62 Opt
           05  INST-SETUP-TRANSACTION-SEQ   PIC 9(7)         *> cols 63-69 Opt
           05  SOURCE-AGE-RESTRICTION-OVERRIDE PIC X            *> cols 70-70 Opt
           05  FILLER-071-080               PIC X(10)        *> cols 71-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO REASON-CD-DISTRIBUTION-REASON
           MOVE <source-field> TO DIV-SUB-DIV-SUB
           MOVE <source-field> TO QUAL-FLG-IMMEDIATE-PAYMENT-IS-NOT-A-QUALIFIED-TOTAL-DISTRIBUTION
           MOVE <source-field> TO LUMP-SUM-FLG-DISTRIBUTION-IS-A-NON-LUMP-SUM-INSTALLMENT-PAYMENT
           MOVE SPACES TO FILLER-016-016
           MOVE <source-field> TO MAX-OMNI-SCRIPT-WDRLMAX-OMNI-SCRIPT-SUFFIX
           MOVE <source-field> TO FORF-OMNI-SCRIPT-WDRLFORF-OMNI-SCRIPT-SUFFIX
           MOVE <source-field> TO GADJ-OMNISCRIPT-FLG-ADJGROSSPMT-OMNI-SCRIPT-OPTIONS
           MOVE <source-field> TO LOAN-DEFAULT-OVR-LOAN-DISCHARGE-OPTIONS
           MOVE <source-field> TO ALT-ADDRESS-IND
           MOVE SPACES TO FILLER-026-028
           MOVE <source-field> TO TRANSACTION-OVERRIDE
           MOVE SPACES TO FILLER-030-031
           MOVE <source-field> TO DEFER-DATE-DEFERRED-PAYMENTS-DATE-CCYYMMDD
           MOVE <source-field> TO DEFER-AGE-DEFERRED-PAYMENTS-AGE
           MOVE SPACES TO FILLER-042-054
           MOVE <source-field> TO QUAL-DEFER-PAY-FLAG-DEFERRED-PAYMENT-OR-INSTALLMENT-IS-A-QUALIFIED-TOTAL-DISTRIBUTION
           MOVE <source-field> TO QVEC-REASON-CD-QVEC-DISTRIBUTION-REASON
           MOVE <source-field> TO QVEC-QUAL-FLG-PAYMENT-IS-NOT-A-QVEC-DIST
           MOVE <source-field> TO TAXYEAR-FLAG-TAX-YEAR
           MOVE <source-field> TO PREMATURE-DIST-EXCEP-PREMATURE-DISTRIBUTION-EXCEPTION
           MOVE <source-field> TO USAGE-CODE-1-USAGE-CODE
           MOVE <source-field> TO CHECK-STATUS-CHECK-STATUS
           MOVE <source-field> TO QUAL-EXPENSE-DIST-FLAG
           MOVE <source-field> TO INST-SETUP-TRANSACTION-SEQ
           MOVE <source-field> TO SOURCE-AGE-RESTRICTION-OVERRIDE
           MOVE SPACES TO FILLER-071-080
