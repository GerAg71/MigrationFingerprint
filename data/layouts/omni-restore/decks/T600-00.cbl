      *> MAPTIVA stamped extract skeleton - card T600/00
      *> T600 Add a Plan - T600/00 Plan Record Creation
      *> Generated from the Omni Format Matrix. Do not hand-edit;
      *> recompile the matrix instead.
       01  T600-00-REC.
           05  TRAN-CODE                    PIC X(3)         *> cols 1-3 Req
           05  SEQ-CODE                     PIC X(2)         *> cols 4-5 Req
           05  FILLER-006-008               PIC X(3)         *> cols 6-8 Not Used
           05  RECORD-TYPE-TIHDR            PIC X(7)         *> cols 9-15 Req
           05  PLAN-NUMBER                  PIC X(6)         *> cols 16-21 Req
           05  FILLER-022-038               PIC X(17)        *> cols 22-38 Not Used
           05  FILLER-039-041               PIC X(3)         *> cols 39-41 Not Used
           05  TRADE-DATE                   PIC 9(8)         *> cols 42-49 Opt
           05  TRADE-TIME                   PIC 9(6)         *> cols 50-55 Opt
           05  CURRENCY-CODE                PIC X(5)         *> cols 56-60 Opt
           05  PASS-SEQUENCE                PIC X(1)         *> cols 61-61 Opt
           05  SUB-PASS-SEQUENCE            PIC X(3)         *> cols 62-64 Opt
           05  FILLER-065-080               PIC X(16)        *> cols 65-80 Not Used
      *> MOVE list (source master -> card image)
           MOVE <source-field> TO TRAN-CODE
           MOVE <source-field> TO SEQ-CODE
           MOVE SPACES TO FILLER-006-008
           MOVE <source-field> TO RECORD-TYPE-TIHDR
           MOVE <source-field> TO PLAN-NUMBER
           MOVE SPACES TO FILLER-022-038
           MOVE SPACES TO FILLER-039-041
           MOVE <source-field> TO TRADE-DATE
           MOVE <source-field> TO TRADE-TIME
           MOVE <source-field> TO CURRENCY-CODE
           MOVE <source-field> TO PASS-SEQUENCE
           MOVE <source-field> TO SUB-PASS-SEQUENCE
           MOVE SPACES TO FILLER-065-080
