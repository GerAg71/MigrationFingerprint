      *> MAPTIVA stamped extract skeleton - card T404/02
      *> T404 Term - T404/02
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T404-02-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  ROLLOVER-USAGE-ROLLOVER-USAGE-CODE PIC X            *> cols 9-9 Opt
           05  MAND-WHOLD-ROLL-MANDATORY-WITHHOLDING-DOES-NOT-APPLY PIC X            *> cols 10-10 Opt
           05  INST-LESS-10-YRS             PIC X            *> cols 11-11 Opt
           05  REC02-TYPE-RESERVED-FOR-FUTURE-USE PIC X(3)         *> cols 12-14 Opt
           05  PAYEE-IND-RESERVED-FOR-FUTURE-USE PIC X            *> cols 15-15 Opt
           05  FILLER-016-076               PIC X(61)        *> cols 16-76 Not Used
           05  FILLER-077-080               PIC X(4)         *> cols 77-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO ROLLOVER-USAGE-ROLLOVER-USAGE-CODE
           MOVE <source-field> TO MAND-WHOLD-ROLL-MANDATORY-WITHHOLDING-DOES-NOT-APPLY
           MOVE <source-field> TO INST-LESS-10-YRS
           MOVE <source-field> TO REC02-TYPE-RESERVED-FOR-FUTURE-USE
           MOVE <source-field> TO PAYEE-IND-RESERVED-FOR-FUTURE-USE
           MOVE SPACES TO FILLER-016-076
           MOVE SPACES TO FILLER-077-080
